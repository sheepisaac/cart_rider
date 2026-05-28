#!/usr/bin/env python3
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


HOST = '0.0.0.0'
PORT = 8080
ROVER_IMAGE = Path(__file__).resolve().parent / 'Rover.png'
COPYRIGHT_TEXT = '(c) Sungkyunkwan University (SKKU). All rights reserved.'


class TitleState:
    def __init__(self):
        self.done = threading.Event()
        self.start_requested = False
        self.streaming_option = None

    def start(self, streaming_option):
        self.streaming_option = streaming_option
        self.start_requested = True
        self.done.set()

    def cancel(self):
        self.start_requested = False
        self.done.set()


class TitleHandler(BaseHTTPRequestHandler):
    state = None
    initial_page = 'title'

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ('/', '/index.html'):
            self.send_html()
            return
        if path == '/Rover.png':
            self.send_rover_image()
            return
        self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == '/start':
            length = int(self.headers.get('Content-Length', '0') or 0)
            streaming_option = self.rfile.read(length).decode('utf-8', errors='ignore').strip()
            if streaming_option not in ('1', '2', '3'):
                self.send_text('invalid option', status=400)
                return
            self.state.start(streaming_option)
            self.send_text('starting')
            return
        if path == '/cancel':
            self.state.cancel()
            self.send_text('cancelled')
            return
        self.send_error(404)

    def send_html(self):
        body = make_title_html(type(self).initial_page).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.end_headers()
        self.wfile.write(body)

    def send_rover_image(self):
        if not ROVER_IMAGE.exists():
            self.send_error(404)
            return
        data = ROVER_IMAGE.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', 'image/png')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(data)

    def send_text(self, text, status=200):
        data = text.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        return


