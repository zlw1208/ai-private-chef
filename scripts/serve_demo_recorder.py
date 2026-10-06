"""Serve README media and accept one browser-recorded WebM file."""

from __future__ import annotations

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "demo" / "ai-private-chef-demo.webm"


class Handler(SimpleHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/save-video":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        OUTPUT.write_bytes(self.rfile.read(length))
        self.send_response(201)
        self.end_headers()
        self.wfile.write(b"saved")


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    print("Recorder: http://127.0.0.1:8765/scripts/demo_recorder.html", flush=True)
    server.serve_forever()
