#!/usr/bin/env python3
"""Serve the desktop Markdown reader and read local Markdown paths.

只用标准库，任何 Python 3.8+ 都能跑。
启动脚本：桌面 `Markdown阅读器启动.bat`。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import mimetypes
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit


SUPPORTED_SUFFIXES = {".md", ".markdown", ".mdown", ".mkdn", ".txt"}
DEFAULT_PORT = 8765
SERVER_TAG = "markdown-reader/1.2"
MAX_WRITE_BYTES = 10 * 1024 * 1024
SCRIPT_DIR = Path(__file__).resolve().parent
DESKTOP_HTML = Path.home() / "Desktop" / "Markdown阅读器.html"
FALLBACK_HTMLS = (SCRIPT_DIR / "markdown_reader_ui.html",)


def resolve_html(explicit: Path | None) -> Path | None:
    """按 显式参数 -> 桌面 -> 仓库副本 的顺序找一个存在的页面文件。"""
    candidates = []
    if explicit is not None:
        candidates.append(Path(explicit))
    candidates.append(DESKTOP_HTML)
    candidates.extend(FALLBACK_HTMLS)
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate.resolve()
        except OSError:
            continue
    return None


def local_path(raw: str) -> Path:
    value = unquote(str(raw or "").strip())
    if value.lower().startswith("file://"):
        parsed = urlsplit(value)
        value = unquote(parsed.path)
        if parsed.netloc:
            value = f"//{parsed.netloc}{value}"
        elif len(value) >= 3 and value[0] == "/" and value[2] == ":":
            value = value[1:]
    candidate = Path(value).expanduser()
    if candidate.exists():
        return candidate
    repaired = re.sub(r"([\\/])\s+", r"\1", value)
    if repaired != value:
        repaired_candidate = Path(repaired).expanduser()
        if repaired_candidate.exists():
            return repaired_candidate
    return candidate


def decode_markdown(raw: bytes) -> str:
    utf8 = raw.decode("utf-8", errors="replace")
    if utf8.count("\ufffd") > 3:
        try:
            return raw.decode("gb18030")
        except UnicodeDecodeError:
            pass
    return utf8


class ReaderHandler(BaseHTTPRequestHandler):
    server_version = "MarkdownReader/1.2"

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Markdown-Reader")
        super().end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        if parsed.path in {"", "/"}:
            if self.server.html_path is None:
                self.send_error(500, "Reader HTML not found")
                return
            self.send_file(self.server.html_path, "text/html; charset=utf-8")
            return
        if parsed.path == "/api/health":
            self.send_json(200, {
                "ok": True,
                "server": SERVER_TAG,
                "pid": __import__("os").getpid(),
                "html": str(self.server.html_path) if self.server.html_path else None,
            })
            return
        if parsed.path == "/api/read":
            self.read_markdown(parse_qs(parsed.query).get("path", [""])[0])
            return
        if parsed.path == "/api/asset":
            self.read_asset(parse_qs(parsed.query).get("path", [""])[0])
            return
        self.send_error(404, "Not found")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        if parsed.path != "/api/write":
            self.send_error(404, "Not found")
            return
        origin = self.headers.get("Origin", "")
        allowed_origin = (
            not origin
            or origin == "null"
            or origin.startswith("http://127.0.0.1:")
            or origin.startswith("http://localhost:")
        )
        if not allowed_origin or self.headers.get("X-Markdown-Reader") != "1":
            self.send_json(403, {"error": "拒绝非本地阅读器的写入请求"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_WRITE_BYTES:
            self.send_json(400, {"error": "保存内容为空或超过 10 MB"})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(400, {"error": "保存请求格式不正确"})
            return
        self.write_markdown(payload.get("path", ""), payload.get("content"))

    def read_markdown(self, raw_path: str) -> None:
        if not raw_path:
            self.send_json(400, {"error": "缺少 path 参数"})
            return
        path = local_path(raw_path)
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            self.send_json(400, {"error": "只支持 Markdown 或纯文本文件"})
            return
        try:
            stat = path.stat()
            if not path.is_file():
                raise FileNotFoundError
            content = decode_markdown(path.read_bytes())
        except (OSError, UnicodeError):
            self.send_json(404, {"error": f"无法读取文件：{path}"})
            return
        self.send_json(
            200,
            {
                "name": path.name,
                "path": str(path),
                "size": stat.st_size,
                "lastModified": int(stat.st_mtime * 1000),
                "content": content,
            },
        )

    def read_asset(self, raw_path: str) -> None:
        """读取 Markdown 引用的本地图片等资源。路径由用户在阅读器中明确打开。"""
        if not raw_path:
            self.send_json(400, {"error": "缺少 path 参数"})
            return
        path = local_path(raw_path)
        try:
            if not path.is_file():
                raise FileNotFoundError
            payload = path.read_bytes()
        except OSError:
            self.send_json(404, {"error": f"无法读取资源：{path}"})
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(payload)

    def write_markdown(self, raw_path: str, content: object) -> None:
        if not raw_path or not isinstance(content, str):
            self.send_json(400, {"error": "缺少文件路径或正文"})
            return
        path = local_path(raw_path)
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            self.send_json(400, {"error": "只允许保存 Markdown 或纯文本文件"})
            return
        temp_name = None
        try:
            if not path.is_file():
                raise FileNotFoundError
            payload = content.encode("utf-8")
            if len(payload) > MAX_WRITE_BYTES:
                self.send_json(400, {"error": "文件超过 10 MB，无法保存"})
                return
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
            ) as temp_file:
                temp_name = temp_file.name
                temp_file.write(payload)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            os.replace(temp_name, path)
            stat = path.stat()
        except OSError as exc:
            if temp_name:
                try:
                    Path(temp_name).unlink(missing_ok=True)
                except OSError:
                    pass
            self.send_json(500, {"error": f"保存失败：{exc}"})
            return
        self.send_json(200, {
            "ok": True,
            "path": str(path),
            "size": stat.st_size,
            "lastModified": int(stat.st_mtime * 1000),
        })

    def send_file(self, path: Path, content_type: str) -> None:
        try:
            payload = path.read_bytes()
        except OSError:
            self.send_error(404, "Reader HTML not found")
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        print(f"[markdown-reader] {format % args}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--html", type=Path, default=None)
    args = parser.parse_args()

    html_path = resolve_html(args.html)
    try:
        server = ThreadingHTTPServer((args.host, args.port), ReaderHandler)
    except OSError as exc:
        print(f"[error] 端口 {args.port} 无法绑定：{exc}", flush=True)
        return 2
    server.html_path = html_path
    print(f"Markdown reader: http://{args.host}:{args.port}/", flush=True)
    print(f"Reader HTML: {html_path}", flush=True)
    if html_path is None:
        print("[warn] 没找到阅读器页面文件，根路径会返回 500", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
