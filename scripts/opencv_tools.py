import os

import cv2
import numpy as np

from stream_config import MOTION_MIN_AREA_RATIO


class OpenCVMotionDeblurrer:
    def __init__(self, enabled):
        self.enabled = enabled
        self.length = max(3, int(os.getenv('CART_RIDER_DEBLUR_LENGTH', '9')))
        self.angle = float(os.getenv('CART_RIDER_DEBLUR_ANGLE', '0'))
        self.amount = float(os.getenv('CART_RIDER_DEBLUR_AMOUNT', '0.7'))
        self.kernel = self.create_motion_kernel(self.length, self.angle)

    def create_motion_kernel(self, length, angle):
        if length % 2 == 0:
            length += 1
            self.length = length

        center = length // 2
        kernel = np.zeros((length, length), dtype=np.float32)
        kernel[center, :] = 1.0
        rotation = cv2.getRotationMatrix2D((center, center), angle, 1.0)
        kernel = cv2.warpAffine(kernel, rotation, (length, length))
        kernel_sum = kernel.sum()
        if kernel_sum > 0:
            kernel /= kernel_sum
        return kernel

    def apply(self, frame):
        if not self.enabled:
            return frame

        blurred = cv2.filter2D(frame, -1, self.kernel)
        return cv2.addWeighted(frame, 1.0 + self.amount, blurred, -self.amount, 0)


class OpenCVMotionDetector:
    def __init__(self, enabled):
        self.enabled = enabled
        self.subtractor = cv2.createBackgroundSubtractorMOG2(
            history=120,
            varThreshold=25,
            detectShadows=True,
        )
        self.kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        self.warmup_frames = 30
        self.frame_count = 0

    def detect_and_draw(self, frame):
        if not self.enabled:
            return 0

        self.frame_count += 1
        blurred = cv2.GaussianBlur(frame, (5, 5), 0)
        fg_mask = self.subtractor.apply(blurred)

        if self.frame_count <= self.warmup_frames:
            cv2.putText(
                frame,
                'OpenCV motion detector warming up...',
                (12, 58),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )
            return 0

        _, fg_mask = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, self.kernel, iterations=1)
        fg_mask = cv2.dilate(fg_mask, self.kernel, iterations=2)

        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        min_area = frame.shape[0] * frame.shape[1] * MOTION_MIN_AREA_RATIO
        boxes = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            boxes.append((x, y, w, h, area))

        boxes.sort(key=lambda item: item[4], reverse=True)
        for index, (x, y, w, h, _area) in enumerate(boxes[:8], start=1):
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 220, 255), 2)
            cv2.putText(
                frame,
                f'motion object {index}',
                (x, max(20, y - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 220, 255),
                2,
                cv2.LINE_AA,
            )
        return min(len(boxes), 8)
