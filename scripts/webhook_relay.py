#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Loopback gateway exposing only the exact Meta webhook route.

Run cloudflared against this listener, never against the dashboard listener.
Authentication (verify token / byte-exact HMAC) remains in the agent backend.
"""
import argparse
import http.client
import http.server
import socket

MAX_BODY = 1024 * 1024


def make_handler(upstream_port):
    class WebhookHandler(http.server.BaseHTTPRequestHandler):
        server_version = "AriaWebhook"
        sys_version = ""

        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, fmt, *args):
            # Never log query strings: Meta verification includes a verify token.
            pass

        def reply(self, status, body=b"", content_type="text/plain; charset=utf-8"):
            self.close_connection = True
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Connection", "close")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def forward(self):
            # No decoding, normalization, redirects or wildcard path matching.
            if self.path.partition("?")[0] != "/webhook":
                self.reply(404, b"Not found")
                return
            lengths = self.headers.get_all("Content-Length", [])
            if self.headers.get("Transfer-Encoding") or len(lengths) > 1:
                self.reply(400, b"Ambiguous request framing")
                return
            if self.command == "POST" and not lengths:
                self.reply(411, b"Content-Length required")
                return
            raw_length = lengths[0] if lengths else "0"
            if len(raw_length) > 10 or not raw_length.isascii() or not raw_length.isdecimal():
                self.reply(400, b"Invalid Content-Length")
                return
            length = int(raw_length)
            if length > MAX_BODY:
                self.reply(413, b"Request too large")
                return
            if self.command == "GET" and length:
                self.reply(400, b"GET body is not supported")
                return
            try:
                body = self.rfile.read(length)
            except (OSError, socket.timeout):
                self.reply(408, b"Request timeout")
                return
            if len(body) != length:
                self.reply(400, b"Incomplete body")
                return
            headers = {"Content-Type": self.headers.get("Content-Type", "application/json")}
            signatures = self.headers.get_all("X-Hub-Signature-256", [])
            if len(signatures) > 1:
                self.reply(400, b"Duplicate signature")
                return
            if signatures:
                headers["X-Hub-Signature-256"] = signatures[0]
            conn = http.client.HTTPConnection("127.0.0.1", upstream_port, timeout=15)
            try:
                conn.request(self.command, self.path, body=body, headers=headers)
                response = conn.getresponse()
                result = response.read(MAX_BODY + 1)
                if len(result) > MAX_BODY:
                    self.reply(502, b"Upstream response too large")
                    return
                self.reply(response.status, result, response.getheader("Content-Type", "text/plain"))
            except (OSError, http.client.HTTPException):
                self.reply(502, b"Webhook backend unavailable")
            finally:
                conn.close()

        do_GET = forward
        do_POST = forward

        def unsupported(self):
            self.reply(405, b"Method not allowed")

        do_HEAD = do_OPTIONS = do_PUT = do_PATCH = do_DELETE = do_TRACE = do_CONNECT = unsupported

    return WebhookHandler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--upstream-port", type=int, default=8080)
    args = parser.parse_args()
    if not all(1 <= p <= 65535 for p in (args.port, args.upstream_port)) or args.port == args.upstream_port:
        parser.error("Provide distinct, valid listener and upstream ports")
    server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.upstream_port))
    print("Webhook-only relay listening on 127.0.0.1:%d" % args.port, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
