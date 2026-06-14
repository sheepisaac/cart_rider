import serial
import threading
import time

uart = serial.Serial('/dev/ttyAMA0', baudrate=1000000, timeout=0, write_timeout=0.05)

STOP_COMMAND = '{"T":0}'
ACTIVE_SEND_INTERVAL = 0.04
IDLE_SEND_INTERVAL = 0.2
INPUT_POLL_INTERVAL = 0.02
KEY_HOLD_TIMEOUT = 1.00
BASE_SPEED = 150
#BOOST_MULTIPLIER = 1.6
BOOST_DURATION = 5.0
BOOST_COOLDOWN = 30.0
BOOST_KEY = 'b'

current_command = STOP_COMMAND
command_changed = threading.Event()
command_lock = threading.Lock()
exit_event = threading.Event()
status_callback = None
web_control_lock = threading.Lock()
web_active_key = None
web_last_motion_input_time = 0
web_boost_until = 0
web_next_boost_available_time = 0

key_directions = {
    'w': (1, 1),
    'a': (0, 1),
    'd': (1, 0),
    's': (-1, -1),
    'z': (0, -1),
    'c': (-1, 0),
}


def get_current_speed(boost_until):
    if time.monotonic() < boost_until:
        return 250
        #return BASE_SPEED * BOOST_MULTIPLIER

    return BASE_SPEED


def set_status_callback(callback):
    global status_callback
    status_callback = callback


def publish_status(active_key, speed, boost_active, boost_cooldown_remaining):
    if status_callback is None:
        return

    displayed_speed = speed if active_key else 0
    status_callback({
        'active_key': active_key,
        'speed': displayed_speed,
        'boost_active': boost_active,
        'boost_cooldown_remaining': boost_cooldown_remaining,
    })


def generate_command(active_key, speed):
    if active_key not in key_directions:
        return STOP_COMMAND

    left_direction, right_direction = key_directions[active_key]
    left_speed = left_direction * speed
    right_speed = right_direction * speed

    return f'{{"T":1,"L":{left_speed},"R":{right_speed}}}'


def set_current_command(next_command):
    global current_command
    with command_lock:
        if current_command != next_command:
            current_command = next_command
            command_changed.set()


def update_control_command(active_key, boost_until, next_boost_available_time):
    now = time.monotonic()
    speed = get_current_speed(boost_until)
    boost_active = now < boost_until
    boost_cooldown_remaining = max(0.0, next_boost_available_time - now)
    next_command = generate_command(active_key, speed)
    publish_status(active_key, speed, boost_active, boost_cooldown_remaining)
    set_current_command(next_command)


def handle_web_key(pressed_key):
    global web_active_key, web_last_motion_input_time, web_boost_until, web_next_boost_available_time

    pressed_key = (pressed_key or '').lower()
    now = time.monotonic()

    with web_control_lock:
        if pressed_key == 'q':
            exit_event.set()
            return

        if pressed_key == 'x':
            web_active_key = None
            update_control_command(web_active_key, web_boost_until, web_next_boost_available_time)
            return

        if pressed_key == BOOST_KEY:
            if now >= web_next_boost_available_time:
                web_boost_until = now + BOOST_DURATION
                web_next_boost_available_time = now + BOOST_COOLDOWN
            if web_active_key:
                web_last_motion_input_time = now
        elif pressed_key in key_directions:
            web_active_key = pressed_key
            web_last_motion_input_time = now

        update_control_command(web_active_key, web_boost_until, web_next_boost_available_time)


def refresh_web_control_state():
    global web_active_key

    while not exit_event.is_set():
        with web_control_lock:
            now = time.monotonic()
            if web_active_key and now - web_last_motion_input_time > KEY_HOLD_TIMEOUT:
                web_active_key = None
            update_control_command(web_active_key, web_boost_until, web_next_boost_available_time)

        time.sleep(INPUT_POLL_INTERVAL)


def reset_web_control_state():
    global current_command, web_active_key, web_last_motion_input_time, web_boost_until, web_next_boost_available_time

    exit_event.clear()
    command_changed.clear()
    with command_lock:
        current_command = STOP_COMMAND

    with web_control_lock:
        web_active_key = None
        web_last_motion_input_time = 0
        web_boost_until = 0
        web_next_boost_available_time = 0
    update_control_command(None, 0, 0)


def send_stop_command():
    uart.write(STOP_COMMAND.encode())
    uart.flush()


def execute_command():
    last_sent_command = None
    next_send_time = 0

    while not exit_event.is_set():
        now = time.monotonic()
        with command_lock:
            command = current_command

        should_send = command_changed.is_set() or now >= next_send_time
        if should_send:
            try:
                uart.write(command.encode())
            except serial.SerialTimeoutException:
                pass

            command_changed.clear()
            last_sent_command = command
            interval = IDLE_SEND_INTERVAL if command == STOP_COMMAND else ACTIVE_SEND_INTERVAL
            next_send_time = now + interval

        wait_time = max(0.0, min(next_send_time - time.monotonic(), INPUT_POLL_INTERVAL))
        exit_event.wait(wait_time)


if __name__ == '__main__':
    executor_thread = threading.Thread(target=execute_command)

    try:
        executor_thread.start()

        refresh_web_control_state()
    except KeyboardInterrupt:
        exit_event.set()
    finally:
        exit_event.set()
        executor_thread.join()

        send_stop_command()
        uart.close()

    print('Program terminated.')
