import os
import time

import cv2
import numpy as np

from stream_config import (
    RACE_EDGE_MIN_PIXELS, RACE_GOAL_CONFIRM_FRAMES,
    RACE_GOAL_MIN_FRAME_RATIO, RACE_GOAL_RED_MIN_RATIO, RACE_GOAL_THRESHOLD,
    RACE_GOAL_WHITE_MIN_RATIO, RACE_RESULT_DELAY_SEC,
    RACE_SCALES_TEXT, RACE_START_CONFIRM_FRAMES, RACE_START_MIN_FRAME_RATIO,
    RACE_TEMPLATE_CHECK_EVERY_N_FRAMES,
    RACE_START_THRESHOLD, RACE_START_WHITE_MIN_RATIO, read_float_list_env,
)


class RaceTemplateTimer:
    def __init__(self, logger):
        self.logger = logger
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = os.path.join(os.path.dirname(self.base_dir), 'data')
        self.start_template = self.load_template('START.png')
        self.goal_template = self.load_template('GOAL.png')
        self.last_gray_edges = None
        self.scales = read_float_list_env(RACE_SCALES_TEXT)
        self.frame_index = 0
        self.state = 'waiting'
        self.start_time = None
        self.finish_time = None
        self.elapsed_time = 0.0
        self.best_start = None
        self.best_goal = None
        self.start_confirm_count = 0
        self.goal_confirm_count = 0
        self.last_event = 'Looking for START'
        self.enabled = self.start_template is not None and self.goal_template is not None
        if self.enabled:
            self.logger.info(
                'Race timer is enabled. START threshold='
                f'{RACE_START_THRESHOLD:.2f}, GOAL threshold={RACE_GOAL_THRESHOLD:.2f}, '
                f'GOAL frame ratio={RACE_GOAL_MIN_FRAME_RATIO:.2f}'
            )
        else:
            self.logger.warning('Race timer disabled because data/START.png or data/GOAL.png could not be loaded.')

    def load_template(self, filename):
        path = os.path.join(self.data_dir, filename)
        template = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if template is None:
            self.logger.warning(f'Failed to load race template: {path}')
            return None
        return template

    def update_and_draw(self, frame, draw_debug=True, draw_status=True, fast_color_only=False):
        if not self.enabled:
            self.draw_status(frame, (0, 0, 255))
            return

        if self.state == 'running' and self.start_time is not None:
            self.elapsed_time = time.monotonic() - self.start_time

        self.frame_index += 1
        if self.frame_index % RACE_TEMPLATE_CHECK_EVERY_N_FRAMES == 1:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            self.last_gray_edges = cv2.Canny(gray, 80, 180)
            if self.state == 'waiting':
                template_start = self.find_best_match(gray, self.start_template)
                color_start = self.find_blue_start_region(frame)
                self.best_start = template_start or color_start
                if not fast_color_only and color_start and (self.best_start is None or color_start['frame_ratio'] > self.best_start.get('frame_ratio', 0.0)):
                    self.best_start = color_start
                if self.best_start:
                    start_ratio = self.best_start.get('frame_ratio') or self.best_start['area'] / (frame.shape[0] * frame.shape[1])
                    self.best_start['frame_ratio'] = start_ratio
                    template_ok = template_start is not None and template_start['score'] >= RACE_START_THRESHOLD
                    color_ok = color_start is not None and color_start.get('white_ratio', 0.0) >= RACE_START_WHITE_MIN_RATIO and color_start['frame_ratio'] >= RACE_START_MIN_FRAME_RATIO
                    start_ok = color_ok if fast_color_only else (template_ok or color_ok)
                    if start_ok:
                        self.start_confirm_count += 1
                    else:
                        self.start_confirm_count = 0
                    if self.start_confirm_count >= RACE_START_CONFIRM_FRAMES:
                        self.state = 'running'
                        self.start_time = time.monotonic()
                        self.finish_time = None
                        self.elapsed_time = 0.0
                        self.start_confirm_count = 0
                        self.goal_confirm_count = 0
                        self.last_event = 'START detected'
                        self.logger.info(
                            f'Race started. START score={self.best_start["score"]:.3f}, '
                            f'frame_ratio={start_ratio:.3f}, source={self.best_start.get("source", "template")}, '
                            f'box={self.best_start["box"]}'
                        )
                else:
                    self.start_confirm_count = 0
            elif self.state == 'running':
                self.best_start = None
                self.best_goal = None if fast_color_only else self.find_best_match(gray, self.goal_template)
                color_goal = self.find_red_goal_region(frame)
                if self.best_goal is None or (color_goal and color_goal['frame_ratio'] > self.best_goal['frame_ratio']):
                    self.best_goal = color_goal
                self.elapsed_time = time.monotonic() - self.start_time
                if self.best_goal:
                    frame_area = frame.shape[0] * frame.shape[1]
                    goal_ratio = self.best_goal.get('frame_ratio') or self.best_goal['area'] / frame_area
                    self.best_goal['frame_ratio'] = goal_ratio
                    template_ok = self.best_goal['score'] >= RACE_GOAL_THRESHOLD
                    color_ok = self.best_goal.get('source') == 'red+white' and self.best_goal.get('white_ratio', 0.0) >= RACE_GOAL_WHITE_MIN_RATIO
                    goal_ok = color_ok or (template_ok and color_goal is not None)
                    if goal_ratio >= RACE_GOAL_MIN_FRAME_RATIO and goal_ok:
                        self.goal_confirm_count += 1
                    else:
                        self.goal_confirm_count = 0
                    if self.goal_confirm_count >= RACE_GOAL_CONFIRM_FRAMES:
                        self.state = 'finished'
                        self.finish_time = time.monotonic()
                        self.elapsed_time = self.finish_time - self.start_time
                        self.goal_confirm_count = 0
                        self.last_event = 'GOAL detected'
                        self.logger.info(
                            f'Race finished. elapsed={self.elapsed_time:.3f}s, '
                            f'GOAL score={self.best_goal["score"]:.3f}, frame_ratio={goal_ratio:.3f}, '
                            f'white_ratio={self.best_goal.get("white_ratio", 0.0):.3f}, '
                            f'source={self.best_goal.get("source", "template")}, box={self.best_goal["box"]}'
                        )
                else:
                    self.goal_confirm_count = 0
            elif self.state == 'finished':
                self.elapsed_time = self.finish_time - self.start_time

        if draw_debug:
            self.draw_matches(frame)
        if draw_status:
            status_color = (0, 255, 0) if self.state == 'running' else (0, 255, 255)
            if self.state == 'finished':
                status_color = (255, 255, 255)
            self.draw_status(frame, status_color)

    def final_score(self):
        return self.elapsed_time

    def result_ready(self):
        return self.state == 'finished' and self.finish_time is not None and time.monotonic() - self.finish_time >= RACE_RESULT_DELAY_SEC

    def find_best_match(self, gray_frame, template):
        best = None
        frame_h, frame_w = gray_frame.shape[:2]
        template_h, template_w = template.shape[:2]
        frame_edges = self.last_gray_edges
        if frame_edges is None:
            frame_edges = cv2.Canny(gray_frame, 80, 180)

        for scale in self.scales:
            scaled_w = max(8, int(template_w * scale))
            scaled_h = max(8, int(template_h * scale))
            if scaled_w > frame_w or scaled_h > frame_h:
                continue

            scaled = cv2.resize(template, (scaled_w, scaled_h), interpolation=cv2.INTER_AREA)
            template_edges = cv2.Canny(scaled, 80, 180)
            if cv2.countNonZero(template_edges) < RACE_EDGE_MIN_PIXELS:
                continue

            result = cv2.matchTemplate(frame_edges, template_edges, cv2.TM_CCOEFF_NORMED)
            _min_val, max_val, _min_loc, max_loc = cv2.minMaxLoc(result)
            if best is None or max_val > best['score']:
                x, y = max_loc
                best = {
                    'score': float(max_val),
                    'scale': scale,
                    'box': (x, y, scaled_w, scaled_h),
                    'area': scaled_w * scaled_h,
                    'frame_ratio': 0.0,
                }

        return best

    def find_blue_start_region(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower_blue = np.array([80, 60, 70], dtype=np.uint8)
        upper_blue = np.array([110, 255, 255], dtype=np.uint8)
        blue_mask = cv2.inRange(hsv, lower_blue, upper_blue)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        blue_mask = cv2.morphologyEx(blue_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        contours, _ = cv2.findContours(blue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        frame_area = frame.shape[0] * frame.shape[1]
        best = None
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            if area < frame_area * RACE_START_MIN_FRAME_RATIO:
                continue
            aspect = w / max(1, h)
            if aspect < 0.8 or aspect > 3.2:
                continue

            roi_hsv = hsv[y:y + h, x:x + w]
            blue_pixels = cv2.countNonZero(blue_mask[y:y + h, x:x + w])
            blue_ratio = blue_pixels / max(1, area)
            white_mask = cv2.inRange(roi_hsv, np.array([0, 0, 145], dtype=np.uint8), np.array([179, 90, 255], dtype=np.uint8))
            white_ratio = cv2.countNonZero(white_mask) / max(1, area)
            if blue_ratio < 0.35 or white_ratio < RACE_START_WHITE_MIN_RATIO:
                continue

            match = {
                'score': 1.0,
                'scale': 0.0,
                'box': (x, y, w, h),
                'area': area,
                'frame_ratio': area / frame_area,
                'white_ratio': white_ratio,
                'source': 'blue+white',
            }
            if best is None or match['area'] > best['area']:
                best = match
        return best

    def find_red_goal_region(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower_red1 = np.array([0, 70, 70], dtype=np.uint8)
        upper_red1 = np.array([12, 255, 255], dtype=np.uint8)
        lower_red2 = np.array([165, 70, 70], dtype=np.uint8)
        upper_red2 = np.array([179, 255, 255], dtype=np.uint8)
        red_mask = cv2.inRange(hsv, lower_red1, upper_red1) | cv2.inRange(hsv, lower_red2, upper_red2)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        frame_area = frame.shape[0] * frame.shape[1]
        best = None
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            if area < frame_area * 0.05:
                continue
            aspect = w / max(1, h)
            if aspect < 0.8 or aspect > 2.8:
                continue

            roi = frame[y:y + h, x:x + w]
            roi_hsv = hsv[y:y + h, x:x + w]
            red_pixels = cv2.countNonZero(red_mask[y:y + h, x:x + w])
            red_ratio = red_pixels / max(1, area)
            white_mask = cv2.inRange(roi_hsv, np.array([0, 0, 150], dtype=np.uint8), np.array([179, 80, 255], dtype=np.uint8))
            white_ratio = cv2.countNonZero(white_mask) / max(1, area)
            if red_ratio < RACE_GOAL_RED_MIN_RATIO or white_ratio < RACE_GOAL_WHITE_MIN_RATIO:
                continue

            match = {
                'score': 1.0,
                'scale': 0.0,
                'box': (x, y, w, h),
                'area': area,
                'frame_ratio': area / frame_area,
                'white_ratio': white_ratio,
                'source': 'red+white',
            }
            if best is None or match['area'] > best['area']:
                best = match
        return best

    def draw_matches(self, frame):
        if self.best_start and self.state == 'waiting':
            self.draw_match(frame, self.best_start, 'START', (0, 255, 255))
        if self.best_goal and self.state in ('running', 'finished'):
            self.draw_match(frame, self.best_goal, 'GOAL', (0, 255, 0))

    def draw_match(self, frame, match, label, color):
        x, y, w, h = match['box']
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
        cv2.putText(
            frame,
            self.format_match_label(label, match),
            (x, max(20, y - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
            cv2.LINE_AA,
        )

    def format_match_label(self, label, match):
        if label == 'GOAL':
            source = 'color' if match.get('source') == 'red+white' else 'tmpl'
            return f'{label} {match["score"]:.2f} area {match.get("frame_ratio", 0.0):.2f} {source}'
        if label == 'START':
            source = 'color' if match.get('source') == 'blue+white' else 'tmpl'
            return f'{label} {match["score"]:.2f} area {match.get("frame_ratio", 0.0):.2f} {source}'
        return f'{label} {match["score"]:.2f}'

    def draw_status(self, frame, color):
        if self.state == 'waiting':
            text = self.last_event
        elif self.state == 'running':
            text = f'RACE RUNNING {self.elapsed_time:.2f}s'
        else:
            text = f'RACE FINISHED {self.elapsed_time:.2f}s'

        cv2.rectangle(frame, (8, 70), (360, 108), (0, 0, 0), -1)
        cv2.putText(
            frame,
            text,
            (12, 96),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            color,
            2,
            cv2.LINE_AA,
        )
