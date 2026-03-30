"""
Image creator skill — generate images via Recraft AI (RecraftV3).
Fallback: Gemini image API.
"""
import os
import json
import time
import httpx

# Recraft AI config
RECRAFT_API_URL = "https://external.api.recraft.ai/v1/images/generations"
RECRAFT_API_KEY = "Hfcdja1KnZajZP9hSgzm1N26CIHnnjQ40tDu42pThB3TY0MHjfMP9gkj7aW4vGQe"

# Gemini fallback
GEMINI_API_URL = "https://vibe.madewgn.dev/v1beta/models/gemini-3.1-flash-image:generateContent"
GEMINI_API_KEY = "xbansos"

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "output")
VALID_STYLES = ["realistic_image", "digital_illustration", "vector_illustration", "icon"]


def _generate_recraft(prompt: str, style: str, output_path: str) -> dict:
    """Generate image using Recraft AI."""
    headers = {
        "Authorization": f"Bearer {RECRAFT_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "prompt": prompt,
        "model": "recraftv3",
        "style": style,
        "size": "1024x1024",
    }

    resp = httpx.post(RECRAFT_API_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    if "error" in data:
        raise Exception(data["error"].get("message", str(data["error"])))

    if "data" not in data or not data["data"]:
        raise Exception("No image returned from Recraft API")

    image_url = data["data"][0].get("url", "")
    if not image_url:
        raise Exception("No image URL in response")

    # Download image
    img_resp = httpx.get(image_url, timeout=30)
    img_resp.raise_for_status()
    with open(output_path, "wb") as f:
        f.write(img_resp.content)

    return {
        "provider": "recraft",
        "credits_used": data.get("credits", "unknown"),
        "image_url": image_url,
    }


def _generate_gemini(prompt: str, output_path: str) -> dict:
    """Fallback: generate image using Gemini."""
    import base64

    headers = {
        "Authorization": f"Bearer {GEMINI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "contents": [{"parts": [{"text": f"Generate an image: {prompt}"}]}],
        "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
    }

    resp = httpx.post(GEMINI_API_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    # Extract image from Gemini response
    for candidate in data.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            if "inlineData" in part:
                img_data = base64.b64decode(part["inlineData"]["data"])
                with open(output_path, "wb") as f:
                    f.write(img_data)
                return {"provider": "gemini", "credits_used": "N/A"}

    raise Exception("No image in Gemini response")


def execute(prompt: str, style: str = "realistic_image", filename: str = "") -> dict:
    """Generate an image from a text prompt."""
    # Validate style
    if style not in VALID_STYLES:
        style = "realistic_image"

    # Setup output
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if not filename:
        filename = f"img_{int(time.time())}"
    output_path = os.path.join(OUTPUT_DIR, f"{filename}.png")

    # Try Recraft first, fallback to Gemini
    try:
        result = _generate_recraft(prompt, style, output_path)
    except Exception as e:
        try:
            result = _generate_gemini(prompt, output_path)
            result["recraft_error"] = str(e)
        except Exception as e2:
            return {
                "status": "error",
                "error": f"Both providers failed. Recraft: {e}, Gemini: {e2}",
            }

    return {
        "status": "ok",
        "prompt": prompt,
        "style": style,
        "file": output_path,
        "size": os.path.getsize(output_path),
        **result,
    }
