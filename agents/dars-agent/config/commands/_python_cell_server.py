#!/usr/bin/env python3

import sys
import os
import socket
import threading
import traceback
import contextlib
import io
from typing import Dict

# Path to the Unix domain socket
SOCKET_FILE = '/tmp/python_cell_socket'

def handle_client_connection(client_socket, namespace: Dict[str, any]):
    try:
        # Receive the length of the incoming code
        code_length_bytes = client_socket.recv(8)
        if not code_length_bytes:
            return
        code_length = int.from_bytes(code_length_bytes, byteorder='big')
        # Receive the actual code
        code = b''
        while len(code) < code_length:
            chunk = client_socket.recv(code_length - len(code))
            if not chunk:
                break
            code += chunk
        code = code.decode('utf-8')

        # Execute the code
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                exec(code, namespace)
            except Exception:
                traceback.print_exc()
        output = stdout.getvalue()
        errors = stderr.getvalue()

        # Prepare the response
        response = {
            'output': output,
            'errors': errors
        }
        response_bytes = pickle.dumps(response)
        # Send the length of the response
        client_socket.sendall(len(response_bytes).to_bytes(8, byteorder='big'))
        # Send the actual response
        client_socket.sendall(response_bytes)
    except Exception:
        traceback.print_exc()
    finally:
        client_socket.close()

def start_server():
    if os.path.exists(SOCKET_FILE):
        os.remove(SOCKET_FILE)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCKET_FILE)
    server.listen(1)
    print(f"Python cell server started and listening on {SOCKET_FILE}")

    # Use a persistent namespace
    namespace = {}

    try:
        while True:
            client_socket, _ = server.accept()
            client_handler = threading.Thread(
                target=handle_client_connection,
                args=(client_socket, namespace)
            )
            client_handler.start()
    except KeyboardInterrupt:
        print("Shutting down the server.")
    finally:
        server.close()
        if os.path.exists(SOCKET_FILE):
            os.remove(SOCKET_FILE)

if __name__ == '__main__':
    import pickle  # Ensure pickle is imported here
    start_server()
