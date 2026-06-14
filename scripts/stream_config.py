import os


IMAGE_TOPIC = '/camera/camera/color/image_raw'
HOST = '0.0.0.0'
PORT = 8080
CONTROL_PORT = int(os.getenv('CART_RIDER_CONTROL_PORT', '8081'))
JPEG_QUALITY = int(os.getenv('CART_RIDER_JPEG_QUALITY', '55'))
STREAM_MAX_FPS = float(os.getenv('CART_RIDER_STREAM_FPS', '12'))
MAX_EXPECTED_LATENCY_SEC = 0.3
STATS_INTERVAL_SEC = 1.0
LOG_STATS_ENABLED = False
MOTION_MIN_AREA_RATIO = 0.003
RACE_TEMPLATE_CHECK_EVERY_N_FRAMES = max(1, int(os.getenv('CART_RIDER_RACE_EVERY_N', '3')))
RACE_START_THRESHOLD = float(os.getenv('CART_RIDER_START_THRESHOLD', '0.62'))
RACE_GOAL_THRESHOLD = float(os.getenv('CART_RIDER_GOAL_THRESHOLD', '0.62'))
RACE_START_MIN_FRAME_RATIO = float(os.getenv('CART_RIDER_START_MIN_FRAME_RATIO', '0.10'))
RACE_GOAL_MIN_FRAME_RATIO = float(os.getenv('CART_RIDER_GOAL_MIN_FRAME_RATIO', '0.45'))
RACE_EDGE_MIN_PIXELS = int(os.getenv('CART_RIDER_RACE_EDGE_MIN_PIXELS', '60'))
RACE_START_WHITE_MIN_RATIO = float(os.getenv('CART_RIDER_START_WHITE_MIN_RATIO', '0.020'))
RACE_START_CONFIRM_FRAMES = max(1, int(os.getenv('CART_RIDER_START_CONFIRM_FRAMES', '2')))
RACE_GOAL_WHITE_MIN_RATIO = float(os.getenv('CART_RIDER_GOAL_WHITE_MIN_RATIO', '0.060'))
RACE_GOAL_CONFIRM_FRAMES = max(1, int(os.getenv('CART_RIDER_GOAL_CONFIRM_FRAMES', '3')))
RACE_GOAL_RED_MIN_RATIO = float(os.getenv('CART_RIDER_GOAL_RED_MIN_RATIO', '0.45'))
RACE_SCALES_TEXT = os.getenv('CART_RIDER_RACE_SCALES', '0.1,0.15,0.2,0.25,0.35,0.5,0.7,0.9,1.1,1.35,1.6,2.0')
RACE_RESULT_DELAY_SEC = float(os.getenv('CART_RIDER_RESULT_DELAY_SEC', '3.0'))


def read_float_list_env(text):
    values = []
    for item in text.split(','):
        item = item.strip()
        if not item:
            continue
        try:
            value = float(item)
        except ValueError:
            continue
        if value > 0:
            values.append(value)
    return values or [1.0]


def read_bool_env(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'y', 'on')

