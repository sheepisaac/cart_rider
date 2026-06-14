#!/usr/bin/env python3
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


HOST = '0.0.0.0'
PORT = 8080
ASSET_DIR = Path(__file__).resolve().parent.parent / 'figure'
ROVER_IMAGE = ASSET_DIR / 'Rover.png'
BACKGROUND_IMAGE = ASSET_DIR / 'background.png'
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
            self.send_image(ROVER_IMAGE)
            return
        if path == '/background.png':
            self.send_image(BACKGROUND_IMAGE)
            return
        self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == '/start':
            length = int(self.headers.get('Content-Length', '0') or 0)
            streaming_option = self.rfile.read(length).decode('utf-8', errors='ignore').strip()
            if streaming_option not in ('race', '1', '2', '3'):
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

    def send_image(self, image_path):
        if not image_path.exists():
            self.send_error(404)
            return
        data = image_path.read_bytes()
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
    background: #071d50;
    color: #071b4a;
    font-family: Arial, Helvetica, sans-serif;
  }}
  body {{
    display: grid;
    place-items: center;
  }}
  .window {{
    width: min(1634px, 100vw);
    height: min(917px, 100vh);
    min-height: min(560px, 100vh);
    border: 0;
    background: #fff;
    display: grid;
    grid-template-rows: 1fr;
    box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.3);
  }}
  .bar {{
    display: none;
    border-bottom: 2px solid #000;
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
  #page-title {{
    padding: 0;
    background: #fff url('/background.png') center / cover no-repeat;
  }}
  .title-stage {{
    position: relative;
    width: 100%;
    height: 100%;
    min-height: 560px;
    overflow: hidden;
  }}
  .brand-logo {{
    position: absolute;
    top: 4.1%;
    left: 50%;
    width: min(910px, 72vw);
    transform: translateX(-50%) skewX(-8deg);
    text-align: center;
    font-family: Impact, Haettenschweiler, 'Arial Black', sans-serif;
    font-weight: 900;
    font-style: italic;
    line-height: 0.78;
    letter-spacing: 0;
    filter: drop-shadow(0 5px 0 #0845ba) drop-shadow(0 0 13px rgba(0, 202, 255, 0.65));
  }}
  .brand-logo .cart,
  .brand-logo .rider {{
    display: block;
    -webkit-text-stroke: 3px #0743b7;
    text-shadow:
      4px 4px 0 #07227a,
      0 0 8px rgba(0, 205, 255, 0.9);
  }}
  .brand-logo .cart {{
    color: #0364c9;
    font-size: clamp(88px, 10.5vw, 164px);
  }}
  .brand-logo .rider {{
    color: #ffc409;
    font-size: clamp(92px, 11vw, 176px);
    -webkit-text-stroke-color: #ec7d00;
  }}
  .title-subtitle {{
    position: absolute;
    top: 39.3%;
    left: 50%;
    width: min(900px, 82vw);
    transform: translateX(-50%) skewX(-8deg);
    margin: 0;
    color: #062a7c;
    font-family: Impact, Haettenschweiler, 'Arial Black', sans-serif;
    font-size: clamp(18px, 2.2vw, 36px);
    font-style: italic;
    letter-spacing: 0;
    white-space: nowrap;
    text-shadow: 0 1px 0 #fff;
  }}
  .title-subtitle .accent {{
    color: #f5b600;
    font-size: 1.55em;
  }}
  #page-title .rover-title {{
    position: absolute;
    left: 50%;
    bottom: 20.0%;
    width: min(520px, 38vw);
    max-height: none;
    transform: translateX(-50%);
    margin: 0;
    filter: drop-shadow(0 26px 22px rgba(1, 18, 50, 0.32));
  }}
  .title-prompt {{
    position: absolute;
    left: 50%;
    bottom: 8.4%;
    width: min(770px, 72vw);
    height: clamp(68px, 8vw, 96px);
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: clamp(24px, 4vw, 72px);
    margin: 0;
    color: #fff;
    white-space: nowrap;
    overflow: hidden;
    background: linear-gradient(180deg, #0e79d8 0%, #053a9e 50%, #05226f 100%);
    border: 3px solid #16d9ff;
    clip-path: polygon(8% 0, 92% 0, 100% 50%, 92% 100%, 8% 100%, 0 50%);
    box-shadow:
      0 0 0 6px rgba(0, 118, 214, 0.45),
      inset 0 0 18px rgba(0, 229, 255, 0.7),
      0 0 20px rgba(0, 192, 255, 0.62);
    font-family: Impact, Haettenschweiler, 'Arial Black', sans-serif;
    font-size: clamp(20px, 2.65vw, 42px);
    font-style: italic;
    letter-spacing: 0;
    text-transform: uppercase;
    text-shadow: 2px 3px 0 #07215f;
  }}
  .title-prompt::before,
  .title-prompt::after {{
    content: '>>>';
    color: #91d9ff;
    font-size: 0.9em;
    opacity: 0.9;
    flex: 0 0 auto;
  }}
  .title-prompt .enter {{
    color: #ffc400;
    font-size: 1.32em;
    margin: 0 0.12em;
  }}
  #page-title .footer {{
    bottom: 2.3%;
    color: #092c86;
    font-size: clamp(14px, 1.35vw, 24px);
  }}
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
  #page-help {{
    padding: 0;
    background: #fff url('/background.png') center / cover no-repeat;
  }}
  .help-stage {{
    position: relative;
    width: 100%;
    height: 100%;
    min-height: 560px;
    overflow: hidden;
  }}
  .help-stage::before {{
    content: '';
    position: absolute;
    left: 50%;
    top: clamp(285px, 42vh, 420px);
    width: min(430px, 31vw, 42vh);
    height: min(54px, 4.2vw, 5.6vh);
    transform: translateX(-50%);
    background: radial-gradient(ellipse, rgba(0, 20, 55, 0.34) 0%, rgba(0, 20, 55, 0.18) 42%, transparent 72%);
    filter: blur(3px);
    z-index: 1;
    pointer-events: none;
  }}
  .rover-help {{
    position: absolute;
    left: 50%;
    top: clamp(36px, 7vh, 78px);
    width: min(500px, 32vw, 42vh);
    max-height: none;
    object-fit: contain;
    transform: translateX(-50%);
    margin: 0;
    z-index: 2;
    filter: drop-shadow(0 16px 16px rgba(1, 18, 50, 0.24));
  }}
  .controls {{
    position: absolute;
    left: 50%;
    bottom: 19.2%;
    width: min(990px, 70vw);
    transform: translateX(-50%);
    display: grid;
    grid-template-columns: 1fr 1fr;
    column-gap: clamp(36px, 4vw, 70px);
    margin: 0;
    text-align: left;
    color: #fff;
    font-family: Impact, Haettenschweiler, 'Arial Black', sans-serif;
    font-size: clamp(18px, 1.85vw, 31px);
    font-style: italic;
    line-height: 1.1;
    letter-spacing: 0;
    text-transform: uppercase;
    text-shadow: 2px 3px 0 #061e63;
    z-index: 4;
  }}
  .control-panel {{
    position: relative;
    min-height: clamp(160px, 16vw, 230px);
    padding: clamp(22px, 2.2vw, 34px) clamp(36px, 3.2vw, 54px);
    background:
      radial-gradient(circle at 14% 78%, rgba(3, 159, 255, 0.26) 0 15%, transparent 16%),
      linear-gradient(180deg, rgba(10, 93, 186, 0.96), rgba(3, 24, 88, 0.98));
    border: 3px solid #13d7ff;
    clip-path: polygon(8% 0, 92% 0, 100% 13%, 100% 87%, 92% 100%, 8% 100%, 0 87%, 0 13%);
    box-shadow:
      0 0 0 5px rgba(0, 116, 219, 0.38),
      inset 0 0 20px rgba(0, 229, 255, 0.62),
      0 0 24px rgba(0, 184, 255, 0.55);
  }}
  .control-row {{
    display: grid;
    grid-template-columns: clamp(46px, 4vw, 64px) auto 1fr;
    align-items: center;
    gap: clamp(10px, 1.2vw, 18px);
    margin: 0 0 clamp(9px, 0.9vw, 14px);
    min-width: 0;
  }}
  .control-row:last-child {{ margin-bottom: 0; }}
  .keycap {{
    display: inline-grid;
    place-items: center;
    width: clamp(42px, 3.8vw, 58px);
    height: clamp(42px, 3.8vw, 58px);
    color: #ffc400;
    background: linear-gradient(180deg, #176fc9, #073b9a);
    border: 2px solid #22d7ff;
    border-radius: 7px;
    box-shadow:
      inset 0 0 10px rgba(0, 225, 255, 0.72),
      0 0 11px rgba(0, 201, 255, 0.72);
    text-shadow: 2px 2px 0 #08256d;
  }}
  .colon {{
    color: #ffffff;
  }}
  .control-action {{
    min-width: 0;
    white-space: nowrap;
  }}
  .control-action.boost {{
    color: #ffc400;
  }}
  #page-help .prompt {{ display: none; }}
  .help-prompt {{
    position: absolute;
    left: 50%;
    bottom: 6.2%;
    width: min(770px, 64vw);
    height: clamp(64px, 7.2vw, 88px);
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: clamp(24px, 4vw, 72px);
    margin: 0;
    color: #fff;
    white-space: nowrap;
    overflow: hidden;
    background: linear-gradient(180deg, #0e79d8 0%, #053a9e 50%, #05226f 100%);
    border: 3px solid #16d9ff;
    clip-path: polygon(8% 0, 92% 0, 100% 50%, 92% 100%, 8% 100%, 0 50%);
    box-shadow:
      0 0 0 6px rgba(0, 118, 214, 0.45),
      inset 0 0 18px rgba(0, 229, 255, 0.7),
      0 0 20px rgba(0, 192, 255, 0.62);
    font-family: Impact, Haettenschweiler, 'Arial Black', sans-serif;
    font-size: clamp(21px, 2.85vw, 44px);
    font-style: italic;
    letter-spacing: 0;
    text-transform: uppercase;
    text-shadow: 2px 3px 0 #07215f;
  }}
  .help-prompt::before,
  .help-prompt::after {{
    content: '>>>';
    color: #91d9ff;
    font-size: 0.9em;
    opacity: 0.9;
    flex: 0 0 auto;
  }}
  .help-prompt .enter {{
    color: #ffc400;
    font-size: 1.32em;
    margin: 0 0.12em;
  }}
  #page-help .footer {{
    bottom: 2.0%;
    color: #092c86;
    font-size: clamp(14px, 1.25vw, 23px);
  }}
  #page-mode {{
    padding: 0;
    background: #fff url('/background.png') center / cover no-repeat;
  }}
  .mode-stage {{
    position: relative;
    width: 100%;
    height: 100%;
    min-height: 560px;
    overflow: hidden;
  }}
  .mode-logo {{
    position: absolute;
    top: 2.0%;
    left: 50%;
    width: min(600px, 56vw);
    transform: translateX(-50%) skewX(-8deg);
    text-align: center;
    font-family: Impact, Haettenschweiler, 'Arial Black', sans-serif;
    font-weight: 900;
    font-style: italic;
    line-height: 0.78;
    letter-spacing: 0;
    filter: drop-shadow(0 4px 0 #0845ba) drop-shadow(0 0 11px rgba(0, 202, 255, 0.68));
  }}
  .mode-logo .cart,
  .mode-logo .rider {{
    display: block;
    -webkit-text-stroke: 2px #0743b7;
    text-shadow: 3px 3px 0 #07227a;
  }}
  .mode-logo .cart {{
    color: #0364c9;
    font-size: clamp(62px, 7.4vw, 110px);
  }}
  .mode-logo .rider {{
    color: #ffc409;
    font-size: clamp(66px, 7.8vw, 118px);
    -webkit-text-stroke-color: #ec7d00;
  }}
  .mode-subtitle {{
    position: absolute;
    top: 26.4%;
    left: 50%;
    width: min(650px, 70vw);
    transform: translateX(-50%) skewX(-8deg);
    margin: 0;
    color: #062a7c;
    font-family: Impact, Haettenschweiler, 'Arial Black', sans-serif;
    font-size: clamp(14px, 1.5vw, 25px);
    font-style: italic;
    letter-spacing: 0;
    white-space: nowrap;
    text-shadow: 0 1px 0 #fff;
  }}
  .mode-subtitle .accent {{
    color: #f5b600;
    font-size: 1.45em;
  }}
  .rover-mode {{
    position: absolute;
    left: 50%;
    top: 32%;
    width: min(170px, 14vw, 18vh);
    transform: translateX(-50%);
    filter: drop-shadow(0 12px 13px rgba(1, 18, 50, 0.27));
  }}
  .mode-menu {{
    position: absolute;
    left: 50%;
    bottom: 16.0%;
    width: min(660px, 58vw);
    transform: translateX(-50%);
    display: grid;
    gap: clamp(8px, 1.1vh, 14px);
    color: #fff;
    font-family: Impact, Haettenschweiler, 'Arial Black', sans-serif;
    font-style: italic;
    text-transform: uppercase;
    letter-spacing: 0;
    text-shadow: 2px 3px 0 #061e63;
  }}
  .mode-banner,
  .mode-choice,
  .mode-input-row {{
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0;
    background: linear-gradient(180deg, #0f73cf, #05246f);
    border: 3px solid #18d7ff;
    box-shadow:
      0 0 0 5px rgba(0, 116, 219, 0.34),
      inset 0 0 18px rgba(0, 229, 255, 0.58),
      0 0 20px rgba(0, 184, 255, 0.42);
  }}
  .mode-banner {{
    height: clamp(42px, 5.5vh, 62px);
    clip-path: polygon(8% 0, 92% 0, 100% 50%, 92% 100%, 8% 100%, 0 50%);
    font-size: clamp(18px, 2vw, 32px);
    white-space: nowrap;
  }}
  .mode-banner::before,
  .mode-banner::after {{
    content: '<<<';
    position: absolute;
    color: #87dcff;
    font-size: 0.82em;
  }}
  .mode-banner::before {{ left: 6%; }}
  .mode-banner::after {{ right: 6%; content: '>>>'; }}
  .mode-choice {{
    height: clamp(40px, 5.1vh, 58px);
    justify-content: flex-start;
    padding: 0 clamp(48px, 6vw, 76px);
    clip-path: polygon(6% 0, 94% 0, 100% 50%, 94% 100%, 6% 100%, 0 50%);
    font-size: clamp(18px, 1.9vw, 30px);
    white-space: nowrap;
  }}
  .mode-choice::after {{
    content: '>>>';
    position: absolute;
    right: 7%;
    color: #ffd31a;
    font-size: 0.9em;
  }}
  .mode-number {{
    display: inline-grid;
    place-items: center;
    width: clamp(38px, 4vw, 52px);
    height: clamp(32px, 3.8vw, 46px);
    margin-right: clamp(18px, 2vw, 30px);
    color: #ffc400;
    background: linear-gradient(180deg, #176fc9, #073b9a);
    border: 2px solid #22d7ff;
    border-radius: 6px;
    box-shadow: inset 0 0 10px rgba(0, 225, 255, 0.72), 0 0 11px rgba(0, 201, 255, 0.72);
  }}
  .mode-colon {{ margin-right: clamp(16px, 1.6vw, 24px); }}
  .mode-input-row {{
    justify-self: center;
    height: clamp(36px, 4.8vh, 52px);
    min-width: min(280px, 34vw);
    gap: 10px;
    padding: 0 20px;
    background: transparent;
    border: 0;
    box-shadow: none;
    font-size: clamp(18px, 1.8vw, 30px);
  }}
  .mode-input-row input {{
    width: clamp(84px, 10vw, 130px);
    height: clamp(32px, 4vh, 48px);
    border: 3px solid #17d9ff;
    border-radius: 0;
    color: #fff;
    background: rgba(2, 32, 101, 0.88);
    box-shadow: inset 0 0 14px rgba(0, 229, 255, 0.7), 0 0 16px rgba(0, 184, 255, 0.45);
    font: inherit;
    text-align: center;
    outline: none;
  }}
  .mode-prompt {{
    position: absolute;
    left: 50%;
    bottom: 5.7%;
    width: min(760px, 66vw);
    height: clamp(58px, 6.8vw, 84px);
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: clamp(20px, 3.2vw, 56px);
    margin: 0;
    color: #fff;
    white-space: nowrap;
    overflow: hidden;
    background: linear-gradient(180deg, #0e79d8 0%, #053a9e 50%, #05226f 100%);
    border: 3px solid #16d9ff;
    clip-path: polygon(8% 0, 92% 0, 100% 50%, 92% 100%, 8% 100%, 0 50%);
    box-shadow: 0 0 0 6px rgba(0, 118, 214, 0.42), inset 0 0 18px rgba(0, 229, 255, 0.7), 0 0 20px rgba(0, 192, 255, 0.55);
    font-family: Impact, Haettenschweiler, 'Arial Black', sans-serif;
    font-size: clamp(20px, 2.75vw, 42px);
    font-style: italic;
    text-transform: uppercase;
    text-shadow: 2px 3px 0 #07215f;
  }}
  .mode-prompt::before,
  .mode-prompt::after {{
    content: '>>>';
    color: #91d9ff;
    font-size: 0.9em;
    flex: 0 0 auto;
  }}
  .mode-prompt .enter {{
    color: #ffc400;
    font-size: 1.32em;
  }}
  #page-mode .option-title,
  #page-mode .options,
  #page-mode .option-input {{ display: none; }}
  .option-title {{
    margin: 78px 0 46px;
    font-size: clamp(32px, 3.6vw, 44px);
    font-weight: 400;
    line-height: 1.2;
  }}
  #page-option {{
    padding: 0;
    background: #fff url('/background.png') center / cover no-repeat;
  }}
  .debug-stage {{
    position: relative;
    width: 100%;
    height: 100%;
    min-height: 560px;
    overflow: hidden;
  }}
  .debug-logo {{
    position: absolute;
    top: 2.0%;
    left: 50%;
    width: min(600px, 56vw);
    transform: translateX(-50%) skewX(-8deg);
    text-align: center;
    font-family: Impact, Haettenschweiler, 'Arial Black', sans-serif;
    font-weight: 900;
    font-style: italic;
    line-height: 0.78;
    letter-spacing: 0;
    filter: drop-shadow(0 4px 0 #0845ba) drop-shadow(0 0 11px rgba(0, 202, 255, 0.68));
  }}
  .debug-logo .cart,
  .debug-logo .rider {{
    display: block;
    -webkit-text-stroke: 2px #0743b7;
    text-shadow: 3px 3px 0 #07227a;
  }}
  .debug-logo .cart {{
    color: #0364c9;
    font-size: clamp(62px, 7.4vw, 110px);
  }}
  .debug-logo .rider {{
    color: #ffc409;
    font-size: clamp(66px, 7.8vw, 118px);
    -webkit-text-stroke-color: #ec7d00;
  }}
  .debug-subtitle {{
    position: absolute;
    top: 26.4%;
    left: 50%;
    width: min(650px, 70vw);
    transform: translateX(-50%) skewX(-8deg);
    margin: 0;
    color: #062a7c;
    font-family: Impact, Haettenschweiler, 'Arial Black', sans-serif;
    font-size: clamp(14px, 1.5vw, 25px);
    font-style: italic;
    letter-spacing: 0;
    white-space: nowrap;
    text-shadow: 0 1px 0 #fff;
  }}
  .debug-subtitle .accent {{
    color: #f5b600;
    font-size: 1.45em;
  }}
  .rover-debug {{
    position: absolute;
    left: 50%;
    top: 32%;
    width: min(170px, 14vw, 18vh);
    transform: translateX(-50%);
    filter: drop-shadow(0 12px 13px rgba(1, 18, 50, 0.27));
  }}
  .debug-menu {{
    position: absolute;
    left: 50%;
    bottom: 16.0%;
    width: min(720px, 66vw);
    transform: translateX(-50%);
    display: grid;
    gap: clamp(7px, 0.95vh, 12px);
    color: #fff;
    font-family: Impact, Haettenschweiler, 'Arial Black', sans-serif;
    font-style: italic;
    text-transform: uppercase;
    letter-spacing: 0;
    text-shadow: 2px 3px 0 #061e63;
  }}
  .debug-banner,
  .debug-choice,
  .debug-input-row {{
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0;
    background: linear-gradient(180deg, #0f73cf, #05246f);
    border: 3px solid #18d7ff;
    box-shadow: 0 0 0 5px rgba(0, 116, 219, 0.34), inset 0 0 18px rgba(0, 229, 255, 0.58), 0 0 20px rgba(0, 184, 255, 0.42);
  }}
  .debug-banner {{
    height: clamp(38px, 5vh, 56px);
    clip-path: polygon(8% 0, 92% 0, 100% 50%, 92% 100%, 8% 100%, 0 50%);
    font-size: clamp(16px, 1.65vw, 28px);
    white-space: nowrap;
  }}
  .debug-banner::before,
  .debug-banner::after {{
    content: '<<<';
    position: absolute;
    color: #87dcff;
    font-size: 0.82em;
  }}
  .debug-banner::before {{ left: 6%; }}
  .debug-banner::after {{ right: 6%; content: '>>>'; }}
  .debug-choice {{
    height: clamp(36px, 4.6vh, 52px);
    justify-content: flex-start;
    padding: 0 clamp(48px, 5.4vw, 76px);
    clip-path: polygon(6% 0, 94% 0, 100% 50%, 94% 100%, 6% 100%, 0 50%);
    font-size: clamp(15px, 1.55vw, 25px);
    white-space: nowrap;
  }}
  .debug-choice::after {{
    content: '>>>';
    position: absolute;
    right: 7%;
    color: #24e6ff;
    font-size: 0.9em;
  }}
  .debug-number {{
    display: inline-grid;
    place-items: center;
    width: clamp(34px, 3.4vw, 48px);
    height: clamp(30px, 3.4vw, 42px);
    margin-right: clamp(16px, 1.7vw, 26px);
    color: #ffc400;
    background: linear-gradient(180deg, #176fc9, #073b9a);
    border: 2px solid #22d7ff;
    border-radius: 6px;
    box-shadow: inset 0 0 10px rgba(0, 225, 255, 0.72), 0 0 11px rgba(0, 201, 255, 0.72);
  }}
  .debug-colon {{ margin-right: clamp(14px, 1.4vw, 22px); }}
  .debug-input-row {{
    justify-self: center;
    height: clamp(34px, 4.6vh, 50px);
    min-width: min(300px, 34vw);
    gap: 10px;
    padding: 0 20px;
    background: transparent;
    border: 0;
    box-shadow: none;
    font-size: clamp(18px, 1.75vw, 29px);
  }}
  .debug-input-row input {{
    width: clamp(96px, 11vw, 140px);
    height: clamp(32px, 4vh, 48px);
    border: 3px solid #17d9ff;
    color: #fff;
    background: rgba(2, 32, 101, 0.88);
    box-shadow: inset 0 0 14px rgba(0, 229, 255, 0.7), 0 0 16px rgba(0, 184, 255, 0.45);
    font: inherit;
    text-align: center;
    outline: none;
  }}
  .debug-prompt {{
    position: absolute;
    left: 50%;
    bottom: 5.7%;
    width: min(760px, 66vw);
    height: clamp(58px, 6.8vw, 84px);
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: clamp(20px, 3.2vw, 56px);
    margin: 0;
    color: #fff;
    white-space: nowrap;
    overflow: hidden;
    background: linear-gradient(180deg, #0e79d8 0%, #053a9e 50%, #05226f 100%);
    border: 3px solid #16d9ff;
    clip-path: polygon(8% 0, 92% 0, 100% 50%, 92% 100%, 8% 100%, 0 50%);
    box-shadow: 0 0 0 6px rgba(0, 118, 214, 0.42), inset 0 0 18px rgba(0, 229, 255, 0.7), 0 0 20px rgba(0, 192, 255, 0.55);
    font-family: Impact, Haettenschweiler, 'Arial Black', sans-serif;
    font-size: clamp(20px, 2.75vw, 42px);
    font-style: italic;
    text-transform: uppercase;
    text-shadow: 2px 3px 0 #07215f;
  }}
  .debug-prompt::before,
  .debug-prompt::after {{
    content: '>>>';
    color: #91d9ff;
    font-size: 0.9em;
    flex: 0 0 auto;
  }}
  .debug-prompt .enter {{
    color: #ffc400;
    font-size: 1.32em;
  }}
  #page-option .option-title,
  #page-option .options,
  #page-option .option-input {{ display: none; }}
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
    z-index: 100;
    background: #fff url('/background.png') center / cover no-repeat;
    overflow: hidden;
  }}
  .starting.active {{ display: block; }}
  .starting-stage {{
    position: relative;
    width: 100%;
    height: 100%;
    min-height: 560px;
  }}
  .starting-logo {{
    position: absolute;
    top: 2.0%;
    left: 50%;
    width: min(600px, 56vw);
    transform: translateX(-50%) skewX(-8deg);
    text-align: center;
    font-family: Impact, Haettenschweiler, 'Arial Black', sans-serif;
    font-weight: 900;
    font-style: italic;
    line-height: 0.78;
    letter-spacing: 0;
    filter: drop-shadow(0 4px 0 #0845ba) drop-shadow(0 0 11px rgba(0, 202, 255, 0.68));
  }}
  .starting-logo .cart,
  .starting-logo .rider {{
    display: block;
    -webkit-text-stroke: 2px #0743b7;
    text-shadow: 3px 3px 0 #07227a;
  }}
  .starting-logo .cart {{
    color: #0364c9;
    font-size: clamp(62px, 7.4vw, 110px);
  }}
  .starting-logo .rider {{
    color: #ffc409;
    font-size: clamp(66px, 7.8vw, 118px);
    -webkit-text-stroke-color: #ec7d00;
  }}
  .starting-subtitle {{
    position: absolute;
    top: 26.4%;
    left: 50%;
    width: min(650px, 70vw);
    transform: translateX(-50%) skewX(-8deg);
    margin: 0;
    color: #062a7c;
    font-family: Impact, Haettenschweiler, 'Arial Black', sans-serif;
    font-size: clamp(14px, 1.5vw, 25px);
    font-style: italic;
    letter-spacing: 0;
    white-space: nowrap;
    text-shadow: 0 1px 0 #fff;
  }}
  .starting-subtitle .accent {{
    color: #f5b600;
    font-size: 1.45em;
  }}
  .rover-starting {{
    position: absolute;
    left: 50%;
    top: 32%;
    width: min(170px, 14vw, 18vh);
    transform: translateX(-50%);
    filter: drop-shadow(0 12px 13px rgba(1, 18, 50, 0.27));
  }}
  .starting-banner {{
    position: absolute;
    left: 50%;
    top: 55%;
    width: min(720px, 66vw);
    height: clamp(74px, 8vw, 104px);
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: clamp(22px, 3.2vw, 58px);
    margin: 0;
    color: #fff;
    white-space: nowrap;
    overflow: hidden;
    background: linear-gradient(180deg, #0e79d8 0%, #053a9e 50%, #05226f 100%);
    border: 3px solid #16d9ff;
    clip-path: polygon(7% 0, 93% 0, 100% 50%, 93% 100%, 7% 100%, 0 50%);
    box-shadow: 0 0 0 7px rgba(0, 118, 214, 0.42), inset 0 0 22px rgba(0, 229, 255, 0.74), 0 0 24px rgba(0, 192, 255, 0.62);
    font-family: Impact, Haettenschweiler, 'Arial Black', sans-serif;
    font-size: clamp(30px, 4.1vw, 62px);
    font-style: italic;
    text-transform: uppercase;
    text-shadow: 2px 4px 0 #07215f;
  }}
  .starting-banner::before,
  .starting-banner::after {{
    content: '>>>';
    color: #23efff;
    font-size: 0.78em;
    flex: 0 0 auto;
  }}
  .starting-banner .accent {{
    color: #ffc400;
  }}
  .starting.cancelled .starting-banner {{
    color: #ff512d;
    background: linear-gradient(180deg, #1d266f 0%, #06194f 50%, #030d35 100%);
    border-color: #ff4a2d;
    box-shadow:
      0 0 0 7px rgba(255, 78, 43, 0.28),
      inset 0 0 24px rgba(255, 77, 43, 0.62),
      0 0 24px rgba(255, 77, 43, 0.62);
    text-shadow:
      2px 4px 0 #5f1111,
      0 0 16px rgba(255, 50, 24, 0.9);
  }}
  .starting.cancelled .starting-banner::before,
  .starting.cancelled .starting-banner::after {{
    color: #ff4335;
  }}
  .starting.cancelled .starting-banner .accent {{
    color: #ff512d;
  }}
  .loading-line {{
    position: absolute;
    left: 50%;
    top: calc(55% + clamp(92px, 9.8vw, 128px));
    width: min(430px, 40vw);
    height: 10px;
    transform: translateX(-50%);
    background: linear-gradient(90deg, transparent, #21ebff 12%, #fff 50%, #21ebff 88%, transparent);
    border-radius: 999px;
    box-shadow: 0 0 14px rgba(0, 229, 255, 0.86);
  }}
  .loading-line::before {{
    content: '';
    position: absolute;
    inset: -5px 0;
    background: repeating-linear-gradient(90deg, transparent 0 56px, #fff 56px 64px, transparent 64px 72px);
    opacity: 0.95;
  }}
  .starting.cancelled .loading-line {{
    background: linear-gradient(90deg, transparent, #ff4b3b 12%, #fff 50%, #ff4b3b 88%, transparent);
    box-shadow: 0 0 16px rgba(255, 68, 50, 0.9);
  }}
  .starting.cancelled .loading-line::before {{
    background: repeating-linear-gradient(90deg, transparent 0 56px, #fff 56px 64px, transparent 64px 72px);
  }}
  .starting .footer {{
    bottom: 3.0%;
    color: #092c86;
    font-size: clamp(14px, 1.25vw, 22px);
  }}
  @media (max-height: 680px) {{
    .page {{ padding-top: 26px; }}
    h1 {{ margin-bottom: 28px; }}
    .rover-title {{ width: min(320px, 48vw); margin-bottom: 24px; }}
    .help-stage::before {{ top: clamp(230px, 41vh, 300px); width: min(280px, 30vw, 36vh); }}
    .rover-help {{ width: min(330px, 32vw, 36vh); top: clamp(26px, 6vh, 52px); margin: 0; }}
    .controls {{ width: min(760px, 74vw); bottom: 20%; font-size: clamp(16px, 1.7vw, 24px); }}
    .control-panel {{ min-height: 138px; padding: 18px 28px; }}
    .help-prompt {{ width: min(620px, 70vw); font-size: clamp(18px, 2.35vw, 32px); }}
    #page-title {{ padding: 0; }}
    .brand-logo {{ top: 3.4%; width: min(650px, 74vw); }}
    .title-subtitle {{ top: 38%; }}
    #page-title .rover-title {{ width: min(340px, 36vw); bottom: 20%; }}
    .title-prompt {{ bottom: 8.5%; width: min(620px, 78vw); font-size: clamp(18px, 2.5vw, 32px); }}
    .mode-logo {{ width: min(440px, 54vw); }}
    .mode-subtitle {{ top: 25.5%; font-size: clamp(12px, 1.35vw, 20px); }}
    .rover-mode {{ top: 31%; width: min(130px, 14vw, 16vh); }}
    .mode-menu {{ bottom: 15.5%; width: min(560px, 68vw); }}
    .mode-prompt {{ width: min(620px, 72vw); font-size: clamp(18px, 2.35vw, 32px); }}
    .debug-logo {{ width: min(440px, 54vw); }}
    .debug-subtitle {{ top: 25.5%; font-size: clamp(12px, 1.35vw, 20px); }}
    .rover-debug {{ top: 31%; width: min(130px, 14vw, 16vh); }}
    .debug-menu {{ bottom: 15.5%; width: min(620px, 74vw); }}
    .debug-banner {{ font-size: clamp(13px, 1.45vw, 22px); }}
    .debug-choice {{ font-size: clamp(13px, 1.35vw, 21px); }}
    .debug-prompt {{ width: min(620px, 72vw); font-size: clamp(18px, 2.35vw, 32px); }}
    .starting-logo {{ width: min(440px, 54vw); }}
    .starting-subtitle {{ top: 25.5%; font-size: clamp(12px, 1.35vw, 20px); }}
    .rover-starting {{ top: 31%; width: min(130px, 14vw, 16vh); }}
    .starting-banner {{ width: min(620px, 72vw); font-size: clamp(24px, 3.4vw, 44px); }}
    .loading-line {{ width: min(320px, 44vw); }}
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
        <div class="title-stage">
          <div class="brand-logo" aria-label="Cart Rider!">
            <span class="cart">CART</span>
            <span class="rider">RIDER!</span>
          </div>
          <p class="title-subtitle"><span class="accent">C</span>lassification <span class="accent">A</span>nd <span class="accent">R</span>eal-time s<span class="accent">T</span>ream<span class="accent">I</span>ng <span class="accent">D</span>etection-<span class="accent">E</span>nabled <span class="accent">R</span>over</p>
          <img class="rover-title" src="/Rover.png" alt="Cart Rider rover">
          <p class="title-prompt">Press <span class="enter">Enter</span> to proceed</p>
          <div class="footer">{COPYRIGHT_TEXT}</div>
        </div>
      </div>
      <div id="page-help" class="page">
        <div class="help-stage">
          <img class="rover-help" src="/Rover.png" alt="Cart Rider rover">
          <div class="controls">
            <div class="control-panel">
              <p class="control-row"><span class="keycap">W</span><span class="colon">:</span><span class="control-action">Go forward</span></p>
              <p class="control-row"><span class="keycap">A</span><span class="colon">:</span><span class="control-action">Left forward</span></p>
              <p class="control-row"><span class="keycap">D</span><span class="colon">:</span><span class="control-action">Right forward</span></p>
              <p class="control-row"><span class="keycap">B</span><span class="colon">:</span><span class="control-action boost">Boost!</span></p>
            </div>
            <div class="control-panel">
              <p class="control-row"><span class="keycap">S</span><span class="colon">:</span><span class="control-action">Go backward</span></p>
              <p class="control-row"><span class="keycap">Z</span><span class="colon">:</span><span class="control-action">Left backward</span></p>
              <p class="control-row"><span class="keycap">C</span><span class="colon">:</span><span class="control-action">Right backward</span></p>
              <p class="control-row"><span class="keycap">Q</span><span class="colon">:</span><span class="control-action">Quit game</span></p>
            </div>
          </div>
          <p class="help-prompt">Press <span class="enter">Enter</span> to play</p>
          <div class="footer">{COPYRIGHT_TEXT}</div>
        </div>
      </div>
      <div id="page-mode" class="page">
        <div class="mode-stage">
          <div class="mode-logo" aria-label="Cart Rider!">
            <span class="cart">CART</span>
            <span class="rider">RIDER!</span>
          </div>
          <p class="mode-subtitle"><span class="accent">C</span>lassification <span class="accent">A</span>nd <span class="accent">R</span>eal-time s<span class="accent">T</span>ream<span class="accent">I</span>ng <span class="accent">D</span>etection-<span class="accent">E</span>nabled <span class="accent">R</span>over</p>
          <img class="rover-mode" src="/Rover.png" alt="Cart Rider rover">
          <div class="mode-menu">
            <p class="mode-banner">Choose play mode and press enter</p>
            <p class="mode-choice"><span class="mode-number">1</span><span class="mode-colon">:</span><span>Race mode</span></p>
            <p class="mode-choice"><span class="mode-number">2</span><span class="mode-colon">:</span><span>Debug mode</span></p>
            <label class="mode-input-row">
              <span>Input:</span>
              <input id="mode-option" maxlength="1" inputmode="numeric" autocomplete="off">
            </label>
            <div id="mode-error" class="error"></div>
          </div>
          <p class="mode-prompt">Press <span class="enter">Enter</span> to select</p>
          <div class="footer">{COPYRIGHT_TEXT}</div>
        </div>
      </div>
      <div id="page-option" class="page">
        <div class="debug-stage">
          <div class="debug-logo" aria-label="Cart Rider!">
            <span class="cart">CART</span>
            <span class="rider">RIDER!</span>
          </div>
          <p class="debug-subtitle"><span class="accent">C</span>lassification <span class="accent">A</span>nd <span class="accent">R</span>eal-time s<span class="accent">T</span>ream<span class="accent">I</span>ng <span class="accent">D</span>etection-<span class="accent">E</span>nabled <span class="accent">R</span>over</p>
          <img class="rover-debug" src="/Rover.png" alt="Cart Rider rover">
          <div class="debug-menu">
            <p class="debug-banner">Choose the debug streaming option and press enter</p>
            <p class="debug-choice"><span class="debug-number">1</span><span class="debug-colon">:</span><span>Only streaming</span></p>
            <p class="debug-choice"><span class="debug-number">2</span><span class="debug-colon">:</span><span>OpenCV-only detection streaming</span></p>
            <p class="debug-choice"><span class="debug-number">3</span><span class="debug-colon">:</span><span>Object detection streaming w/ YOLO</span></p>
            <label class="debug-input-row">
              <span>Input:</span>
              <input id="stream-option" maxlength="1" inputmode="numeric" autocomplete="off">
            </label>
            <div id="option-error" class="error"></div>
          </div>
          <p class="debug-prompt">Press <span class="enter">Enter</span> to select</p>
          <div class="footer">{COPYRIGHT_TEXT}</div>
        </div>
      </div>
      <div id="starting" class="starting">
        <div class="starting-stage">
          <div class="starting-logo" aria-label="Cart Rider!">
            <span class="cart">CART</span>
            <span class="rider">RIDER!</span>
          </div>
          <p class="starting-subtitle"><span class="accent">C</span>lassification <span class="accent">A</span>nd <span class="accent">R</span>eal-time s<span class="accent">T</span>ream<span class="accent">I</span>ng <span class="accent">D</span>etection-<span class="accent">E</span>nabled <span class="accent">R</span>over</p>
          <img class="rover-starting" src="/Rover.png" alt="Cart Rider rover">
          <p class="starting-banner"><span>Starting <span class="accent">stream...</span></span></p>
          <div class="loading-line"></div>
          <div class="footer">{COPYRIGHT_TEXT}</div>
        </div>
      </div>
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
    document.getElementById('page-mode').classList.remove('active');
    document.getElementById('page-option').classList.remove('active');
    document.getElementById('page-title').classList.add('active');
    page = 0;
  }}

  function showHelp() {{
    document.getElementById('page-title').classList.remove('active');
    document.getElementById('page-mode').classList.remove('active');
    document.getElementById('page-option').classList.remove('active');
    document.getElementById('page-help').classList.add('active');
    page = 1;
  }}

  function showMode() {{
    document.getElementById('page-title').classList.remove('active');
    document.getElementById('page-help').classList.remove('active');
    document.getElementById('page-option').classList.remove('active');
    document.getElementById('page-mode').classList.add('active');
    page = 2;
    setTimeout(() => document.getElementById('mode-option').focus(), 0);
  }}

  function showOptions() {{
    document.getElementById('page-title').classList.remove('active');
    document.getElementById('page-help').classList.remove('active');
    document.getElementById('page-mode').classList.remove('active');
    document.getElementById('page-option').classList.add('active');
    page = 3;
    setTimeout(() => document.getElementById('stream-option').focus(), 0);
  }}

  async function startRaceMode() {{
    if (starting) return;
    starting = true;
    const startingView = document.getElementById('starting');
    startingView.classList.remove('cancelled');
    document.querySelector('#starting .starting-banner span').innerHTML = 'Starting <span class="accent">stream...</span>';
    document.getElementById('page-mode').classList.remove('active');
    startingView.classList.add('active');
    await fetch('/start', {{ method: 'POST', body: 'race', cache: 'no-store' }});
    setTimeout(() => {{ window.location.href = '/'; }}, 1400);
  }}

  async function chooseMode() {{
    const input = document.getElementById('mode-option');
    const option = input.value.trim();
    const error = document.getElementById('mode-error');
    if (option === '1') {{
      await startRaceMode();
      return;
    }}
    if (option === '2') {{
      input.value = '';
      error.textContent = '';
      showOptions();
      return;
    }}
    error.textContent = 'Please input 1 or 2.';
    input.value = '';
    input.focus();
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
    const startingView = document.getElementById('starting');
    startingView.classList.remove('cancelled');
    document.querySelector('#starting .starting-banner span').innerHTML = 'Starting <span class="accent">stream...</span>';
    document.getElementById('page-option').classList.remove('active');
    startingView.classList.add('active');
    await fetch('/start', {{ method: 'POST', body: option, cache: 'no-store' }});
    setTimeout(() => {{ window.location.href = '/'; }}, 1400);
  }}

  document.getElementById('mode-option').addEventListener('input', event => {{
    event.target.value = event.target.value.replace(/[^1-2]/g, '').slice(0, 1);
    document.getElementById('mode-error').textContent = '';
  }});

  document.getElementById('stream-option').addEventListener('input', event => {{
    event.target.value = event.target.value.replace(/[^1-3]/g, '').slice(0, 1);
    document.getElementById('option-error').textContent = '';
  }});

  const initialPage = '{initial_page}';
  if (initialPage === 'help') showHelp();
  else if (initialPage === 'option') showMode();

  document.addEventListener('keydown', async (event) => {{
    if (event.key === 'Backspace') {{
      event.preventDefault();
      if (page === 3) showMode();
      else if (page === 2) showHelp();
      else if (page === 1) showTitle();
      return;
    }}

    if (event.key === 'Enter') {{
      event.preventDefault();
      if (page === 0) showHelp();
      else if (page === 1) showMode();
      else if (page === 2) await chooseMode();
      else await startGame();
    }} else if (event.key === 'Escape' || (page !== 2 && event.key.toLowerCase() === 'q')) {{
      await post('/cancel');
      const startingView = document.getElementById('starting');
      document.querySelectorAll('.page.active').forEach(activePage => activePage.classList.remove('active'));
      document.querySelector('#starting .starting-banner span').innerHTML = '<span class="accent">Cancelled</span>';
      startingView.classList.add('cancelled');
      startingView.classList.add('active');
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
    print('Press Enter twice, choose RACE mode or Debug mode, then press Enter in the browser.')

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
