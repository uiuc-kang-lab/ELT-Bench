# Task container for JoyAgent: the shared ELT agent image plus an MCP server
# (mcp_workspace_server.py) that gives JoyAgent's executor shell and file
# tools inside /workspace. The server has its own virtualenv, so the Python
# environment the agent uses for dbt and scripts is the same as for the
# other agents.
#   docker build -t elt-swe-joyagent agents/joyagent/elt-swe-joyagent
FROM elt-swe

# Same versions as JoyAgent's genie-client (its uv.lock); mcp 1.9.4 fails to
# import with newer pydantic releases.
RUN python -m venv /opt/joyagent/venv \
    && /opt/joyagent/venv/bin/pip install --no-cache-dir \
        mcp==1.9.4 pydantic==2.11.7 pydantic-core==2.33.2 pydantic-settings==2.9.1 \
        anyio==4.9.0 httpx==0.28.1 sse-starlette==2.3.6 starlette==0.46.2 uvicorn==0.34.3

COPY mcp_workspace_server.py /opt/joyagent/mcp_workspace_server.py

WORKDIR /workspace
CMD ["/opt/joyagent/venv/bin/python", "/opt/joyagent/mcp_workspace_server.py", "--host", "0.0.0.0", "--port", "8000"]
