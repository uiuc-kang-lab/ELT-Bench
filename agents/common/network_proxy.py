"""A small, default-deny HTTP proxy for a kernel-isolated agent container.

This is not a sandbox by itself: the runner must prevent direct egress and must
keep this host-side process inaccessible to the agent. HTTPS is tunneled, not
decrypted. A DNS CONNECT target requires a matching TLS ClientHello SNI; this
does not inspect encrypted HTTP Host headers or prevent all domain fronting.
Encrypted ClientHello without a visible matching SNI fails closed.

Requests use Content-Length (chunked request bodies are rejected), at most
32 MiB. Plain HTTP responses are capped at 128 MiB; CONNECT streams have a
five-minute idle timeout. Credentials and request/response contents are never
logged. Redirects are returned to the client, never followed by this proxy.
"""

from __future__ import annotations

import http.client
import ipaddress
import re
import select
import socket
import threading
import time
from collections.abc import Iterable, Mapping
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

MAX_HEADERS = 64 * 1024
MAX_BODY = 32 * 1024 * 1024
MAX_RESPONSE = 128 * 1024 * 1024
MAX_HELLO = 64 * 1024
MAX_EVENTS = 1000
MAX_CONNECTIONS = 64
IO_TIMEOUT = 30
# Airbyte discovery and connection creation can wait for cold worker/image
# startup. Keep connection/client/upload timeouts short, but allow an upstream
# HTTP response ten minutes of read inactivity. close() still shuts down the
# tracked socket immediately, including while getresponse() is waiting.
HTTP_RESPONSE_TIMEOUT = 600
TUNNEL_IDLE_TIMEOUT = 300
_TOKEN = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
_HOP_HEADERS = {
    "connection", "proxy-connection", "keep-alive", "transfer-encoding",
    "te", "trailer", "upgrade", "proxy-authorization", "proxy-authenticate",
}


