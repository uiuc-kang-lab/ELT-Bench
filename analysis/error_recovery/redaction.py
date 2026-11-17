"""Additional redaction for subprocess argument lists in rerun tool observations."""
import re
from sanitize_text import redact as base_redact
BASIC_LIST=re.compile(r'''(?i)(["'](?:-u|--user)["']\s*,\s*)["'][^"'\n]*:[^"'\n]*["']''')
SECRET_LIST=re.compile(r'''(?i)(["']--(?:password|token|api-key|secret)["']\s*,\s*)["'][^"'\n]*["']''')
def redact(s):
 s=BASIC_LIST.sub(r"\1'[REDACTED_BASIC_AUTH]'",s)
 s=SECRET_LIST.sub(r"\1'[REDACTED]'",s)
 return base_redact(s)
