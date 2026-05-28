import os
import sys
import threading
import time
from pathlib import Path

import cv2
import numpy as np

import camera_stream


YOLOV5_ROOT = Path(os.getenv('CART_RIDER_YOLOV5_ROOT', '/home/cartrider/yolov5'))
YOLOV5_VENV_SITE = Path(
    os.getenv('CART_RIDER_YOLOV5_SITE', '/home/cartrider/yolov5/yolov5/lib/python3.12/site-packages')
)
DEFAULT_WEIGHTS = YOLOV5_ROOT / 'yolov5n.pt'
YOLO_WEIGHTS = Path(os.getenv('CART_RIDER_YOLO_WEIGHTS', str(DEFAULT_WEIGHTS))).expanduser()
YOLO_IMAGE_SIZE = int(os.getenv('CART_RIDER_YOLO_IMGSZ', '256'))
YOLO_CONF_THRES = float(os.getenv('CART_RIDER_YOLO_CONF', '0.35'))
YOLO_IOU_THRES = float(os.getenv('CART_RIDER_YOLO_IOU', '0.45'))
YOLO_MAX_DET = int(os.getenv('CART_RIDER_YOLO_MAX_DET', '12'))
YOLO_INFER_EVERY_N_FRAMES = max(1, int(os.getenv('CART_RIDER_YOLO_EVERY_N', '3')))

HOST = camera_stream.HOST
PORT = camera_stream.PORT
MJPEGHandler = camera_stream.MJPEGHandler
spin_node = camera_stream.spin_node


def _prepare_yolov5_imports():
    # ROS/cv_bridge/OpenCV are imported by camera_stream before this point. Keep
    # YOLO venv paths after system paths so its NumPy does not replace ROS NumPy.
    site = str(YOLOV5_VENV_SITE)
    root = str(YOLOV5_ROOT)
    if site not in sys.path:
        sys.path.append(site)
    if root not in sys.path:
        sys.path.insert(0, root)


