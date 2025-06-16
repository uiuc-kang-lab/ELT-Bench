#!/usr/bin/env python3

import os
import time
import socket
import threading
import subprocess
import pickle
from typing import Optional
import shlex
import sys
import errno
import logging

SOCKET_FILE = '/tmp/bash_command_socket'
LOG_FILE = '/tmp/bash_server.log'

# Configure logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

process: Optional[subprocess.Popen] = None  # Track the single background process
process_lock = threading.Lock()  # Ensure thread-safe access to the process variable

def handle_client_connection(client_socket):
    global process
    try:
        # Receive the command length
        code_length_bytes = client_socket.recv(8)
        if not code_length_bytes:
            return
        code_length = int.from_bytes(code_length_bytes, byteorder='big')

        # Receive the actual command
        command_bytes = b''
        while len(command_bytes) < code_length:
            chunk = client_socket.recv(code_length - len(command_bytes))
            if not chunk:
                break
            command_bytes += chunk
        command = command_bytes.decode('utf-8').strip()

        response = {}

        if command == 'stop':
            with process_lock:
                if process and process.poll() is None:
                    process.terminate()
                    process.wait()
                    process = None  # Reset process reference after stopping it
                    response = {'output': "Process stopped.", 'errors': ''}
                    logging.info("Background process stopped.")
                else:
                    response = {'output': '', 'errors': 'No process is running currently.'}
        elif command == 'get_logs':
            if os.path.exists(LOG_FILE):
                try:
                    time.sleep(45)
                    with open(LOG_FILE, 'r') as f:
                        logs = ''.join(f.readlines()[-100:])
                    response = {'output': logs, 'errors': ''}
                except Exception as e:
                    response = {'output': '', 'errors': f'Error reading log file: {e}'}
            else:
                response = {'output': '', 'errors': 'Log file not found.'}
        else:
            with process_lock:
                if process and process.poll() is None:
                    process.terminate()
                    process.wait()
                    logging.info("Previous background process terminated.")

                try:
                    open(LOG_FILE, 'w').close()
                except Exception as e:
                    logging.error(f"Error clearing log file: {e}")

                command_args = shlex.split(command)
                if command_args[0] == 'python' or command_args[0].endswith('python'):
                    command_args.insert(1, '-u')

                env = os.environ.copy()
                env['PYTHONUNBUFFERED'] = '1'

                try:
                    process = subprocess.Popen(
                        command_args,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        bufsize=1,
                        universal_newlines=True,
                        env=env
                    )

                    collected_output = []

                    def log_output():
                        start_time = time.time()
                        while time.time() - start_time < 45:
                            line = process.stdout.readline()
                            if line:
                                line = line.strip()
                                collected_output.append(line)
                                logging.info(f"[Process Output] {line}")
                            if process.poll() is not None:
                                break

                    logging_thread = threading.Thread(target=log_output)
                    logging_thread.start()
                    logging_thread.join(45)

                    output = "\n".join(collected_output)
                    if process.poll() is None:
                        threading.Thread(target=log_subprocess_output, args=(process,)).start()
                        response = {'output': f"Process started: {command}\n\nInitial logs:\n{output}", 'errors': ''}
                        logging.info(f"Started background process: {command}")
                    else:
                        response = {'output': output, 'errors': ''}
                        logging.info(f"Process completed within 45 seconds with output:\n{output}")

                except Exception as e:
                    response = {'output': '', 'errors': f'Error starting process: {e}'}
                    logging.error(f"Error starting process '{command}': {e}")

        # Send response back to the client
        response_bytes = pickle.dumps(response)
        client_socket.sendall(len(response_bytes).to_bytes(8, byteorder='big'))
        client_socket.sendall(response_bytes)

    except Exception as e:
        logging.error(f"Error in handle_client_connection: {e}")
    finally:
        client_socket.close()

def log_subprocess_output(proc):
    """Read subprocess output and write to the log file."""
    try:
        for line in iter(proc.stdout.readline, ''):
            if line:
                line = line.rstrip()
                logging.info(f"[Process Output] {line}")
            else:
                break
    except Exception as e:
        logging.error(f"Error in log_subprocess_output: {e}")

def start_server():
    if os.path.exists(SOCKET_FILE):
        os.remove(SOCKET_FILE)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCKET_FILE)
    server.listen(5)
    logging.info(f"Bash command server started and listening on {SOCKET_FILE}")

    try:
        while True:
            client_socket, _ = server.accept()
            client_handler = threading.Thread(target=handle_client_connection, args=(client_socket,))
            client_handler.daemon = True
            client_handler.start()
    except Exception as e:
        logging.error(f"Server error: {e}")
    finally:
        server.close()
        if os.path.exists(SOCKET_FILE):
            os.remove(SOCKET_FILE)
        logging.info("Server shutdown.")

if __name__ == '__main__':
    start_server()
