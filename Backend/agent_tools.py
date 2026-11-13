import os
import subprocess
from typing import Dict, Any, List

WORKSPACE_ROOT = os.getenv("WORKSPACE_ROOT", os.path.expanduser("~"))

ALLOWED_COMMAND_PREFIXES = (
    "ls", "cat", "pwd", "mkdir", "touch", "rm", "cp", "mv",
    "find", "grep", "head", "tail", "wc", "chmod", "echo",
    "python", "python3", "node", "git", "tree", "dir"
)

def is_safe_agent_command(cmd: str) -> bool:
    clean = cmd.strip()
    if not clean:
        return False
    parts = clean.split()
    base_cmd = os.path.basename(parts[0])
    return base_cmd in ALLOWED_COMMAND_PREFIXES or any(clean.startswith(p) for p in ALLOWED_COMMAND_PREFIXES)

def execute_agent_bash(command: str, timeout: int = 15) -> Dict[str, Any]:
    cmd_clean = command.strip()
    if not cmd_clean:
        return {"ok": False, "error": "Command is empty"}

    try:
        proc = subprocess.run(
            cmd_clean,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=WORKSPACE_ROOT if os.path.exists(WORKSPACE_ROOT) else None
        )
        return {
            "ok": True,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "returncode": proc.returncode,
            "command": cmd_clean
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Command timed out ({timeout}s limit)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def list_workspace_files(base_path: str = None) -> List[Dict[str, Any]]:
    target = base_path or WORKSPACE_ROOT
    if not os.path.exists(target):
        return []
    result = []
    try:
        for root, dirs, files in os.walk(target):
            # Skip hidden folders like .git
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for f in files:
                if f.startswith('.'):
                    continue
                full_p = os.path.join(root, f)
                rel_p = os.path.relpath(full_p, target)
                size = os.path.getsize(full_p) if os.path.exists(full_p) else 0
                result.append({"name": rel_p, "size": size})
    except Exception:
        pass
    return result
