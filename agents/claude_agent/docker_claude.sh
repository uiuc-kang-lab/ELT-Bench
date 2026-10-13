#!/bin/sh
# Runs the Claude Code CLI inside the task container. The Python SDK spawns
# this script in place of a local `claude` binary and talks to it over stdin
# and stdout, so every tool the CLI offers executes inside the container.
if [ -z "$CLAUDE_CONTAINER" ]; then
  echo "docker_claude.sh: CLAUDE_CONTAINER is not set" >&2
  exit 1
fi
# Forward the variables the SDK sets on the CLI process (by name, so values
# are taken from this process's environment and only when set).
exec docker exec -i -w /workspace \
  -e CLAUDE_CODE_ENTRYPOINT -e CLAUDE_AGENT_SDK_VERSION \
  -e CLAUDE_CODE_SDK_READS_SESSION_STATE \
  "$CLAUDE_CONTAINER" claude "$@"
