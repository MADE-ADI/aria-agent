"""Shell execution skill — run commands safely."""
import subprocess


def execute(command: str, timeout: int = 30) -> dict:
    """Execute a shell command and return output."""
    # Safety: block obviously dangerous commands
    dangerous = ["rm -rf /", "mkfs", ":(){:|:&};:", "dd if=/dev/zero"]
    for d in dangerous:
        if d in command:
            return {"status": "blocked", "error": f"Blocked dangerous command: {command}"}

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "status": "ok",
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout[:10000],  # cap output
            "stderr": result.stderr[:5000] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "command": command, "error": f"Command timed out after {timeout}s"}
    except Exception as e:
        return {"status": "error", "error": str(e)}