def make_title_html(initial_page='title'):
    return f'''<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cart Rider!</title>
<style>
  * {{ box-sizing: border-box; }}
  html, body {{
    margin: 0;
    width: 100%;
    height: 100%;
    background: #f4f4f4;
    color: #000;
    font-family: Arial, Helvetica, sans-serif;
  }}
  body {{
    display: grid;
    place-items: center;
  }}
  .window {{
    width: min(1280px, calc(100vw - 18px));
    height: min(760px, calc(100vh - 18px));
    min-height: 560px;
    border: 2px solid #000;
    background: #fff;
    display: grid;
    grid-template-rows: 38px 1fr;
  }}
  .bar {{
    border-bottom: 2px solid #000;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-left: 16px;
    font-size: 27px;
    line-height: 1;
  }}
  .buttons {{
    display: flex;
    gap: 5px;
    padding-right: 5px;
  }}
  .button {{
    width: 30px;
    height: 30px;
    border: 2px solid #000;
    position: relative;
  }}
  .min::after {{
    content: '';
    position: absolute;
    left: 6px;
    right: 6px;
    bottom: 8px;
    border-bottom: 2px solid #000;
  }}
  .max::after {{
    content: '';
    position: absolute;
    inset: 7px;
    border: 2px solid #000;
  }}
  .close::before, .close::after {{
    content: '';
    position: absolute;
    left: 7px;
    right: 7px;
    top: 13px;
    border-bottom: 2px solid #000;
  }}
  .close::before {{ transform: rotate(45deg); }}
  .close::after {{ transform: rotate(-45deg); }}
  .screen {{
    position: relative;
    height: 100%;
    overflow: hidden;
  }}
  .page {{
    position: absolute;
    inset: 0;
    display: none;
    text-align: center;
    padding: 44px 24px 20px;
  }}
  .page.active {{ display: block; }}
  h1 {{
    margin: 10px 0 56px;
    font-size: clamp(54px, 6vw, 74px);
    font-weight: 400;
    line-height: 1.05;
  }}
  .rover-title {{
    display: block;
    width: min(380px, 55vw);
    max-height: 320px;
    object-fit: contain;
    margin: 0 auto 34px;
  }}
  .rover-help {{
    display: block;
    width: min(360px, 50vw);
    max-height: 320px;
    object-fit: contain;
    margin: 30px auto 26px;
  }}
  .prompt {{
    font-size: clamp(34px, 4vw, 44px);
    line-height: 1.1;
    margin: 0;
  }}
  .controls {{
    width: min(620px, 92vw);
    margin: 0 auto 18px;
    display: grid;
    grid-template-columns: 1fr 1fr;
    column-gap: 72px;
    text-align: left;
    font-size: clamp(28px, 3vw, 38px);
    line-height: 1.15;
  }}
  .controls p {{ margin: 0 0 4px; }}
  .option-title {{
    margin: 78px 0 46px;
    font-size: clamp(32px, 3.6vw, 44px);
    font-weight: 400;
    line-height: 1.2;
  }}
  .options {{
    width: min(900px, 92vw);
    margin: 0 auto 42px;
    text-align: left;
    font-size: clamp(25px, 2.8vw, 36px);
    line-height: 1.35;
  }}
  .option-input {{
    display: inline-flex;
    align-items: center;
    gap: 14px;
    font-size: clamp(28px, 3vw, 38px);
  }}
  .option-input input {{
    width: 82px;
    height: 54px;
    border: 2px solid #000;
    font: inherit;
    text-align: center;
    outline: none;
  }}
  .error {{
    height: 30px;
    margin-top: 18px;
    color: #b00020;
    font-size: 22px;
  }}
  .footer {{
    position: absolute;
    left: 0;
    right: 0;
    bottom: 13px;
    text-align: center;
    font-size: 17px;
  }}
  .starting {{
    display: none;
    position: absolute;
    inset: 0;
    background: #fff;
    place-items: center;
    font-size: clamp(34px, 4vw, 46px);
  }}
  .starting.active {{ display: grid; }}
  @media (max-height: 680px) {{
    .page {{ padding-top: 26px; }}
    h1 {{ margin-bottom: 28px; }}
    .rover-title {{ width: min(320px, 48vw); margin-bottom: 24px; }}
    .rover-help {{ width: min(300px, 46vw); margin: 12px auto 18px; }}
    .controls {{ font-size: 28px; margin-bottom: 12px; }}
  }}
</style>
</head>
<body>
  <main class="window">
    <div class="bar">
      <span>Cart Rider!</span>
      <div class="buttons" aria-hidden="true">
        <span class="button min"></span>
        <span class="button max"></span>
        <span class="button close"></span>
      </div>
    </div>
    <section class="screen">
      <div id="page-title" class="page active">
        <h1>Cart Rider!</h1>
        <img class="rover-title" src="/Rover.png" alt="Cart Rider rover">
        <p class="prompt">Press Enter to proceed</p>
        <div class="footer">{COPYRIGHT_TEXT}</div>
      </div>
      <div id="page-help" class="page">
        <img class="rover-help" src="/Rover.png" alt="Cart Rider rover">
        <div class="controls">
          <div>
            <p>w: go forward</p>
            <p>a: left forward</p>
            <p>d: right forward</p>
            <p>b: BOOST!</p>
          </div>
          <div>
            <p>s: go backward</p>
            <p>z: left backward</p>
            <p>c: right backward</p>
            <p>q: quit game</p>
          </div>
        </div>
        <p class="prompt">Press Enter to play</p>
        <div class="footer">{COPYRIGHT_TEXT}</div>
      </div>
      <div id="page-option" class="page">
        <h2 class="option-title">Choose the camera streaming option and press enter</h2>
        <div class="options">
          <p>1: only streaming</p>
          <p>2: opencv-only detection streaming</p>
          <p>3: object detection streaming w/ YOLO</p>
        </div>
        <label class="option-input">
          <span>Input:</span>
          <input id="stream-option" maxlength="1" inputmode="numeric" autocomplete="off">
        </label>
        <div id="option-error" class="error"></div>
        <div class="footer">{COPYRIGHT_TEXT}</div>
      </div>
      <div id="starting" class="starting">Starting stream...</div>
    </section>
  </main>
<script>
  let page = 0;
  let starting = false;

  async function post(path) {{
    try {{ await fetch(path, {{ method: 'POST', cache: 'no-store' }}); }} catch (error) {{}}
  }}

  function showTitle() {{
    document.getElementById('page-help').classList.remove('active');
    document.getElementById('page-option').classList.remove('active');
    document.getElementById('page-title').classList.add('active');
    page = 0;
  }}

  function showHelp() {{
    document.getElementById('page-title').classList.remove('active');
    document.getElementById('page-option').classList.remove('active');
    document.getElementById('page-help').classList.add('active');
    page = 1;
  }}

  function showOptions() {{
    document.getElementById('page-title').classList.remove('active');
    document.getElementById('page-help').classList.remove('active');
    document.getElementById('page-option').classList.add('active');
    page = 2;
    setTimeout(() => document.getElementById('stream-option').focus(), 0);
  }}

  async function startGame() {{
    if (starting) return;
    const input = document.getElementById('stream-option');
    const option = input.value.trim();
    const error = document.getElementById('option-error');
    if (!['1', '2', '3'].includes(option)) {{
      error.textContent = 'Please input 1, 2, or 3.';
      input.value = '';
      input.focus();
      return;
    }}

    starting = true;
    document.getElementById('page-option').classList.remove('active');
    document.getElementById('starting').classList.add('active');
    await fetch('/start', {{ method: 'POST', body: option, cache: 'no-store' }});
    setTimeout(() => {{ window.location.href = '/'; }}, 1400);
  }}

  document.getElementById('stream-option').addEventListener('input', event => {{
    event.target.value = event.target.value.replace(/[^1-3]/g, '').slice(0, 1);
    document.getElementById('option-error').textContent = '';
  }});

  const initialPage = '{initial_page}';
  if (initialPage === 'help') showHelp();
  else if (initialPage === 'option') showOptions();

  document.addEventListener('keydown', async (event) => {{
    if (event.key === 'Backspace') {{
      event.preventDefault();
      if (page === 2) showHelp();
      else if (page === 1) showTitle();
      return;
    }}

    if (event.key === 'Enter') {{
      event.preventDefault();
      if (page === 0) showHelp();
      else if (page === 1) showOptions();
      else await startGame();
    }} else if (event.key === 'Escape' || (page !== 2 && event.key.toLowerCase() === 'q')) {{
      await post('/cancel');
      document.getElementById('starting').textContent = 'Cancelled';
      document.getElementById('starting').classList.add('active');
    }}
  }});
</script>
</body>
</html>'''


def get_local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(('8.8.8.8', 80))
            return sock.getsockname()[0]
    except OSError:
        return '127.0.0.1'


def show_title_sequence(initial_page='title'):
    state = TitleState()
    TitleHandler.state = state
    TitleHandler.initial_page = initial_page
    server = ThreadingHTTPServer((HOST, PORT), TitleHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    local_ip = get_local_ip()
    print(f'Open this URL in a browser: http://{local_ip}:{PORT}/')
    print('Press Enter twice, choose 1/2/3, then press Enter in the browser.')

    try:
        state.done.wait()
        return state.streaming_option if state.start_requested else None
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=1.0)


def main():
    streaming_option = show_title_sequence()
    if not streaming_option:
        return

    import main as cart_main
    cart_main.main(show_title=False, streaming_option=streaming_option)


if __name__ == '__main__':
    main()
