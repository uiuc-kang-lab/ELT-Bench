# Claude Code CLI on top of the shared ELT agent image. With the CLI inside the
# container, every tool it offers (Bash, Read, Write, Glob, Grep) runs in the
# container and sees only /workspace, the same containment the OpenHands and
# Codex runners already have.
FROM elt-swe

ARG CLAUDE_CODE_VERSION=2.1.282
ARG NODE_MAJOR=22

RUN apt-get update && apt-get install -y ca-certificates curl gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
       | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE_MAJOR}.x nodistro main" \
       > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update && apt-get install -y nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN npm install -g "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
    && claude --version

WORKDIR /workspace
CMD ["/bin/bash"]
