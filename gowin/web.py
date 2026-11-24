"""Loopback-only HTTP adapter for the optional browser GUI."""

import json
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.parse import urlsplit

from .board import GameError
from .platform import Platform
from .storage import Archive


class GuiServer(ThreadingHTTPServer):
    def __init__(self, port: int):
        self.platform = Platform()
        self.lock = Lock()
        self.static = Path(__file__).with_name("static")
        super().__init__(("127.0.0.1", port), GuiHandler)

    @property
    def origin(self) -> str:
        return f"http://127.0.0.1:{self.server_port}"


class GuiHandler(BaseHTTPRequestHandler):
    server: GuiServer

    def log_message(self, format, *args):
        pass

    def _send(self, status: HTTPStatus, mime: str, payload: bytes):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, status: HTTPStatus, **data):
        self._send(status, "application/json; charset=utf-8", json.dumps(
            data, ensure_ascii=False
        ).encode("utf-8"))

    def _valid_host(self) -> bool:
        return self.headers.get("Host") == self.server.origin.removeprefix("http://")

    def do_GET(self):
        if not self._valid_host():
            self._json(HTTPStatus.FORBIDDEN, message="请通过本机图形界面的地址访问。")
            return
        path = urlsplit(self.path).path
        if path == "/api/state":
            with self.server.lock:
                state = self.server.platform.view()
            self._json(HTTPStatus.OK, state=state)
            return
        if path == "/api/archive":
            try:
                with self.server.lock:
                    payload = self.server.platform.archive()
            except GameError as error:
                self._json(HTTPStatus.BAD_REQUEST, message=str(error))
            else:
                self._send(HTTPStatus.OK, "application/json; charset=utf-8", payload)
            return
        files = {
            "/": ("index.html", "text/html"),
            "/app.css": ("app.css", "text/css"),
            "/app.js": ("app.js", "text/javascript"),
        }
        if path in files:
            name, mime = files[path]
            self._send(HTTPStatus.OK, mime + "; charset=utf-8", (self.server.static / name).read_bytes())
            return
        self._json(HTTPStatus.NOT_FOUND, message="未找到页面。")

    def do_POST(self):
        if not self._valid_host() or self.headers.get("Origin") != self.server.origin:
            self._json(HTTPStatus.FORBIDDEN, message="请求必须来自本机图形界面。")
            return
        path = urlsplit(self.path).path
        if path not in ("/api/action", "/api/load"):
            self._json(HTTPStatus.NOT_FOUND, message="未知接口。")
            return
        try:
            payload = self._body()
        except GameError as error:
            self._json(HTTPStatus.BAD_REQUEST, message=str(error))
            return
        with self.server.lock:
            platform = self.server.platform
            try:
                message = platform.restore(payload) if path == "/api/load" else self._act(platform, payload)
            except GameError as error:
                status, message = HTTPStatus.BAD_REQUEST, str(error)
            else:
                status = HTTPStatus.OK
            state = platform.view()
        self._json(status, message=message, state=state)

    def _body(self) -> bytes:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise GameError("请求长度无效。") from error
        if self.headers.get_content_type() != "application/json":
            raise GameError("请求格式必须为 JSON。")
        if not 0 < length <= Archive.max_bytes:
            raise GameError("请求大小必须在 1 MiB 以内。")
        return self.rfile.read(length)

    @staticmethod
    def _act(platform: Platform, payload: bytes) -> str:
        try:
            request = json.loads(payload.decode("utf-8"))
        except (ValueError, RecursionError) as error:
            raise GameError("操作数据不是有效的 JSON。") from error
        if not isinstance(request, dict):
            raise GameError("操作格式无效。")
        action = request.get("action")
        if action == "new":
            return platform.start(request.get("kind"), request.get("size"))
        if action == "restart":
            return platform.restart()
        return platform.act(action, request.get("coordinate"))


def run_gui(port: int, open_browser: bool):
    with GuiServer(port) as server:
        print(f"Go-win 图形界面：{server.origin}（Ctrl+C 退出）", flush=True)
        if open_browser:
            webbrowser.open(server.origin)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n已退出。")
