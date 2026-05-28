import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from rclpy.time import Time
from sensor_msgs.msg import Image


IMAGE_TOPIC = '/camera/camera/color/image_raw'
HOST = '0.0.0.0'
PORT = 8080
JPEG_QUALITY = 75
MAX_EXPECTED_LATENCY_SEC = 0.3
STATS_INTERVAL_SEC = 1.0
LOG_STATS_ENABLED = False
MOTION_MIN_AREA_RATIO = 0.003


def read_bool_env(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'y', 'on')


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


class VideoStreamer(Node):
    def __init__(self, width, height, detection_enabled, drive_status_provider=None, deblur_enabled=None):
        super().__init__('video_streamer')
        qos_profile = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.subscription = self.create_subscription(
            Image,
            IMAGE_TOPIC,
            self.listener_callback,
            qos_profile)
        self.bridge = CvBridge()
        self.width = width
        self.height = height
        self.drive_status_provider = drive_status_provider
        if deblur_enabled is None:
            deblur_enabled = read_bool_env('CART_RIDER_DEBLUR', default=False)
        self.deblurrer = OpenCVMotionDeblurrer(deblur_enabled)
        self.detector = OpenCVMotionDetector(detection_enabled)
        self.lock = threading.Condition()
        self.latest_jpeg = None
        self.latest_frame_id = 0
        self.received_count = 0
        self.encoded_count = 0
        self.served_count = 0
        self.detected_count = 0
        self.last_stats_time = time.monotonic()
        self.last_latency_sec = None
        self.last_callback_ms = 0.0
        self.last_encode_ms = 0.0

        cv2.setUseOptimized(True)
        cv2.setNumThreads(1)
        self.get_logger().info(f'Subscribed to {IMAGE_TOPIC} with QoS depth=1 / best_effort.')
        self.get_logger().info(
            f'OpenCV encodes MJPEG at http://{HOST}:{PORT}/ . JPEG quality={JPEG_QUALITY}.'
        )
        if detection_enabled:
            self.get_logger().info('OpenCV motion detection is enabled. This detects moving regions, not semantic classes.')
        else:
            self.get_logger().info('OpenCV motion detection is disabled.')
        if self.deblurrer.enabled:
            self.get_logger().info(
                f'OpenCV motion deblur is enabled. length={self.deblurrer.length}, '
                f'angle={self.deblurrer.angle}, amount={self.deblurrer.amount}'
            )

    def listener_callback(self, msg):
        callback_start = time.monotonic()
        self.received_count += 1

        try:
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        except Exception as e:
            self.get_logger().error(f'Failed to convert image: {e}')
            return

        if self.width and self.height and (frame.shape[1] != self.width or frame.shape[0] != self.height):
            frame = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_NEAREST)

        frame = self.deblurrer.apply(frame)
        self.detected_count = self.detector.detect_and_draw(frame)
        self.last_latency_sec = self.get_image_latency(msg.header.stamp)
        self.draw_overlay(frame, self.last_latency_sec)

        encode_start = time.monotonic()
        ok, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        self.last_encode_ms = (time.monotonic() - encode_start) * 1000.0
        if not ok:
            self.get_logger().error('Failed to encode JPEG frame.')
            return

        jpeg_bytes = encoded.tobytes()
        with self.lock:
            self.latest_jpeg = jpeg_bytes
            self.latest_frame_id += 1
            self.encoded_count += 1
            self.last_callback_ms = (time.monotonic() - callback_start) * 1000.0
            self.lock.notify_all()

        self.log_stats_if_needed()

    def wait_for_jpeg(self, last_frame_id):
        with self.lock:
            self.lock.wait_for(
                lambda: self.latest_jpeg is not None and self.latest_frame_id != last_frame_id,
                timeout=1.0,
            )
            return self.latest_jpeg, self.latest_frame_id

    def mark_served(self):
        self.served_count += 1

    def get_image_latency(self, stamp_msg):
        stamp = Time.from_msg(stamp_msg)
        if stamp.nanoseconds == 0:
            return None
        return (self.get_clock().now() - stamp).nanoseconds / 1e9

    def draw_overlay(self, frame, latency_sec):
        if latency_sec is None:
            latency_text = 'latency: n/a'
        else:
            latency_text = f'latency: {latency_sec:.3f}s'
        color = (0, 255, 0) if latency_sec is None or latency_sec <= MAX_EXPECTED_LATENCY_SEC else (0, 0, 255)
        cv2.putText(frame, latency_text, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)
        if self.deblurrer.enabled:
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
            f'OpenCV objects: {self.detected_count}',
            (12, frame.shape[0] - 16),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        status = self.get_drive_status()
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

    def get_drive_status(self):
        if self.drive_status_provider is None:
            return None
        try:
            return self.drive_status_provider()
        except Exception as e:
            self.get_logger().warning(f'Failed to read drive status: {e}')
            return None

    def log_stats_if_needed(self):
        if not LOG_STATS_ENABLED:
            return

        now = time.monotonic()
        elapsed = now - self.last_stats_time
        if elapsed < STATS_INTERVAL_SEC:
            return

        receive_fps = self.received_count / elapsed
        encode_fps = self.encoded_count / elapsed
        served_fps = self.served_count / elapsed
        latency_text = 'n/a' if self.last_latency_sec is None else f'{self.last_latency_sec:.3f}s'
        level = self.get_logger().warning if self.last_latency_sec and self.last_latency_sec > MAX_EXPECTED_LATENCY_SEC else self.get_logger().info
        level(
            f'latency={latency_text}, receive_fps={receive_fps:.1f}, encode_fps={encode_fps:.1f}, '
            f'served_fps={served_fps:.1f}, objects={self.detected_count}, '
            f'callback={self.last_callback_ms:.1f}ms, jpeg={self.last_encode_ms:.1f}ms'
        )
        self.received_count = 0
        self.encoded_count = 0
        self.served_count = 0
        self.last_stats_time = now


