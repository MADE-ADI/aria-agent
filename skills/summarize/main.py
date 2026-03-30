"""Summarize skill — extracts text from source, returns it for LLM summarization."""
import httpx
import os


def execute(text: str = "", url: str = "", file: str = "") -> dict:
    """Get text from source for summarization."""
    content = ""

    if url:
        try:
            resp = httpx.get(url, timeout=15, follow_redirects=True)
            resp.raise_for_status()
            # Basic HTML stripping
            import re
            html = resp.text
            html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
            html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
            html = re.sub(r'<[^>]+>', ' ', html)
            html = re.sub(r'\s+', ' ', html).strip()
            content = html[:15000]
        except Exception as e:
            return {"status": "error", "error": f"Failed to fetch URL: {e}"}

    elif file:
        path = os.path.expanduser(file)
        if not os.path.exists(path):
            return {"status": "error", "error": f"File not found: {path}"}
        with open(path) as f:
            content = f.read(15000)

    elif text:
        content = text[:15000]

    else:
        return {"status": "error", "error": "Provide text, url, or file to summarize"}

    return {
        "status": "ok",
        "source": url or file or "direct_text",
        "content": content,
        "length": len(content),
        "instruction": "Please summarize the above content into clear, concise bullet points.",
    }
