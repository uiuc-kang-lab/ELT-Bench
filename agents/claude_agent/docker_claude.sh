#!/bin/sh
# Runs the Claude Code CLI inside the task container. The Python SDK spawns
# this script in place of a local `claude` binary and talks to it over stdin
# and stdout, so every tool the CLI offers executes inside the container.
if [ -z "$CLAUDE_CONTAINER" ]; then
  echo "docker_claude.sh: CLAUDE_CONTAINER is not set" >&2
  exit 1
fi
exec docker exec -i -w /workspace "$CLAUDE_CONTAINER" claude "$@"
