#!/usr/bin/env python3

# @yaml
# signature: execute_server <command>
# docstring: To run long-lived processes such as server or daemon. It runs the command in the background and provides a log of the output.
# arguments:
#   command:
#       type: string
#       description: Bash command to execute in the shell.
#       required: true
# special_commands:
#   - get_logs: Retrieves the last 100 lines of the server log.
#   - stop: Stops the background Bash server process.

import sys
import os
import argparse
import socket
import pickle
import errno

SOCKET_FILE = '/tmp/bash_command_socket'

def start_server_process():
    """Start the Bash server process if it's not already running."""
    import subprocess
    import time
    server_script = 'bash_server'

    try:
        subprocess.Popen([server_script])
    except FileNotFoundError:
        print(f"Error: Server script '{server_script}' not found in PATH.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error starting server process: {e}", file=sys.stderr)
        sys.exit(1)

    # Wait for the server to start
    timeout = 5  # seconds
    start_time = time.time()
    while not os.path.exists(SOCKET_FILE):
        if time.time() - start_time > timeout:
            print("Error: Server did not start within expected time.", file=sys.stderr)
            sys.exit(1)
        time.sleep(0.1)

def send_command_to_server(command: str):
    """Send a command to the server and get the output."""
    if not os.path.exists(SOCKET_FILE):
        start_server_process()

    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.connect(SOCKET_FILE)
    except socket.error as e:
        if e.errno in (errno.ENOENT, errno.ECONNREFUSED):
            print("Server not running, starting server...")
            start_server_process()
            try:
                client.connect(SOCKET_FILE)
            except socket.error as e:
                print(f"Error connecting to server after restart: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            print(f"Error connecting to server: {e}", file=sys.stderr)
            sys.exit(1)

    try:
        # Send the command
        command_bytes = command.encode('utf-8')
        client.sendall(len(command_bytes).to_bytes(8, byteorder='big'))
        client.sendall(command_bytes)

        # Receive the response length
        response_length_bytes = client.recv(8)
        if not response_length_bytes:
            print("No response from server.", file=sys.stderr)
            sys.exit(1)
        response_length = int.from_bytes(response_length_bytes, byteorder='big')

        # Read the response
        response_bytes = b''
        while len(response_bytes) < response_length:
            chunk = client.recv(min(response_length - len(response_bytes), 4096))
            if not chunk:
                break
            response_bytes += chunk
        response = pickle.loads(response_bytes)
        client.close()
        return response
    except Exception as e:
        print(f"Error during communication with server: {e}", file=sys.stderr)
        client.close()
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Executes Bash commands through a persistent server."
    )
    parser.add_argument(
        "command",
        type=str,
        help="The Bash command to execute, or 'stop'/'get_logs' for special commands."
    )
    args = parser.parse_args()

    # Send the command to the server
    response = send_command_to_server(args.command)
    output = response.get('output', '')
    errors = response.get('errors', '')

    if output.strip():
        print("Output:")
        print("-" * 50)
        print(output.rstrip())

    if errors.strip():
        print("\nErrors:", file=sys.stderr)
        print("-" * 50, file=sys.stderr)
        print(errors.rstrip(), file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()