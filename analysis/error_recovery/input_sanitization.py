"""Frozen v3 sanitization rules copied from prepare_fresh_inputs.py.

No trajectory entries are removed or reordered.
"""
import re
from redaction import redact

REASONING_KEYS = {'reasoning_content', 'thinking_blocks', 'responses_reasoning_item',
                  'thought', 'thinking', 'reasoning'}


SECRET_KEYS = re.compile(r'(?:.*password|.*token|.*secret|apikey|secretaccesskey|'
                         r'accesskeyid|secretkey|privatekey|authorization|auth)\Z')


POSTHOC_KEYS = {'candidate_reasons', 'paper_rescore_per_model',
                'paper_rescore_all_targets_pass', 'evaluation_association'}


def sanitize(value, counts):
    if isinstance(value, str):
        clean = redact(value)
        # Existing redactor covers assignments, shell arguments, auth tuples and URLs.
        # Also cover multiline PEM private keys and credential bearer/JWT formats.
        clean = re.sub(r'-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----',
                       '[REDACTED_PRIVATE_KEY]', clean, flags=re.S)
        clean = re.sub(r'\b(?:sk-(?:ant-)?[A-Za-z0-9_-]{16,}|AKIA[A-Z0-9]{16})\b',
                       '[REDACTED_KEY]', clean)
        clean = re.sub(r'''(?i)(["']?Authorization["']?\s*[:=]\s*["']?(?:Bearer|Basic)\s+)[^\s"',}]+''',
                       r'\1[REDACTED]', clean)
        clean = re.sub(r'(?i)([a-z][a-z0-9+.-]*://[^\s/:@]+:)[^\s/@]+(@)',
                       r'\1[REDACTED]\2', clean)
        clean = re.sub(r'''(?im)(["']?(?:private[_-]?key|client[_-]?secret|session[_-]?token|refresh[_-]?token|access[_-]?token|api[_-]?key)["']?\s*[:=]\s*)(?:"[^"\n]*"|'[^'\n]*'|[^\s,}\n]+)''',
                       r'\1[REDACTED]', clean)
        counts['redacted_strings'] += clean != value
        return clean
    if isinstance(value, list):
        # Keep every array position stable for trajectory_entry/result_entry pointers.
        return [sanitize(item, counts) for item in value]
    if isinstance(value, dict):
        if (value.get('type') in {'thinking', 'reasoning', 'redacted_thinking'} or
                (value.get('type') == 'unknown' and
                 str(value.get('repr', '')).startswith(('ThinkingBlock(', 'RedactedThinkingBlock(')))):
            counts['removed_reasoning_blocks'] += 1
            return {'type': 'reasoning_omitted', 'note': 'Private reasoning omitted; no action or feedback removed.'}
        out = {}
        for key, item in value.items():
            if key in REASONING_KEYS:
                counts['removed_reasoning_fields'] += 1
            elif key in POSTHOC_KEYS:
                counts['removed_posthoc_fields'] += 1
            elif SECRET_KEYS.fullmatch(re.sub(r'[^a-z0-9]', '', key.lower())):
                out[key] = '[REDACTED]' if item is not None else None
                counts['redacted_secret_fields'] += item is not None
            else:
                out[key] = sanitize(item, counts)
        return out
    return value


def scrub_encoded_authorization(value, counts):
    """Second deterministic pass for JSON-encoded Authorization strings."""
    if isinstance(value, str):
        clean, count = re.subn(r'(?is)(Authorization.{0,80}?\b(?:Bearer|Basic)\s+)[A-Za-z0-9._~+/=-]+',
                              r'\1[REDACTED]', value)
        counts['encoded_authorization_scrubs'] = counts.get('encoded_authorization_scrubs', 0) + count
        return clean
    if isinstance(value, list):
        return [scrub_encoded_authorization(x, counts) for x in value]
    if isinstance(value, dict):
        return {key: scrub_encoded_authorization(item, counts) for key, item in value.items()}
    return value
