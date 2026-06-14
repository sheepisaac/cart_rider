from http.server import BaseHTTPRequestHandler


class ControlHandler(BaseHTTPRequestHandler):
    control_callback = None
    back_callback = None

    def send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cache-Control', 'no-store')

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()

    def do_POST(self):
        if self.path == '/back':
            callback = type(self).back_callback
            if callback is not None:
                callback()
            self.send_response(204)
            self.send_cors_headers()
            self.end_headers()
            return

        if self.path != '/control':
            self.send_response(404)
            self.send_cors_headers()
            self.end_headers()
            return

        length = int(self.headers.get('Content-Length', '0') or 0)
        key = self.rfile.read(length).decode('utf-8', errors='ignore').strip().lower()
        callback = type(self).control_callback
        if callback is not None:
            callback(key)

        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()

    def log_message(self, format, *args):
        return


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
                b'<script>document.body.focus();const controlBase="http://"+location.hostname+":8081";let held=null,lastSent=0;function send(k){fetch(controlBase+"/control",{method:"POST",body:k,cache:"no-store",mode:"cors"}).catch(()=>{});}'
                b'function keepAlive(){if(!held)return;const n=performance.now();if(n-lastSent<250)return;lastSent=n;send(held);}'
                b'function stopHeld(){if(!held)return;held=null;send("x");}'
                b'function goBack(){stopHeld();fetch(controlBase+"/back",{method:"POST",cache:"no-store",mode:"cors"}).finally(()=>{document.body.textContent="Returning...";document.body.style.color="white";document.body.style.font="36px Arial,sans-serif";setTimeout(()=>{window.location.href="/";},1200);});}'
                b'document.addEventListener("keydown",e=>{if(e.key==="Backspace"){e.preventDefault();goBack();return;}'
                b'const k=e.key.toLowerCase();if(!"wasdzcbq".includes(k))return;e.preventDefault();'
                b'if(k==="b"||k==="q"){send(k);return;}if(held!==k){held=k;lastSent=performance.now();send(k);}});'
                b'document.addEventListener("keyup",e=>{const k=e.key.toLowerCase();if(k===held)stopHeld();});'
                b'setInterval(keepAlive,100);document.addEventListener("blur",stopHeld);document.addEventListener("click",()=>document.body.focus());</script></body></html>'
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
