# Codex CLI on top of the shared ELT agent image, for running Codex with a
# ChatGPT plan login (subscription) instead of an API key. The CLI runs inside
# the task container, so every tool it uses sees only /workspace.
FROM elt-swe

ARG CODEX_VERSION=0.160.0
ARG NODE_MAJOR=22

RUN apt-get update && apt-get install -y ca-certificates curl gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
       | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE_MAJOR}.x nodistro main" \
       > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update && apt-get install -y nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN npm install -g "@openai/codex@${CODEX_VERSION}" && codex --version

WORKDIR /workspace
CMD ["/bin/bash"]
