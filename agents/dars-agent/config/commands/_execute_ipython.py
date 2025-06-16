#!/usr/bin/env python3

# @yaml
# signature: execute_ipython $<code>
# docstring: Executes Python code in a persistent cell, returning its output. Variables persist between executions.
# arguments:
#   code:
#       type: string
#       description: Python code to execute in the cell.
#       required: true

import sys
import os
import argparse
import socket
import pickle

# Path to the Unix domain socket
SOCKET_FILE = '/tmp/python_cell_socket'

def start_server_process():
    """Start the server process if it's not already running."""
    import subprocess
    import time
    server_script = 'python_cell_server'

    try:
        # Start the server script directly, assuming it's in the PATH
        subprocess.Popen([server_script])
    except FileNotFoundError:
        print(f"Error: Server script '{server_script}' not found in PATH.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error starting server process: {e}", file=sys.stderr)
        sys.exit(1)

    # Wait a moment for the server to start
    time.sleep(0.5)

def send_code_to_server(code: str):
    """Send code to the server and get the output."""
    # Ensure the server is running
    if not os.path.exists(SOCKET_FILE):
        start_server_process()

    # Connect to the server
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.connect(SOCKET_FILE)
    except socket.error as e:
        print(f"Error connecting to server: {e}", file=sys.stderr)
        sys.exit(1)

    # Send the length of the code
    code_bytes = code.encode('utf-8')
    client.sendall(len(code_bytes).to_bytes(8, byteorder='big'))
    # Send the actual code
    client.sendall(code_bytes)

    # Receive the length of the response
    response_length_bytes = client.recv(8)
    if not response_length_bytes:
        print("No response from server.", file=sys.stderr)
        sys.exit(1)
    response_length = int.from_bytes(response_length_bytes, byteorder='big')
    # Receive the actual response
    response_bytes = b''
    while len(response_bytes) < response_length:
        chunk = client.recv(response_length - len(response_bytes))
        if not chunk:
            break
        response_bytes += chunk
    response = pickle.loads(response_bytes)
    client.close()
    return response

def format_output(output: str, errors: str) -> None:
    """Format and print the output from the cell execution."""
    if output.strip():
        print("Output:")
        print("-" * 50)
        print(output.rstrip())
        
    if errors.strip():
        print("\nErrors:", file=sys.stderr)
        print("-" * 50, file=sys.stderr)
        print(errors.rstrip(), file=sys.stderr)

def main():
    # Set up argument parser to take code as a command-line argument
    parser = argparse.ArgumentParser(
        description="Executes Python code in a persistent cell."
    )
    parser.add_argument(
        "code", 
        type=str, 
        nargs='?', 
        help="The Python code to execute in the cell. If not provided, reads from stdin."
    )
    args = parser.parse_args()
    
    if args.code:
        code = args.code
    else:
        # Read code from stdin
        code = sys.stdin.read()
    
    # Check if the provided code is empty or only contains whitespace
    if not code.strip():
        print("Error: 'code' must not be empty.")
        print("Usage: execute_ipython $<code>")
        sys.exit(1)
    
    # Send the code to the server and get the response
    response = send_code_to_server(code)
    output = response.get('output', '')
    errors = response.get('errors', '')

    # Format and display the output
    format_output(output, errors)
    
    # Exit with error code if there were any errors
    if errors.strip():
        sys.exit(1)

if __name__ == '__main__':
    main()
