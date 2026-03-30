"""Weather skill using wttr.in (no API key needed)."""
import httpx


def execute(location: str) -> dict:
    """Get weather for a location."""
    try:
        url = f"https://wttr.in/{location}?format=j1"
        resp = httpx.get(url, timeout=10, headers={"User-Agent": "py-agent/1.0"})
        resp.raise_for_status()
        data = resp.json()

        current = data.get("current_condition", [{}])[0]
        area = data.get("nearest_area", [{}])[0]

        result = {
            "location": area.get("areaName", [{}])[0].get("value", location),
            "country": area.get("country", [{}])[0].get("value", ""),
            "temp_c": current.get("temp_C"),
            "feels_like_c": current.get("FeelsLikeC"),
            "humidity": current.get("humidity"),
            "description": current.get("weatherDesc", [{}])[0].get("value", ""),
            "wind_kph": current.get("windspeedKmph"),
            "wind_dir": current.get("winddir16Point"),
        }

        # 3-day forecast
        forecast = []
        for day in data.get("weather", [])[:3]:
            forecast.append({
                "date": day.get("date"),
                "max_c": day.get("maxtempC"),
                "min_c": day.get("mintempC"),
                "description": day.get("hourly", [{}])[4].get("weatherDesc", [{}])[0].get("value", ""),
            })
        result["forecast"] = forecast

        return {"status": "ok", **result}

    except Exception as e:
        return {"status": "error", "error": str(e)}
