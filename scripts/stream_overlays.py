import cv2

from stream_config import MAX_EXPECTED_LATENCY_SEC


class StreamOverlayRenderer:
    def __init__(self, streamer):
        self.streamer = streamer

    def draw_overlay(self, frame, latency_sec):
        if self.streamer.game_mode:
            self.draw_game_overlay(frame)
            return

        if latency_sec is None:
            latency_text = 'latency: n/a'
        else:
            latency_text = f'latency: {latency_sec:.3f}s'
        color = (0, 255, 0) if latency_sec is None or latency_sec <= MAX_EXPECTED_LATENCY_SEC else (0, 0, 255)
        cv2.putText(frame, latency_text, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)
        if self.streamer.deblurrer.enabled:
            cv2.putText(
                frame,
                'OpenCV deblur: ON',
                (12, 58),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )
        cv2.putText(
            frame,
            f'OpenCV objects: {self.streamer.detected_count}',
            (12, frame.shape[0] - 16),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        status = self.streamer.get_drive_status()
        if status is None:
            return

        speed = status.get('speed', 0)
        boost_active = status.get('boost_active', False)
        mode = 'BOOST' if boost_active else 'BASE'
        cv2.putText(
            frame,
            f'drive speed: {speed} ({mode})',
            (12, frame.shape[0] - 46),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 255) if boost_active else (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        cooldown_remaining = status.get('boost_cooldown_remaining', 0.0)
        cooldown_text = f'boost cooldown: {cooldown_remaining:.1f}s'
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        thickness = 2
        text_size, _baseline = cv2.getTextSize(cooldown_text, font, font_scale, thickness)
        x = max(12, frame.shape[1] - text_size[0] - 12)
        color = (0, 255, 255) if cooldown_remaining > 0 else (0, 255, 0)
        cv2.putText(
            frame,
            cooldown_text,
            (x, 28),
            font,
            font_scale,
            color,
            thickness,
            cv2.LINE_AA,
        )

    def draw_game_overlay(self, frame):
        cv2.putText(
            frame,
            'RACE mode',
            (12, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )

        status = self.streamer.get_drive_status()
        if status is None:
            return

        speed = status.get('speed', 0)
        boost_active = status.get('boost_active', False)
        cooldown_remaining = status.get('boost_cooldown_remaining', 0.0)
        mode = 'BOOST' if boost_active else 'BASE'
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.65
        thickness = 2
        line_y = frame.shape[0] - 18

        cv2.putText(
            frame,
            f'drive speed: {speed} ({mode})',
            (12, line_y),
            font,
            font_scale,
            (0, 255, 255) if boost_active else (255, 255, 255),
            thickness,
            cv2.LINE_AA,
        )

        cooldown_text = f'boost cooldown: {cooldown_remaining:.1f}s'
        text_size, _baseline = cv2.getTextSize(cooldown_text, font, font_scale, thickness)
        x = max(12, frame.shape[1] - text_size[0] - 12)
        cv2.putText(
            frame,
            cooldown_text,
            (x, line_y),
            font,
            font_scale,
            (0, 255, 255) if cooldown_remaining > 0 else (0, 255, 0),
            thickness,
            cv2.LINE_AA,
        )

    def draw_race_result_overlay(self, frame):
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (frame.shape[1], frame.shape[0]), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)

        elapsed = self.streamer.race_timer.elapsed_time
        final_score = self.streamer.race_timer.final_score()
        lines = [
            f'Time: {elapsed:.2f}s',
            f'Final score: {final_score:.2f}',
        ]
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = max(0.8, min(1.4, frame.shape[1] / 650.0))
        thickness = 2
        line_height = int(42 * font_scale)
        total_h = line_height * len(lines)
        y = max(40, (frame.shape[0] - total_h) // 2)
        max_w = max(cv2.getTextSize(line, font, font_scale, thickness)[0][0] for line in lines)
        x = max(20, (frame.shape[1] - max_w) // 2)
        for line in lines:
            cv2.putText(frame, line, (x, y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
            y += line_height


