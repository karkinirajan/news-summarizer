"""Tiny local HTTP servers that behave like NewsAPI and the OpenAI Responses endpoint."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar
from urllib.parse import parse_qs, urlparse


class _Server:
    def __init__(self, handler_cls):
        self.requests: list[dict] = []
        handler_cls.owner = self
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
        self.thread = threading.Thread(
            target=lambda: self.httpd.serve_forever(poll_interval=0.05), daemon=True
        )

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def start(self):
        self.thread.start()
        return self

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class _Handler(BaseHTTPRequestHandler):
    owner: _Server

    def log_message(self, *args):  # silence the test output
        pass

    def reply(self, status: int, body: dict):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class NewsAPIHandler(_Handler):
    articles: ClassVar[list[dict]] = []
    api_key = ""

    def do_GET(self):
        url = urlparse(self.path)
        self.owner.requests.append(
            {
                "path": url.path,
                "query": parse_qs(url.query),
                "headers": {k.lower(): v for k, v in self.headers.items()},
            }
        )
        if url.path != "/v2/everything":
            return self.reply(404, {"status": "error", "message": "not found"})
        if self.headers.get("X-Api-Key") != self.api_key:
            return self.reply(
                401,
                {"status": "error", "code": "apiKeyInvalid", "message": "Your API key is invalid."},
            )
        self.reply(
            200, {"status": "ok", "totalResults": len(self.articles), "articles": self.articles}
        )


class ResponsesHandler(_Handler):
    api_key = ""

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")
        self.owner.requests.append(
            {
                "path": self.path,
                "body": body,
                "headers": {k.lower(): v for k, v in self.headers.items()},
            }
        )
        if self.headers.get("Authorization") != f"Bearer {self.api_key}":
            return self.reply(
                401,
                {
                    "error": {
                        "message": "Incorrect API key provided.",
                        "type": "invalid_request_error",
                        "code": "invalid_api_key",
                    }
                },
            )
        text_in = body.get("input", "")
        title = text_in.split("\n", 1)[0].removeprefix("Title: ")
        if "BREAK" in title:
            return self.reply(
                400,
                {"error": {"message": "this request is refused", "type": "invalid_request_error"}},
            )
        self.reply(
            200,
            {
                "id": "resp_demo",
                "object": "response",
                "created_at": 1700000000.0,
                "status": "completed",
                "model": body.get("model", "?"),
                "output": [
                    {
                        "type": "message",
                        "id": "msg_demo",
                        "status": "completed",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": f"Summary of: {title}",
                                "annotations": [],
                            }
                        ],
                    }
                ],
                "parallel_tool_calls": True,
                "tool_choice": "auto",
                "tools": [],
            },
        )


def start_news_server(articles: list[dict], api_key: str) -> _Server:
    handler = type("News", (NewsAPIHandler,), {"articles": articles, "api_key": api_key})
    return _Server(handler).start()


def start_openai_server(api_key: str) -> _Server:
    handler = type("Responses", (ResponsesHandler,), {"api_key": api_key})
    return _Server(handler).start()
