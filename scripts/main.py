#!/usr/bin/env python3
import os
import threading


class DriveStatus:
    def __init__(self):
        self.lock = threading.Lock()
        self.control_callback = None
        self.back_callback = None
        self.status = {
            'active_key': None,
            'speed': 0,
            'boost_active': False,
            'boost_cooldown_remaining': 0.0,
        }

    def update(self, status):
        with self.lock:
            self.status = dict(status)

    def snapshot(self):
        with self.lock:
            return dict(self.status)


def start_camera_stream(drive_status, streaming_option):
    from http.server import ThreadingHTTPServer

    import rclpy

    game_mode = streaming_option == 'race'
    if game_mode:
        os.environ.setdefault('CART_RIDER_STREAM_FPS', '6')
        os.environ.setdefault('CART_RIDER_JPEG_QUALITY', '35')
        os.environ.setdefault('CART_RIDER_YOLO_IMGSZ', '160')
        os.environ.setdefault('CART_RIDER_YOLO_EVERY_N', '30')
        os.environ.setdefault('CART_RIDER_YOLO_TORCH_THREADS', '1')
        os.environ.setdefault('CART_RIDER_YOLO_MAX_DET', '4')
        os.environ.setdefault('CART_RIDER_RACE_EVERY_N', '5')
    if streaming_option in ('3', 'race'):
        try:
            import camera_stream_yolo as camera_stream
            detection_enabled = True
        except ImportError:
            import camera_stream
            detection_enabled = False
            game_mode = False
            print('YOLO streaming is not ready yet. Falling back to only streaming.')
    else:
        import camera_stream
        detection_enabled = streaming_option == '2'

    width = 0
    height = 0

    rclpy.init()
    deblur_enabled = streaming_option not in ('3', 'race') and os.getenv('CART_RIDER_DEBLUR', '').strip().lower() in (
        '1',
        'true',
        'yes',
        'y',
        'on',
    )
    streamer = camera_stream.VideoStreamer(
        width,
        height,
        detection_enabled,
        drive_status_provider=drive_status.snapshot,
        deblur_enabled=deblur_enabled,
        game_mode=game_mode,
    )
    camera_stream.MJPEGHandler.streamer = streamer
    camera_stream.MJPEGHandler.control_callback = drive_status.control_callback
    camera_stream.MJPEGHandler.back_callback = drive_status.back_callback
    camera_stream.ControlHandler.control_callback = drive_status.control_callback
    camera_stream.ControlHandler.back_callback = drive_status.back_callback
    server = ThreadingHTTPServer((camera_stream.HOST, camera_stream.PORT), camera_stream.MJPEGHandler)
    control_server = ThreadingHTTPServer((camera_stream.HOST, camera_stream.CONTROL_PORT), camera_stream.ControlHandler)

    spin_thread = threading.Thread(target=camera_stream.spin_node, args=(streamer,), daemon=True)
    spin_thread.start()
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    control_server_thread = threading.Thread(target=control_server.serve_forever, daemon=True)
    control_server_thread.start()

    return camera_stream, streamer, server, control_server, spin_thread, server_thread, control_server_thread


def stop_camera_stream(streamer, server, control_server, spin_thread, server_thread, control_server_thread):
    import rclpy

    control_server.shutdown()
    control_server.server_close()
    server.shutdown()
    server.server_close()
    streamer.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()
    spin_thread.join(timeout=1.0)
    server_thread.join(timeout=1.0)
    control_server_thread.join(timeout=1.0)


def run_stream(ctrl_cart, streaming_option):
    back_event = threading.Event()
    drive_status = DriveStatus()

    def request_back():
        back_event.set()
        ctrl_cart.exit_event.set()

    ctrl_cart.reset_web_control_state()
    drive_status.control_callback = ctrl_cart.handle_web_key
    drive_status.back_callback = request_back
    ctrl_cart.set_status_callback(drive_status.update)
    camera_stream, streamer, server, control_server, spin_thread, server_thread, control_server_thread = start_camera_stream(drive_status, streaming_option)
    executor_thread = threading.Thread(target=ctrl_cart.execute_command)
    input_thread = threading.Thread(target=ctrl_cart.refresh_web_control_state)

    try:
        import title
        display_host = title.get_local_ip()
    except Exception:
        display_host = '127.0.0.1'
    print(f'Open this URL in a browser: http://{display_host}:{camera_stream.PORT}/')
    print(f'Control server: http://{display_host}:{camera_stream.CONTROL_PORT}/')
    print(f'Streaming option: {streaming_option}')
    print('Control keys in browser: w/a/s/d/z/c, boost: b, quit: q, backspace: previous page')

    try:
        executor_thread.start()
        input_thread.start()
        ctrl_cart.exit_event.wait()
    except KeyboardInterrupt:
        ctrl_cart.exit_event.set()
    finally:
        ctrl_cart.exit_event.set()
        executor_thread.join()
        input_thread.join()
        ctrl_cart.send_stop_command()
        stop_camera_stream(streamer, server, control_server, spin_thread, server_thread, control_server_thread)

    return back_event.is_set()


def main(show_title=True, streaming_option='2'):
    import title

    initial_page = 'title'
    if not show_title:
        initial_page = 'option'

    import ctrl_cart

    try:
        while True:
            if show_title:
                selected_option = title.show_title_sequence(initial_page=initial_page)
                if not selected_option:
                    break
                streaming_option = selected_option

            went_back = run_stream(ctrl_cart, streaming_option)
            if not went_back:
                break

            show_title = True
            initial_page = 'option'
    finally:
        ctrl_cart.uart.close()

    print('Program terminated.')


if __name__ == '__main__':
    main()
