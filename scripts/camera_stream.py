import sys
import threading
import time
from http.server import ThreadingHTTPServer

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from rclpy.time import Time
from sensor_msgs.msg import Image

from opencv_tools import OpenCVMotionDeblurrer, OpenCVMotionDetector
from race_timer import RaceTemplateTimer
from stream_http import ControlHandler, MJPEGHandler
from stream_overlays import StreamOverlayRenderer
from stream_config import (
    CONTROL_PORT, HOST,
    IMAGE_TOPIC, JPEG_QUALITY, LOG_STATS_ENABLED, MAX_EXPECTED_LATENCY_SEC, PORT,
    STATS_INTERVAL_SEC, STREAM_MAX_FPS, read_bool_env,
)


class VideoStreamer(Node):
    def __init__(self, width, height, detection_enabled, drive_status_provider=None, deblur_enabled=None, game_mode=False):
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
        self.game_mode = game_mode
        if deblur_enabled is None:
            deblur_enabled = read_bool_env('CART_RIDER_DEBLUR', default=False)
        self.deblurrer = OpenCVMotionDeblurrer(deblur_enabled)
        self.detector = OpenCVMotionDetector(detection_enabled)
        self.race_features_enabled = game_mode or detection_enabled
        self.race_timer = RaceTemplateTimer(self.get_logger())
        self.overlay_renderer = StreamOverlayRenderer(self)
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
        self.min_encode_interval = 0.0 if STREAM_MAX_FPS <= 0 else 1.0 / STREAM_MAX_FPS
        self.last_encode_time = 0.0

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

        now = time.monotonic()
        if self.min_encode_interval > 0 and now - self.last_encode_time < self.min_encode_interval:
            return
        self.last_encode_time = now

        frame = self.deblurrer.apply(frame)
        self.detected_count = self.detector.detect_and_draw(frame)
        if self.race_features_enabled:
            self.race_timer.update_and_draw(
                frame,
                draw_debug=not self.game_mode,
                draw_status=True,
                fast_color_only=self.game_mode,
            )
        self.last_latency_sec = self.get_image_latency(msg.header.stamp)
        self.draw_overlay(frame, self.last_latency_sec)
        if self.game_mode and self.race_timer.result_ready():
            self.draw_race_result_overlay(frame)

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
        self.overlay_renderer.draw_overlay(frame, latency_sec)


    def draw_race_result_overlay(self, frame):
        self.overlay_renderer.draw_race_result_overlay(frame)

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
