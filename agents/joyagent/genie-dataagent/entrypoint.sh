#!/bin/sh
# Start genie-tool and genie-client, wait until both answer, then run the
# backend in the foreground. Per-run settings (model, MCP server, step limits,
# the data agent's warehouse connection) come from /config/override.yml,
# written by agents/joyagent/run.py --variant dataagent.
#
# Unlike the main branch, genie-tool calls the LLM itself here (NL2SQL, table
# RAG, analysis, report). Those calls go to the runner's proxy:
# GENIE_LLM_BASE_URL (OpenAI-compatible, ending in /v1) and GENIE_LLM_MODEL.
set -e
LOG_DIR="${GENIE_LOG_DIR:-/tmp/genie-logs}"
STATE_DIR="${GENIE_STATE_DIR:-/tmp/genie-state}"
mkdir -p "$LOG_DIR" "$STATE_DIR"
: "${GENIE_LLM_BASE_URL:?set by run.py}" "${GENIE_LLM_MODEL:?set by run.py}"
# litellm's provider prefix for an OpenAI-compatible endpoint
M="openai/$GENIE_LLM_MODEL"

cd /app/genie-tool
(
export ENV=prod LOG_PATH="$LOG_DIR/genie-tool.log" \
    FILE_SAVE_PATH="$STATE_DIR/file_db_dir" SQLITE_DB_PATH="$STATE_DIR/autobots.db" \
    FILE_SERVER_URL=http://127.0.0.1:1601/v1/file_tool \
    OPENAI_BASE_URL="$GENIE_LLM_BASE_URL" OPENAI_API_KEY=set-by-proxy \
    DEFAULT_MODEL="$M" NL2SQL_MODEL_NAME="$M" REWRITE_MODEL_NAME="$M" THINK_MODEL_NAME="$M" \
    TR_EXTRACT_SYS_WSD_MODEL_NAME="$M" TR_TABLE_FILTER_MODEL_NAME="$M" TR_COLUMN_FILTER_MODEL_NAME="$M" \
    REPORT_MODEL="$M" CAL_ENGINE_MODEL="$M" CODE_INTEPRETER_MODEL="$M" \
    ANALYSIS_MODEL="$GENIE_LLM_MODEL" \
    ANA_SCHEMA_URL=http://127.0.0.1:8080/data/queryModelInfo \
    ANA_DATA_URL=http://127.0.0.1:8080/data/apiChatQuery
# The file table, as in upstream's setup (python -m genie_tool.db.db_engine).
.venv/bin/python -m genie_tool.db.db_engine > "$LOG_DIR/genie-tool-initdb.out" 2>&1
exec .venv/bin/python server.py --workers 1 > "$LOG_DIR/genie-tool.out" 2>&1
) &

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

# --add-opens: the Snowflake JDBC driver's Arrow reader needs java.nio.
cd /app/backend
exec java --add-opens=java.base/java.nio=ALL-UNNAMED \
  -classpath "conf/:lib/*" -Dbasedir=/app/backend -Dfile.encoding=UTF-8 \
  com.jd.genie.GenieApplication \
  --spring.config.additional-location=file:/config/override.yml
