"""Web search skill using DuckDuckGo (no API key needed)."""
import httpx


def execute(query: str) -> dict:
    """Search the web and return results."""
    url = "https://api.duckduckgo.com/"
    params = {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1}

    try:
        resp = httpx.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        results = []

        # Abstract (instant answer)
        if data.get("Abstract"):
            results.append({
                "title": data.get("Heading", ""),
                "snippet": data["Abstract"],
                "url": data.get("AbstractURL", ""),
            })

        # Related topics
        for topic in data.get("RelatedTopics", [])[:5]:
            if "Text" in topic:
                results.append({
                    "title": topic.get("Text", "")[:80],
                    "snippet": topic.get("Text", ""),
                    "url": topic.get("FirstURL", ""),
                })

        if not results:
            return {"status": "no_results", "query": query, "message": "No results found. Try rephrasing."}

        return {"status": "ok", "query": query, "results": results}

    except Exception as e:
        return {"status": "error", "error": str(e)}
