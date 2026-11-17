#!/bin/sh
# Start genie-tool and genie-client, wait until both answer, then run the
# backend in the foreground. Per-run settings (model, MCP server, step
# limits) come from /config/override.yml, written by agents/joyagent/run.py.
set -e
LOG_DIR="${GENIE_LOG_DIR:-/tmp/genie-logs}"
STATE_DIR="${GENIE_STATE_DIR:-/tmp/genie-state}"
mkdir -p "$LOG_DIR" "$STATE_DIR"

# genie-tool serves file_tool (files are kept in SQLite + a local directory).
cd /app/genie-tool
ENV=prod LOG_PATH="$LOG_DIR/genie-tool.log" \
    FILE_SAVE_PATH="$STATE_DIR/file_db_dir" SQLITE_DB_PATH="$STATE_DIR/autobots.db" \
    FILE_SERVER_URL=http://127.0.0.1:1601/v1/file_tool \
    .venv/bin/python server.py --workers 1 > "$LOG_DIR/genie-tool.out" 2>&1 &

cd /app/genie-client
LOG_DIR="$LOG_DIR/genie-client" .venv/bin/python server.py > "$LOG_DIR/genie-client.out" 2>&1 &

for url in http://127.0.0.1:8188/health http://127.0.0.1:1601/docs; do
  i=0
  until curl -sf -o /dev/null "$url"; do
    i=$((i + 1))
    if [ "$i" -gt 120 ]; then echo "service not ready: $url" >&2; exit 1; fi
    sleep 1
  done
done

cd /app/backend
exec java -classpath "conf/:lib/*" -Dbasedir=/app/backend -Dfile.encoding=UTF-8 \
  com.jd.genie.GenieApplication \
  --spring.config.additional-location=file:/config/override.yml
