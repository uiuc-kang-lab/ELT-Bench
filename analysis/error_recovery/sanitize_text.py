"""Conservative credential redaction for saved audit copies; raw trajectories stay untouched."""
import re
ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
CREDENTIAL = re.compile(r'''(?im)(["']?(?:[\w]*password|api_key|client_secret|access_key_id|secret_access_key|secret_key|token)["']?\s*[:=]\s*)(?:"[^"\n]*"|'[^'\n]*'|[^\s,}\n]+)''')
SHELL_SECRET = re.compile(r'''(?im)(\b(?:PGPASSWORD|PASS|PWD)\s*=\s*)(?:"[^"\n]*"|'[^'\n]*'|[^\s;,}\n]+)''')
def redact(s):
    s = ANSI.sub('', s)
    s = re.sub(r"(?is)(\bauth\s*=\s*\[REDACTED_BASIC_AUTH\])\s*,\s*(['\"])[^'\"]*\2\s*\)", r'\1', s)
    s = re.sub(r'(?is)(\bauth\s*=\s*)\([^)]*\)', r'\1[REDACTED_AUTH_TUPLE]', s)
    s = CREDENTIAL.sub(r'\1[REDACTED]', s)
    def redact_shell(match):
        # Preserve dbt completion counters, which are not shell credentials.
        if re.fullmatch(r'PASS=\d+', match.group(0)):
            return match.group(0)
        return match.group(1) + '[REDACTED]'
    s = SHELL_SECRET.sub(redact_shell, s)
    s = re.sub(r'''(?i)(Authorization\s*[:=]\s*["']?(?:Bearer|Basic)\s+)[^\s"']+''', r'\1[REDACTED]', s)
    s = re.sub(r'''(?i)(--(?:password|token|api-key|secret)(?:=|\s+))(?:"[^"]*"|'[^']*'|[^\s]+)''', r'\1[REDACTED]', s)
    s = re.sub(r'(?i)((?:postgres(?:ql)?|mongodb(?:\+srv)?)://[^:/\s]+:)[^@\s]+(@)', r'\1[REDACTED]\2', s)
    s = re.sub(r"(?i)((?:-u|--user)\s+)(?:\"[^\"]*:[^\"]*\"|'[^']*:[^']*'|[^\s]+:[^\s]+)", r'\1[REDACTED_BASIC_AUTH]', s)
    s = re.sub(r"(?im)(\bAUTH\s*=\s*)(?:\"[^\"\n]*\"|'[^'\n]*'|[^\s;,}\n]+)", r'\1[REDACTED_BASIC_AUTH]', s)
    return s
