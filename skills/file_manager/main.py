"""File management skill — read, write, list, append, delete files."""
import os


def execute(action: str, path: str, content: str = "") -> dict:
    """Manage files on disk."""
    path = os.path.expanduser(path)

    try:
        if action == "read":
            if not os.path.exists(path):
                return {"status": "error", "error": f"File not found: {path}"}
            with open(path) as f:
                data = f.read(50000)  # cap at 50KB
            return {"status": "ok", "path": path, "content": data, "size": os.path.getsize(path)}

        elif action == "write":
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w") as f:
                f.write(content)
            return {"status": "ok", "path": path, "bytes_written": len(content)}

        elif action == "append":
            with open(path, "a") as f:
                f.write(content)
            return {"status": "ok", "path": path, "bytes_appended": len(content)}

        elif action == "list":
            if not os.path.isdir(path):
                return {"status": "error", "error": f"Not a directory: {path}"}
            entries = []
            for name in sorted(os.listdir(path)):
                full = os.path.join(path, name)
                entries.append({
                    "name": name,
                    "type": "dir" if os.path.isdir(full) else "file",
                    "size": os.path.getsize(full) if os.path.isfile(full) else None,
                })
            return {"status": "ok", "path": path, "entries": entries}

        elif action == "delete":
            if not os.path.exists(path):
                return {"status": "error", "error": f"Not found: {path}"}
            os.remove(path)
            return {"status": "ok", "path": path, "deleted": True}

        else:
            return {"status": "error", "error": f"Unknown action: {action}"}

    except Exception as e:
        return {"status": "error", "error": str(e)}
