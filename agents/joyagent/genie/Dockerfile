# JoyAgent-JDGenie (github.com/jd-opensource/joyagent-jdgenie, main branch)
# for ELT-Bench: genie-backend (Java, :8080), genie-tool (:1601) and
# genie-client (MCP client, :8188); the web UI is not needed. The upstream
# source is patched only where ELT-Bench needs it (joyagent-elt.patch).
#   docker build -t joyagent-genie agents/joyagent/genie
ARG JOYAGENT_COMMIT=3cc29a638f0e7a3274a52f16c8ff38a7573a042d

FROM maven:3.9-eclipse-temurin-17 AS backend
ARG JOYAGENT_COMMIT
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN git init -q . \
    && git remote add origin https://github.com/jd-opensource/joyagent-jdgenie.git \
    && git fetch -q --depth 1 origin "${JOYAGENT_COMMIT}" \
    && git checkout -q FETCH_HEAD
COPY joyagent-elt.patch /tmp/joyagent-elt.patch
RUN git apply /tmp/joyagent-elt.patch
RUN cd genie-backend && mvn -q -B clean package -DskipTests

FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
        openjdk-17-jre-headless curl \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.12.20

COPY --from=backend /src/genie-backend/target/genie-backend /app/backend
COPY --from=backend /src/genie-tool /app/genie-tool
COPY --from=backend /src/genie-client /app/genie-client
ENV UV_PROJECT_ENVIRONMENT=.venv UV_LINK_MODE=copy
RUN cd /app/genie-tool && uv sync --frozen --no-dev \
    && cd /app/genie-client && uv sync --frozen --no-dev \
    && chmod -R a+rX /app

COPY entrypoint.sh /app/entrypoint.sh
EXPOSE 8080
ENTRYPOINT ["/bin/sh", "/app/entrypoint.sh"]
