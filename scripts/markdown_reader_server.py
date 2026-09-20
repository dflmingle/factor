#!/usr/bin/env python3
"""Serve the desktop Markdown reader and read local Markdown paths."""

from __future__ import annotations

import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit


SUPPORTED_SUFFIXES = {".md", ".markdown", ".mdown", ".mkdn", ".txt"}
DEFAULT_PORT = 8765
DEFAULT_HTML = Path.home() / "Desktop" / "Markdown阅读器.html"


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
    server_version = "MarkdownReader/1.0"

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        if parsed.path in {"", "/"}:
            self.send_file(self.server.html_path, "text/html; charset=utf-8")
            return
        if parsed.path == "/api/health":
            self.send_json(200, {"ok": True})
            return
        if parsed.path == "/api/read":
            self.read_markdown(parse_qs(parsed.query).get("path", [""])[0])
            return
        self.send_error(404, "Not found")

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

    def send_json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[markdown-reader] {format % args}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--html", type=Path, default=DEFAULT_HTML)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), ReaderHandler)
    server.html_path = args.html.resolve()
    print(f"Markdown reader: http://{args.host}:{args.port}/", flush=True)
    print(f"Reader HTML: {server.html_path}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