class MJPEGHandler(BaseHTTPRequestHandler):
    streamer = None
    control_callback = None
    back_callback = None

    def do_POST(self):
        if self.path == '/back':
            callback = type(self).back_callback
            if callback is not None:
                callback()
            self.send_response(204)
            self.end_headers()
            return

        if self.path != '/control':
            self.send_error(404)
            return

        length = int(self.headers.get('Content-Length', '0') or 0)
        key = self.rfile.read(length).decode('utf-8', errors='ignore').strip().lower()
        callback = type(self).control_callback
        if callback is not None:
            callback(key)

        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        if self.path in ('/', '/index.html'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(
                b'<!doctype html><html><head><title>Cart Rider Stream</title>'
                b'<style>html,body{margin:0;width:100%;height:100%;background:#111;overflow:hidden}'
                b'body{display:grid;place-items:center}img{max-width:100vw;max-height:100vh;image-rendering:auto}'
                b'.hint{position:fixed;left:10px;top:8px;color:#fff;background:rgba(0,0,0,.45);'
                b'font:15px Arial,sans-serif;padding:6px 8px;border-radius:4px}</style></head>'
                b'<body tabindex="0"><div class="hint">Click here, then use w/a/s/d/z/c, b boost, q quit, Backspace previous page</div>'
                b'<img src="/stream.mjpg">'
                b'<script>document.body.focus();let last={};function send(k){fetch("/control",{method:"POST",body:k,cache:"no-store"}).catch(()=>{});}'
                b'function goBack(){fetch("/back",{method:"POST",cache:"no-store"}).finally(()=>{document.body.textContent="Returning...";document.body.style.color="white";document.body.style.font="36px Arial,sans-serif";setTimeout(()=>{window.location.href="/";},1200);});}'
                b'document.addEventListener("keydown",e=>{if(e.key==="Backspace"){e.preventDefault();goBack();return;}'
                b'const k=e.key.toLowerCase();if(!"wasdzcbq".includes(k))return;'
                b'e.preventDefault();const n=performance.now();if(k!=="b"&&k!=="q"&&last[k]&&n-last[k]<45)return;last[k]=n;send(k);});'
                b'document.addEventListener("click",()=>document.body.focus());</script></body></html>'
            )
            return

        if self.path != '/stream.mjpg':
            self.send_error(404)
            return

        self.send_response(200)
        self.send_header('Age', '0')
        self.send_header('Cache-Control', 'no-cache, private')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
        self.end_headers()

        last_frame_id = 0
        while True:
            jpeg, frame_id = self.streamer.wait_for_jpeg(last_frame_id)
            if jpeg is None or frame_id == last_frame_id:
                continue
            last_frame_id = frame_id
            try:
                self.wfile.write(b'--frame\r\n')
                self.wfile.write(b'Content-Type: image/jpeg\r\n')
                self.wfile.write(f'Content-Length: {len(jpeg)}\r\n\r\n'.encode('ascii'))
                self.wfile.write(jpeg)
                self.wfile.write(b'\r\n')
                self.streamer.mark_served()
            except (BrokenPipeError, ConnectionResetError):
                break

    def log_message(self, format, *args):
        return


def read_dimension(prompt):
    value = input(prompt).strip()
    if value == '':
        return 0
    return int(value)


def read_yes_no(prompt, default=True):
    suffix = 'Y/n' if default else 'y/N'
    value = input(f'{prompt} ({suffix}): ').strip().lower()
    if value == '':
        return default
    return value in ('y', 'yes', '1', 'true')


def spin_node(node):
    try:
        rclpy.spin(node)
    except ExternalShutdownException:
        pass


def main(args=None):
    try:
        width = read_dimension('Enter stream width, or press Enter for camera native width: ')
        height = read_dimension('Enter stream height, or press Enter for camera native height: ')
    except ValueError:
        print('Invalid input. Please enter integer values for width and height.')
        sys.exit(1)

    if width < 0 or height < 0:
        print('Width and height must be positive integers, or blank for native size.')
        sys.exit(1)
    if (width == 0) != (height == 0):
        print('Enter both width and height, or leave both blank for native size.')
        sys.exit(1)

    detection_enabled = read_yes_no('Enable OpenCV motion detection', default=True)

    rclpy.init(args=args)
    streamer = VideoStreamer(width, height, detection_enabled)
    MJPEGHandler.streamer = streamer
    server = ThreadingHTTPServer((HOST, PORT), MJPEGHandler)

    spin_thread = threading.Thread(target=spin_node, args=(streamer,), daemon=True)
    spin_thread.start()
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    print(f'Open this URL in a browser: http://{HOST}:{PORT}/')
    print('Press CTRL+C here to stop.')

    try:
        while rclpy.ok():
            time.sleep(0.2)
    except KeyboardInterrupt:
        print('\nKeyboard Interrupt (CTRL+C) received. Exiting...')
    finally:
        server.shutdown()
        server.server_close()
        streamer.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        spin_thread.join(timeout=1.0)
        server_thread.join(timeout=1.0)


if __name__ == '__main__':
    main()
