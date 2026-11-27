import http.server
import socketserver
import os
import mimetypes
import re
import sys
import json
import urllib.request
import urllib.error
from urllib.parse import urlsplit, parse_qsl, urlencode

class NoFormRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        # Never forward submitted personal data to another destination.
        return None

PORT = int(sys.argv[1]) if __name__ == "__main__" and len(sys.argv) > 1 else 8081
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
IMAGE_CACHE_PATH = os.path.join(DIRECTORY, "local-image-cache.json")
IMAGE_CACHE = {}
if os.path.isfile(IMAGE_CACHE_PATH):
    with open(IMAGE_CACHE_PATH, encoding="utf-8") as cache_file:
        IMAGE_CACHE = json.load(cache_file)

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("image/webp", ".webp")
mimetypes.add_type("video/mp4", ".mp4")
mimetypes.add_type("application/manifest+json", ".webmanifest")

class RangeHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def translate_path(self, path):
        # Exact, predownloaded public image variants; never fetch at runtime.
        parsed = urlsplit(path)
        for host in ("images.unsplash.com", "images.pexels.com"):
            prefix = "/_ext/" + host
            if parsed.path.startswith(prefix + "/"):
                key = "https://" + host + parsed.path[len(prefix):] + "?" + urlencode(sorted(parse_qsl(parsed.query)))
                record = IMAGE_CACHE.get(key)
                if record:
                    target = os.path.abspath(os.path.join(DIRECTORY, record["file"]))
                    if os.path.commonpath((DIRECTORY, target)) == DIRECTORY:
                        return target
        return super().translate_path(path)

    def handle(self):
        try:
            super().handle()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            # Browsers cancel media/prefetch requests during navigation.
            pass

    def do_GET(self):
        # Support HTTP Range requests for video/audio streaming
        range_header = self.headers.get("Range")
        if not range_header:
            return super().do_GET()

        path = self.translate_path(self.path)
        if not os.path.isfile(path):
            return super().do_GET()

        try:
            file_size = os.path.getsize(path)
            # Parse Range header e.g. "bytes=0-1024" or "bytes=0-"
            m = re.search(r"bytes=(\d+)-(\d*)", range_header)
            if not m:
                return super().do_GET()

            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else file_size - 1
            if start >= file_size or end >= file_size or start > end:
                self.send_error(416, "Requested Range Not Satisfiable")
                return

            length = end - start + 1

            self.send_response(206)
            content_type = self.guess_type(path)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self.send_header("Content-Length", str(length))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()

            with open(path, "rb") as f:
                f.seek(start)
                bytes_to_send = length
                buf_size = 64 * 1024
                while bytes_to_send > 0:
                    read_size = min(buf_size, bytes_to_send)
                    data = f.read(read_size)
                    if not data:
                        break
                    self.wfile.write(data)
                    bytes_to_send -= len(data)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass
        except Exception as e:
            try:
                self.send_error(500, str(e))
            except Exception:
                pass

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_POST(self):
        # The original mail/newsletter PHP backend is an online service, not a
        # downloadable static asset. Forward only explicit browser submissions
        # to its original public endpoint. No fake success or stored form data.
        if urlsplit(self.path).path != "/form-handler.php":
            self.send_error(405, "This local server only forwards the original contact endpoint")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 65536:
                self.send_error(413, "Invalid form request size")
                return
            payload = self.rfile.read(length)
            json.loads(payload)
            headers = {"Content-Type": "application/json", "Accept": "application/json"}
            # Preserve the real origin; do not spoof access-control headers.
            for name in ("Origin", "Referer", "User-Agent"):
                if self.headers.get(name):
                    headers[name] = self.headers[name]
            request = urllib.request.Request(
                "https://2mcrafters.com/form-handler.php", data=payload,
                headers=headers, method="POST"
            )
            try:
                response = urllib.request.build_opener(NoFormRedirect()).open(request, timeout=20)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                body = response.read(262144)
                self.send_response(response.status)
                self.send_header("Content-Type", response.headers.get("Content-Type", "application/json"))
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        except (ValueError, json.JSONDecodeError):
            self.send_error(400, "Invalid form JSON")
        except (urllib.error.URLError, TimeoutError):
            self.send_error(502, "The original online form service is unavailable")
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass

    def log_message(self, format, *args):
        # Simple logging without spamming
        print(f"[{self.log_date_time_string()}] {args[0]} - {args[1]}", flush=True)

class ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    request_queue_size = 128

if __name__ == "__main__":
    os.chdir(DIRECTORY)
    server_address = ("127.0.0.1", PORT)
    httpd = ThreadingServer(server_address, RangeHTTPRequestHandler)
    print(f"Server with HTTP Range & No-Cache support running at http://localhost:{PORT}/", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