def _host(value: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("invalid host")
    try:
        return ipaddress.ip_address(value).compressed
    except ValueError:
        pass
    if len(value) > 253 or not value.isascii() or value.endswith("."):
        raise ValueError("invalid host")
    if re.fullmatch(r"[0-9.]+", value):
        raise ValueError("invalid IP address")
    labels = value.lower().split(".")
    if any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", s) for s in labels):
        raise ValueError("invalid host")
    return ".".join(labels)


def _port(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 65535:
        raise ValueError("invalid port")
    return value


def _authority(value: str, default_port: int | None = None) -> tuple[str, int]:
    if not value or any(c in value for c in "/?#@\\") or any(ord(c) <= 32 for c in value):
        raise ValueError("invalid authority")
    parsed = urlsplit("//" + value)
    host = _host(parsed.hostname or "")
    port = parsed.port
    if port is None:
        if default_port is None or value.endswith(":"):
            raise ValueError("explicit port required")
        port = default_port
    return host, _port(port)


def _display_authority(host: str, port: int) -> str:
    return f"[{host}]:{port}" if ":" in host else f"{host}:{port}"


class _HeaderBudget:
    def __init__(self, stream):
        self.stream = stream
        self.remaining = MAX_HEADERS

    def readline(self, limit=-1):
        size = min(limit, self.remaining + 1) if limit >= 0 else self.remaining + 1
        line = self.stream.readline(size)
        self.remaining -= len(line)
        if self.remaining < 0:
            raise http.client.LineTooLong("header block")
        return line


class _BoundedResponse(http.client.HTTPResponse):
    def begin(self):
        original = self.fp
        self.fp = _HeaderBudget(original)
        try:
            super().begin()
        finally:
            self.fp = original


class _ProxyServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False

    def __init__(self, *args, **kwargs):
        self._slots = threading.BoundedSemaphore(MAX_CONNECTIONS)
        super().__init__(*args, **kwargs)

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            self.proxy._event(None, None, "INVALID", False, "connection_limit")
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()

    def handle_error(self, request, client_address):
        # No traceback or request context in server stderr.
        self.proxy._event(None, None, "INVALID", False, "handler_error")


def _read_exact(stream: socket.socket, length: int) -> bytes:
    result = bytearray()
    while len(result) < length:
        part = stream.recv(length - len(result))
        if not part:
            raise ValueError("incomplete TLS hello")
        result.extend(part)
    return bytes(result)


def _client_hello(stream: socket.socket) -> tuple[bytes, str | None]:
    """Read bounded TLS handshake records and extract the first ClientHello SNI."""
    wire, handshake = bytearray(), bytearray()
    while True:
        header = _read_exact(stream, 5)
        length = int.from_bytes(header[3:5], "big")
        if header[0] != 22 or header[1] != 3 or not 1 <= length <= 18432:
            raise ValueError("TLS ClientHello required")
        if len(wire) + length + 5 > MAX_HELLO:
            raise ValueError("TLS hello too large")
        payload = _read_exact(stream, length)
        wire.extend(header + payload)
        handshake.extend(payload)
        if len(handshake) >= 4:
            total = 4 + int.from_bytes(handshake[1:4], "big")
            if handshake[0] != 1 or total > MAX_HELLO:
                raise ValueError("TLS ClientHello required")
            if len(handshake) >= total:
                break
    body = bytes(handshake[4:total])
    offset = 0

    def take(n: int) -> bytes:
        nonlocal offset
        if offset + n > len(body):
            raise ValueError("malformed ClientHello")
        result = body[offset:offset + n]
        offset += n
        return result

    take(34)  # legacy_version and random
    session_length = take(1)[0]
    if session_length > 32:
        raise ValueError("malformed session ID")
    take(session_length)
    cipher_length = int.from_bytes(take(2), "big")
    if cipher_length < 2 or cipher_length % 2:
        raise ValueError("malformed cipher list")
    take(cipher_length)
    compression_length = take(1)[0]
    if not compression_length:
        raise ValueError("malformed compression list")
    take(compression_length)
    if offset == len(body):
        return bytes(wire), None
    extension_length = int.from_bytes(take(2), "big")
    if offset + extension_length != len(body):
        raise ValueError("malformed extensions")
    seen, sni = set(), None
    while offset < len(body):
        kind = int.from_bytes(take(2), "big")
        data = take(int.from_bytes(take(2), "big"))
        if kind in seen:
            raise ValueError("duplicate extension")
        seen.add(kind)
        if kind != 0:
            continue
        if len(data) < 5 or int.from_bytes(data[:2], "big") != len(data) - 2:
            raise ValueError("malformed SNI")
        if data[2] != 0 or int.from_bytes(data[3:5], "big") != len(data) - 5:
            raise ValueError("exactly one host_name required")
        sni = _host(data[5:].decode("ascii"))
    return bytes(wire), sni


class RestrictedProxy:
    def __init__(self, allowed_endpoints: Iterable[tuple[str, int]], bind_host: str,
                 allowed_client_ip: str | None = None,
                 host_address_map: Mapping[str, str] | None = None):
        self.allowed_endpoints = frozenset((_host(h), _port(p)) for h, p in allowed_endpoints)
        # Trusted runner-supplied Docker DNS replacements. These affect routing,
        # never authorization, HTTP Host or TLS SNI validation.
        self._host_address_map = {
            _host(name): str(ipaddress.ip_address(address))
            for name, address in (host_address_map or {}).items()
        }
        self.bind_host = str(ipaddress.ip_address(bind_host))
        self.events: list[dict] = []
        self._lock = threading.Lock()
        self._sockets: set[socket.socket] = set()
        self._closing = threading.Event()
        self._server = None
        self._thread = None
        self._client_ip = None
        self.set_allowed_client_ip(allowed_client_ip)

    def set_allowed_client_ip(self, ip: str | None) -> None:
        value = str(ipaddress.ip_address(ip)) if ip is not None else None
        with self._lock:
            self._client_ip = value

    def _client_allowed(self, ip: str) -> bool:
        with self._lock:
            return self._client_ip is None or str(ipaddress.ip_address(ip)) == self._client_ip

    def _event(self, host, port, method, allowed: bool, result: str):
        # Deliberately do not add paths, URLs, bodies, headers or exceptions here.
        with self._lock:
            self.events.append({"host": host, "port": port, "method": method,
                                "allowed": allowed, "result": result})
            del self.events[:-MAX_EVENTS]

    def _track(self, sock, add=True):
        with self._lock:
            if add:
                if self._closing.is_set():
                    sock.close()
                    raise OSError("proxy is closing")
                self._sockets.add(sock)
            else:
                self._sockets.discard(sock)

    def start(self) -> str:
        if self._server is None:
            if self._closing.is_set():
                raise RuntimeError("proxy is closed")
            family = socket.AF_INET6 if ":" in self.bind_host else socket.AF_INET
            server_type = type("ProxyServer", (_ProxyServer,), {"address_family": family})
            self._server = server_type((self.bind_host, 0), _Handler)
            self._server.proxy = self
            self._thread = threading.Thread(target=self._server.serve_forever,
                                            kwargs={"poll_interval": 0.1}, daemon=True)
            self._thread.start()
        return "http://" + _display_authority(self.bind_host, self._server.server_port)

    def close(self):
        self._closing.set()
        with self._lock:
            sockets = tuple(self._sockets)
        for sock in sockets:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    rbufsize = 0  # CONNECT must not lose TLS bytes in a buffered HTTP reader.

    @property
    def proxy(self):
        return self.server.proxy

    def setup(self):
        self.request.settimeout(IO_TIMEOUT)
        super().setup()
        self.proxy._track(self.connection)

    def finish(self):
        try:
            super().finish()
        finally:
            self.proxy._track(self.connection, False)

    def log_message(self, *_args):
        pass

    def send_error(self, code, message=None, explain=None):
        # BaseHTTPRequestHandler's default error page can echo request text.
        phrase = HTTPStatus(code).phrase
        body = (phrase + "\n").encode("ascii")
        self.send_response(code, phrase)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        if getattr(self, "command", None) != "HEAD":
            self.wfile.write(body)
        self.close_connection = True

    def handle_one_request(self):
        try:
            self.raw_requestline = self.rfile.readline(8193)
            if len(self.raw_requestline) > 8192:
                self.requestline = self.request_version = self.command = ""
                self.send_error(414)
                self.proxy._event(None, None, "INVALID", False, "request_line_too_large")
                return
            if not self.raw_requestline:
                self.close_connection = True
                return
            original = self.rfile
            self.rfile = _HeaderBudget(original)
            try:
                valid = self.parse_request()
            finally:
                self.rfile = original
            self.close_connection = True
            if not valid:
                self.proxy._event(None, None, "INVALID", False, "invalid_headers")
                return
            if not self.proxy._client_allowed(self.client_address[0]):
                self.proxy._event(None, None, "INVALID", False, "client_denied")
                self.send_error(403)
                return
            if self.command not in {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "CONNECT"}:
                self.proxy._event(None, None, "INVALID", False, "method_denied")
                self.send_error(405)
                return
            self._dispatch()
        except (OSError, ValueError, http.client.HTTPException):
            self.close_connection = True

    def handle_expect_100(self):
        return True  # Send only after checking the ACL and body length.

    def _target(self):
        hosts = self.headers.get_all("Host", [])
        # Python <= 3.11 http.client/urllib uses HTTP/1.0 CONNECT without Host.
        # Its authority-form request target is sufficient for the same ACL.
        legacy_connect = self.command == "CONNECT" and self.request_version == "HTTP/1.0"
        if len(hosts) != 1 and not (legacy_connect and not hosts):
            raise ValueError("exactly one Host required")
        for name, value in self.headers.items():
            if not _TOKEN.fullmatch(name) or any(ord(c) < 32 and c != "\t" or ord(c) == 127 for c in value):
                raise ValueError("invalid header")
        if self.command == "CONNECT":
            target = _authority(self.path)
            if hosts and _authority(hosts[0], target[1]) != target:
                raise ValueError("conflicting Host")
            return *target, None
        uri = urlsplit(self.path)
        if uri.scheme.lower() != "http" or not uri.netloc or uri.fragment:
            raise ValueError("absolute HTTP URI required")
        target = _authority(uri.netloc, 80)
        if _authority(hosts[0], 80) != target:
            raise ValueError("conflicting Host")
        path = uri.path or "/"
        if uri.query:
            path += "?" + uri.query
        return *target, path

    def _dispatch(self):
        try:
            host, port, path = self._target()
            lengths = self.headers.get_all("Content-Length", [])
            if self.headers.get_all("Transfer-Encoding") or len(lengths) > 1:
                raise ValueError("ambiguous body framing")
            if lengths and (not re.fullmatch(r"[0-9]{1,10}", lengths[0])):
                raise ValueError("invalid content length")
            length = int(lengths[0]) if lengths else 0
            if self.command == "CONNECT" and length:
                raise ValueError("CONNECT request body forbidden")
            if self.headers.get("Expect", "").lower() not in {"", "100-continue"}:
                raise ValueError("unsupported expectation")
        except (ValueError, UnicodeError):
            self.proxy._event(None, None, self.command, False, "invalid_request")
            self.send_error(400)
            return
        if (host, port) not in self.proxy.allowed_endpoints:
            self.proxy._event(host, port, self.command, False, "endpoint_denied")
            self.send_error(403)
            return
        if length > MAX_BODY:
            self.proxy._event(host, port, self.command, False, "body_too_large")
            self.send_error(413)
            return
        if self.command == "CONNECT":
            self._connect(host, port)
            return
        if self.headers.get("Expect", "").lower() == "100-continue":
            self.send_response_only(100)
            self.end_headers()
        self._forward(host, port, path, length)

    def _connect(self, host, port):
        self.send_response(200, "Connection Established")
        self.end_headers()
        upstream = None
        try:
            hello, sni = _client_hello(self.connection)
            try:
                ipaddress.ip_address(host)
                is_ip = True
            except ValueError:
                is_ip = False
            if (sni is None and not is_ip) or (sni is not None and sni != host):
                raise ValueError("SNI mismatch")
            address = self.proxy._host_address_map.get(host, host)
            upstream = socket.create_connection((address, port), timeout=IO_TIMEOUT)
            self.proxy._track(upstream)
            upstream.sendall(hello)
            self.proxy._event(host, port, "CONNECT", True, "tunnel_opened")
            sockets = [self.connection, upstream]
            last_activity = time.monotonic()
            while not self.proxy._closing.is_set():
                ready, _, _ = select.select(sockets, [], [], 1)
                if not ready:
                    if time.monotonic() - last_activity > TUNNEL_IDLE_TIMEOUT:
                        break
                    continue
                for source in ready:
                    data = source.recv(65536)
                    if not data:
                        return
                    target = upstream if source is self.connection else self.connection
                    target.sendall(data)
                    last_activity = time.monotonic()
        except (ValueError, UnicodeError):
            self.proxy._event(host, port, "CONNECT", False, "tls_hello_rejected")
        except OSError:
            self.proxy._event(host, port, "CONNECT", True, "connection_error")
        finally:
            if upstream is not None:
                self.proxy._track(upstream, False)
                upstream.close()

    def _forward(self, host, port, path, length):
        address = self.proxy._host_address_map.get(host, host)
        upstream = http.client.HTTPConnection(address, port, timeout=IO_TIMEOUT)
        upstream.response_class = _BoundedResponse
        tracked = None
        sent = False
        try:
            body_parts, remaining = [], length
            while remaining:
                part = self.rfile.read(min(remaining, 65536))
                if not part:
                    raise ValueError("incomplete request body")
                body_parts.append(part)
                remaining -= len(part)
            body = b"".join(body_parts)
            upstream.connect()
            tracked = upstream.sock
            self.proxy._track(tracked)
            upstream.putrequest(self.command, path, skip_host=True, skip_accept_encoding=True)
            blocked = _HOP_HEADERS | {s.strip().lower() for s in self.headers.get("Connection", "").split(",")}
            for name, value in self.headers.items():
                if name.lower() not in blocked | {"host", "content-length", "expect"}:
                    upstream.putheader(name, value)
            upstream.putheader("Host", _display_authority(host, port))
            upstream.putheader("Connection", "close")
            if length or "Content-Length" in self.headers:
                upstream.putheader("Content-Length", str(length))
            upstream.endheaders(body)
            tracked.settimeout(HTTP_RESPONSE_TIMEOUT)
            response = upstream.getresponse()
            if response.status < 200 or response.status > 599:
                raise ValueError("unsupported upstream status")
            if response.length is not None and response.length > MAX_RESPONSE:
                raise ValueError("upstream body too large")
            blocked_response = _HOP_HEADERS | {s.strip().lower() for s in response.getheader("Connection", "").split(",")} | {"content-length"}
            headers = [(name, value) for name, value in response.getheaders() if name.lower() not in blocked_response]
            for name, value in headers:
                if not _TOKEN.fullmatch(name) or any(ord(c) < 32 and c != "\t" or ord(c) == 127 for c in value):
                    raise ValueError("invalid upstream header")
            self.send_response(response.status)
            for name, value in headers:
                self.send_header(name, value)
            self.send_header("Connection", "close")
            self.end_headers()
            sent = True
            total = 0
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_RESPONSE:
                    raise ValueError("upstream body too large")
                self.wfile.write(chunk)
            self.proxy._event(host, port, self.command, True, "response_forwarded")
        except (OSError, ValueError, http.client.HTTPException):
            self.proxy._event(host, port, self.command, True, "forwarding_error")
            if not sent:
                self.send_error(502)
        finally:
            if tracked is not None:
                self.proxy._track(tracked, False)
            upstream.close()
