"""Controlled local-server tests. No Internet access or third-party packages."""

import http.client
import importlib.util
import json
import pathlib
import socket
import socketserver
import ssl
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from urllib.parse import urlsplit


MODULE = pathlib.Path(__file__).resolve().parents[1] / "agents/common/network_proxy.py"
spec = importlib.util.spec_from_file_location("network_proxy_under_test", MODULE)
proxy_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proxy_module)
RestrictedProxy = proxy_module.RestrictedProxy


class Origin(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        self.server.hits.append((self.command, self.path, b""))
        self.send_response(302 if self.path == "/redirect" else 200)
        if self.path == "/redirect":
            self.send_header("Location", self.server.redirect)
        self.end_headers()
        self.wfile.write(b"origin-response")

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.server.hits.append((self.command, self.path, body))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(body)

    do_PUT = do_POST


class Echo(socketserver.BaseRequestHandler):
    def handle(self):
        self.server.hits.append(True)
        try:
            while True:
                data = self.request.recv(65536)
                if not data:
                    break
                self.request.sendall(data)
        except OSError:
            pass


class DelayedOrigin(Origin):
    def do_GET(self):
        self.server.request_started.set()
        self.server.release_response.wait(timeout=3)
        try:
            super().do_GET()
        except OSError:
            # A shutdown test intentionally closes the waiting connection.
            pass


def client_hello(sni=None):
    body = b"\x03\x03" + b"r" * 32 + b"\x00\x00\x02\x13\x01\x01\x00"
    if sni is not None:
        name = sni.encode("ascii")
        item = b"\x00" + len(name).to_bytes(2, "big") + name
        ext = len(item).to_bytes(2, "big") + item
        extensions = b"\x00\x00" + len(ext).to_bytes(2, "big") + ext
        body += len(extensions).to_bytes(2, "big") + extensions
    message = b"\x01" + len(body).to_bytes(3, "big") + body
    return b"\x16\x03\x01" + len(message).to_bytes(2, "big") + message


class ProxyTests(unittest.TestCase):
    def setUp(self):
        self.servers = []
        self.proxies = []
        self.sockets = []

    def tearDown(self):
        for proxy in self.proxies:
            proxy.close()
        for sock in self.sockets:
            sock.close()
        for server in self.servers:
            server.shutdown()
            server.server_close()

    def server(self, handler=Origin):
        cls = ThreadingHTTPServer if issubclass(handler, BaseHTTPRequestHandler) else socketserver.ThreadingTCPServer
        server = cls(("127.0.0.1", 0), handler)
        server.daemon_threads = True
        server.hits = []
        server.redirect = ""
        server.request_started = threading.Event()
        server.release_response = threading.Event()
        self.servers.append(server)
        threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        return server

    def proxy(self, endpoints=(), client_ip=None, host_address_map=None):
        proxy = RestrictedProxy(endpoints, "127.0.0.1", client_ip, host_address_map)
        self.proxies.append(proxy)
        parsed = urlsplit(proxy.start())
        return proxy, (parsed.hostname, parsed.port)

    def request(self, address, target, method="GET", body=None, headers=None):
        conn = http.client.HTTPConnection(*address, timeout=3)
        try:
            conn.request(method, target, body=body, headers=headers or {})
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()

    def raw(self, address, payload):
        with socket.create_connection(address, timeout=3) as sock:
            sock.sendall(payload)
            result = bytearray()
            while True:
                part = sock.recv(65536)
                if not part:
                    return bytes(result)
                result.extend(part)

    def tunnel(self, address, host, port):
        sock = socket.create_connection(address, timeout=3)
        self.sockets.append(sock)
        authority = f"{host}:{port}"
        sock.sendall(f"CONNECT {authority} HTTP/1.1\r\nHost: {authority}\r\n\r\n".encode())
        response = bytearray()
        while not response.endswith(b"\r\n\r\n"):
            response.extend(sock.recv(1))
        self.assertTrue(response.startswith(b"HTTP/1.1 200"), response)
        return sock

    def test_default_deny_exact_hosts_ports_and_bad_authorities(self):
        origin = self.server()
        port = origin.server_port
        proxy, address = self.proxy([("localhost", port)])
        for target, status in [
            (f"http://localhost:{port}/", 200),
            (f"http://127.0.0.1:{port}/", 403),
            (f"http://localhost:{port + 1}/", 403),
            (f"http://localhost.attacker.invalid:{port}/", 403),
            (f"http://user:password@localhost:{port}/", 400),
            (f"http://localhost:{port}/#fragment", 400),
            (f"https://localhost:{port}/", 400),
        ]:
            with self.subTest(target=target):
                self.assertEqual(self.request(address, target)[0], status)
        self.assertEqual(len(origin.hits), 1)
        empty, empty_address = self.proxy()
        self.assertEqual(self.request(empty_address, f"http://localhost:{port}/")[0], 403)
        self.assertFalse(empty.events[-1]["allowed"])

    def test_post_put_bodies_and_safe_bounded_events(self):
        origin = self.server()
        proxy, address = self.proxy([("127.0.0.1", origin.server_port)])
        for method in ["POST", "PUT"]:
            target = f"http://127.0.0.1:{origin.server_port}/private-path?token=private-query"
            result = self.request(address, target, method, b"private-body", {"Authorization": "Bearer private-auth"})
            self.assertEqual((result[0], result[2]), (200, b"private-body"))
        encoded = json.dumps(proxy.events)
        for secret in ["private-path", "private-query", "private-body", "private-auth"]:
            self.assertNotIn(secret, encoded)
        for event in proxy.events:
            self.assertEqual(set(event), {"host", "port", "method", "allowed", "result"})
        for _ in range(proxy_module.MAX_EVENTS + 5):
            proxy._event("localhost", 80, "GET", False, "endpoint_denied")
        self.assertEqual(len(proxy.events), proxy_module.MAX_EVENTS)

    def test_slow_http_response_has_separate_read_timeout(self):
        origin = self.server(DelayedOrigin)
        _, address = self.proxy([("127.0.0.1", origin.server_port)])
        timer = threading.Timer(0.3, origin.release_response.set)
        try:
            with patch.object(proxy_module, "IO_TIMEOUT", 0.1), \
                    patch.object(proxy_module, "HTTP_RESPONSE_TIMEOUT", 2):
                timer.start()
                status, _, body = self.request(address, f"http://127.0.0.1:{origin.server_port}/")
            self.assertEqual((status, body), (200, b"origin-response"))
            self.assertTrue(origin.request_started.is_set())
        finally:
            origin.release_response.set()
            timer.cancel()
            timer.join()

    def test_close_cancels_waiting_http_response(self):
        origin = self.server(DelayedOrigin)
        proxy, address = self.proxy([("127.0.0.1", origin.server_port)])
        sock = socket.create_connection(address, timeout=3)
        self.sockets.append(sock)
        target = f"127.0.0.1:{origin.server_port}"
        try:
            with patch.object(proxy_module, "HTTP_RESPONSE_TIMEOUT", 10):
                sock.sendall(f"GET http://{target}/ HTTP/1.1\r\nHost: {target}\r\n\r\n".encode())
                self.assertTrue(origin.request_started.wait(timeout=1))
                start = time.monotonic()
                proxy.close()
                self.assertLess(time.monotonic() - start, 1)
                self.assertEqual(sock.recv(1), b"")
                # The upstream waiting handler must terminate too, rather than
                # retaining its ten-minute response wait after client closure.
                deadline = time.monotonic() + 1
                while proxy._sockets and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertFalse(proxy._sockets)
        finally:
            origin.release_response.set()

    def test_redirect_is_returned_not_followed_and_next_request_checked(self):
        origin, forbidden = self.server(), self.server()
        origin.redirect = f"http://127.0.0.1:{forbidden.server_port}/secret"
        _, address = self.proxy([("127.0.0.1", origin.server_port)])
        status, headers, _ = self.request(address, f"http://127.0.0.1:{origin.server_port}/redirect")
        self.assertEqual(status, 302)
        self.assertEqual(headers["Location"], origin.redirect)
        self.assertEqual(forbidden.hits, [])
        self.assertEqual(self.request(address, headers["Location"])[0], 403)
        self.assertEqual(forbidden.hits, [])

    def test_bad_host_and_body_framing_are_rejected(self):
        origin = self.server()
        _, address = self.proxy([("127.0.0.1", origin.server_port)])
        target = f"http://127.0.0.1:{origin.server_port}/"
        host = f"127.0.0.1:{origin.server_port}"
        bad_headers = [
            "Host: unrelated.invalid\r\n",
            f"Host: {host}\r\nHost: {host}\r\n",
            f"Host: {host}\r\nContent-Length: 0\r\nContent-Length: 0\r\n",
            f"Host: {host}\r\nTransfer-Encoding: chunked\r\n",
            f"Host: {host}\r\nContent-Length: -1\r\n",
        ]
        for headers in bad_headers:
            response = self.raw(address, f"POST {target} HTTP/1.1\r\n{headers}\r\n".encode())
            self.assertTrue(response.startswith(b"HTTP/1.1 400"), response)
        self.assertEqual(origin.hits, [])

    def test_request_limits(self):
        origin = self.server()
        _, address = self.proxy([("127.0.0.1", origin.server_port)])
        target = f"http://127.0.0.1:{origin.server_port}/"
        host = f"127.0.0.1:{origin.server_port}"
        payload = f"POST {target} HTTP/1.1\r\nHost: {host}\r\nContent-Length: {proxy_module.MAX_BODY + 1}\r\n\r\n"
        self.assertTrue(self.raw(address, payload.encode()).startswith(b"HTTP/1.1 413"))
        payload = f"GET {target} HTTP/1.1\r\nHost: {host}\r\n" + "X-Pad: " + "a" * proxy_module.MAX_HEADERS + "\r\n\r\n"
        self.assertTrue(self.raw(address, payload.encode()).startswith(b"HTTP/1.1 431"))

    def test_client_ip_can_be_enabled_after_start(self):
        origin = self.server()
        proxy, address = self.proxy([("127.0.0.1", origin.server_port)], "0.0.0.0")
        target = f"http://127.0.0.1:{origin.server_port}/"
        self.assertEqual(self.request(address, target)[0], 403)
        proxy.set_allowed_client_ip("127.0.0.1")
        self.assertEqual(self.request(address, target)[0], 200)

    def test_docker_host_mapping_does_not_expand_the_acl(self):
        origin = self.server()
        _, address = self.proxy(
            [("internal.invalid", origin.server_port)],
            host_address_map={"internal.invalid": "127.0.0.1", "other.invalid": "127.0.0.1"},
        )
        self.assertEqual(self.request(address, f"http://internal.invalid:{origin.server_port}/")[0], 200)
        self.assertEqual(self.request(address, f"http://other.invalid:{origin.server_port}/")[0], 403)
        self.assertEqual(self.request(address, f"http://127.0.0.1:{origin.server_port}/")[0], 403)
        self.assertEqual(len(origin.hits), 1)

    def test_connect_forwards_matching_hello_and_bytes(self):
        echo = self.server(Echo)
        port = echo.server_address[1]
        proxy, address = self.proxy([("localhost", port)])
        sock = self.tunnel(address, "localhost", port)
        data = client_hello("localhost") + b"tunnel-data"
        # Fragmented delivery also exercises exact-length socket reads.
        sock.sendall(data[:2])
        sock.sendall(data[2:])
        received = bytearray()
        while len(received) < len(data):
            received.extend(sock.recv(len(data) - len(received)))
        self.assertEqual(bytes(received), data)
        self.assertTrue(any(e["result"] == "tunnel_opened" for e in proxy.events))

    def test_connect_rejects_wrong_missing_sni_and_plaintext(self):
        echo = self.server(Echo)
        port = echo.server_address[1]
        proxy, address = self.proxy([("localhost", port)])
        for data in [client_hello("attacker.invalid"), client_hello(), b"GET / HTTP/1.1\r\n\r\n"]:
            sock = self.tunnel(address, "localhost", port)
            sock.sendall(data)
            self.assertEqual(sock.recv(1), b"")
            sock.close()
        self.assertEqual(echo.hits, [])
        self.assertEqual(sum(e["result"] == "tls_hello_rejected" for e in proxy.events), 3)

    def test_real_stdlib_tls_client_hello_is_forwarded(self):
        echo = self.server(Echo)
        port = echo.server_address[1]
        _, address = self.proxy([("localhost", port)])
        incoming, outgoing = ssl.MemoryBIO(), ssl.MemoryBIO()
        tls = ssl.create_default_context().wrap_bio(incoming, outgoing, server_hostname="localhost")
        with self.assertRaises(ssl.SSLWantReadError):
            tls.do_handshake()
        hello = outgoing.read()
        sock = self.tunnel(address, "localhost", port)
        sock.sendall(hello)
        self.assertEqual(proxy_module._read_exact(sock, len(hello)), hello)

    def test_stdlib_http10_connect_without_host(self):
        echo = self.server(Echo)
        port = echo.server_address[1]
        _, address = self.proxy([("localhost", port)])
        conn = http.client.HTTPConnection(*address, timeout=3)
        conn.set_tunnel("localhost", port)
        # Exercise stdlib's actual tunnel implementation with the wire format
        # emitted by Python 3.11; newer stdlib versions add Host automatically.
        conn._http_vsn = 10
        conn._http_vsn_str = "HTTP/1.0"
        conn._tunnel_headers.clear()
        try:
            conn.connect()
            hello = client_hello("localhost")
            conn.sock.sendall(hello)
            self.assertEqual(proxy_module._read_exact(conn.sock, len(hello)), hello)
        finally:
            conn.close()
        for version, headers in [
            ("HTTP/1.1", ""),
            ("HTTP/1.0", "Host: attacker.invalid\r\n"),
            ("HTTP/1.0", f"Host: localhost:{port}\r\nHost: localhost:{port}\r\n"),
        ]:
            request = f"CONNECT localhost:{port} {version}\r\n{headers}\r\n"
            self.assertTrue(self.raw(address, request.encode()).startswith(b"HTTP/1.1 400"))

    def test_ip_connect_without_sni_and_prompt_close(self):
        echo = self.server(Echo)
        port = echo.server_address[1]
        proxy, address = self.proxy([("127.0.0.1", port)])
        sock = self.tunnel(address, "127.0.0.1", port)
        data = client_hello()
        sock.sendall(data)
        self.assertEqual(proxy_module._read_exact(sock, len(data)), data)
        start = time.monotonic()
        proxy.close()
        self.assertLess(time.monotonic() - start, 2)
        self.assertEqual(sock.recv(1), b"")

    def test_connect_denied_before_any_upstream_connection(self):
        _, address = self.proxy([("localhost", 443)])
        for authority in ["localhost:444", "localhost.attacker.invalid:443", "user@localhost:443"]:
            with patch.object(proxy_module.socket, "create_connection", side_effect=AssertionError("unexpected upstream")):
                # Use a raw socket so the patched create_connection covers the proxy only.
                with socket.socket() as client:
                    client.settimeout(3)
                    client.connect(address)
                    client.sendall(f"CONNECT {authority} HTTP/1.1\r\nHost: {authority}\r\n\r\n".encode())
                    self.assertRegex(client.recv(100), rb"HTTP/1.1 (400|403)")


if __name__ == "__main__":
    unittest.main()