class YOLOv5ObjectDetector:
    def __init__(self, enabled, logger):
        self.enabled = enabled
        self.logger = logger
        self.ready = False
        self.error_message = None
        self.model = None
        self.torch = None
        self.names = {}
        self.stride = 32
        self.frame_index = 0
        self.last_detections = []
        self.last_infer_ms = 0.0
        self.lock = threading.Lock()
        self.worker_event = threading.Event()
        self.pending_frame = None
        self.worker_busy = False
        self.worker_thread = None

        if self.enabled:
            self.load_model()
            if self.ready:
                self.worker_thread = threading.Thread(target=self.worker_loop, daemon=True)
                self.worker_thread.start()

    def load_model(self):
        if not YOLO_WEIGHTS.exists():
            self.error_message = f'YOLO weights not found: {YOLO_WEIGHTS}'
            self.logger.warning(self.error_message)
            return

        try:
            _prepare_yolov5_imports()
            import torch
            from models.common import DetectMultiBackend

            self.torch = torch
            torch.set_num_threads(max(1, int(os.getenv('CART_RIDER_YOLO_TORCH_THREADS', '2'))))
            device = torch.device('cpu')
            self.model = DetectMultiBackend(str(YOLO_WEIGHTS), device=device, dnn=False, fp16=False)
            self.stride = int(getattr(self.model, 'stride', 32))
            self.names = getattr(self.model, 'names', {}) or {}
            self.model.warmup(imgsz=(1, 3, YOLO_IMAGE_SIZE, YOLO_IMAGE_SIZE))
            self.ready = True
            self.logger.info(
                f'YOLOv5 object detection enabled. weights={YOLO_WEIGHTS}, imgsz={YOLO_IMAGE_SIZE}, device=cpu'
            )
        except Exception as e:
            self.error_message = f'YOLO unavailable: {e}'
            self.logger.error(self.error_message)

    def detect_and_draw(self, frame):
        if not self.enabled:
            return 0
        if not self.ready:
            self.draw_unavailable(frame)
            return 0

        self.frame_index += 1
        if self.frame_index % YOLO_INFER_EVERY_N_FRAMES == 1:
            self.submit_frame(frame)

        with self.lock:
            detections = list(self.last_detections)
            infer_ms = self.last_infer_ms

        self.draw_detections(frame, detections, infer_ms)
        return len(detections)

    def submit_frame(self, frame):
        with self.lock:
            if self.worker_busy:
                return
            self.pending_frame = frame.copy()
            self.worker_busy = True
            self.worker_event.set()

    def worker_loop(self):
        while True:
            self.worker_event.wait()
            self.worker_event.clear()
            with self.lock:
                frame = self.pending_frame
                self.pending_frame = None
            if frame is None:
                with self.lock:
                    self.worker_busy = False
                continue

            detections = self.infer(frame)
            with self.lock:
                self.last_detections = detections
                self.worker_busy = False


    def infer(self, frame):
        try:
            from utils.augmentations import letterbox
            from utils.general import non_max_suppression, scale_boxes

            start = time.monotonic()
            image = letterbox(frame, YOLO_IMAGE_SIZE, stride=self.stride, auto=True)[0]
            image = image[:, :, ::-1].transpose(2, 0, 1)
            image = np.ascontiguousarray(image)
            tensor = self.torch.from_numpy(image).to(self.model.device).float() / 255.0
            if tensor.ndimension() == 3:
                tensor = tensor.unsqueeze(0)

            pred = self.model(tensor, augment=False, visualize=False)
            pred = non_max_suppression(
                pred,
                YOLO_CONF_THRES,
                YOLO_IOU_THRES,
                max_det=YOLO_MAX_DET,
            )

            detections = []
            for det in pred:
                if len(det) == 0:
                    continue
                det[:, :4] = scale_boxes(tensor.shape[2:], det[:, :4], frame.shape).round()
                for *xyxy, conf, cls in det:
                    cls_id = int(cls.item())
                    label = self.names.get(cls_id, str(cls_id)) if isinstance(self.names, dict) else self.names[cls_id]
                    detections.append((tuple(int(v.item()) for v in xyxy), float(conf.item()), label))

            self.last_infer_ms = (time.monotonic() - start) * 1000.0
            return detections
        except Exception as e:
            self.error_message = f'YOLO inference failed: {e}'
            self.logger.error(self.error_message)
            self.ready = False
            return []

    def draw_detections(self, frame, detections, infer_ms=None):
        for index, (xyxy, conf, label) in enumerate(detections):
            x1, y1, x2, y2 = xyxy
            color = (50, 220, 50)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            text = f'{label} {conf:.2f}'
            text_size, baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
            y_text = max(20, y1 - 8)
            cv2.rectangle(
                frame,
                (x1, y_text - text_size[1] - baseline - 4),
                (x1 + text_size[0] + 6, y_text + baseline),
                color,
                -1,
            )
            cv2.putText(
                frame,
                text,
                (x1 + 3, y_text - 3),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 0, 0),
                2,
                cv2.LINE_AA,
            )

        cv2.putText(
            frame,
            f'YOLO objects: {len(detections)} infer: {(self.last_infer_ms if infer_ms is None else infer_ms):.1f}ms',
            (12, 58),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (50, 220, 50),
            2,
            cv2.LINE_AA,
        )

    def draw_unavailable(self, frame):
        message = self.error_message or 'YOLO unavailable'
        cv2.putText(
            frame,
            message[:90],
            (12, 58),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 0, 255),
            2,
            cv2.LINE_AA,
        )


class VideoStreamer(camera_stream.VideoStreamer):
    def __init__(self, width, height, detection_enabled, drive_status_provider=None, deblur_enabled=False):
        super().__init__(width, height, False, drive_status_provider=drive_status_provider, deblur_enabled=False)
        self.detector = YOLOv5ObjectDetector(detection_enabled, self.get_logger())
        if not detection_enabled:
            self.get_logger().info('YOLO object detection is disabled.')

    def draw_overlay(self, frame, latency_sec):
        super().draw_overlay(frame, latency_sec)
        cv2.rectangle(frame, (8, frame.shape[0] - 38), (290, frame.shape[0] - 5), (0, 0, 0), -1)
        cv2.putText(
            frame,
            f'YOLO objects: {self.detected_count}',
            (12, frame.shape[0] - 16),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
