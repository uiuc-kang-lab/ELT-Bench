"""`sweagent` CLI entry point that allows commands longer than five minutes.

SWE-ReX sends each session command over aiohttp without its own timeout, so aiohttp's
default client timeout (300 s total) caps every command regardless of
--agent.tools.execution_timeout. This launcher lifts that default for this process
only; the command timeout is then enforced by SWE-agent/SWE-ReX as configured.
"""
import sys

import aiohttp
import aiohttp.client

aiohttp.client.DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=None, sock_connect=30)

from sweagent.run.run import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
