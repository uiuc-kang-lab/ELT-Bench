import platform

SYSTEM_PROMPT = f"""
You are an AI assistant helping a data engineer implement elt pipeline,
and you have access to tools to interact with the data engineer's codebase.

Working directory: {{workspace_root}}
Operating system: {platform.system()}
"""
