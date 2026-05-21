"""OneMap reverse-geocode + haversine distance helpers."""
import math
import os
import time

import requests

from config import MSCPS

_token_cache = {"token": None, "expires": 0}


def _onemap_token():
    """Fetch + cache OneMap auth token (valid ~3 days)."""
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires"] - 3600:
        return _token_cache["token"]
    email = (os.environ.get("ONEMAP_EMAIL") or "").strip()
    pwd = (os.environ.get("ONEMAP_PASSWORD") or "").strip()
    if not (email and pwd):
        return None
    try:
        r = requests.post(
            "https://www.onemap.gov.sg/api/auth/post/getToken",
            json={"email": email, "password": pwd},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        _token_cache["token"] = data.get("access_token")
        _token_cache["expires"] = int(data.get("expiry_timestamp", now + 60 * 60 * 24))
        return _token_cache["token"]
    except Exception:
        return None


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest_mscp(lat: float, lon: float):
    best = None
    best_d = float("inf")
    for m in MSCPS:
        d = haversine_m(lat, lon, m["lat"], m["lon"])
        if d < best_d:
            best_d = d
            best = m
    return best, best_d


def reverse_geocode(lat: float, lon: float) -> dict:
    """OneMap public reverse geocode. Returns {address, postal}."""
    url = "https://www.onemap.gov.sg/api/public/revgeocode"
    params = {
        "location": f"{lat},{lon}",
        "buffer": 50,
        "addressType": "All",
        "otherFeatures": "N",
    }
    token = _onemap_token()
    if not token:
        return {"address": "", "postal": ""}
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=8)
        r.raise_for_status()
        data = r.json()
        results = data.get("GeocodeInfo", [])
        if not results:
            return {"address": "", "postal": ""}
        top = results[0]
        block = top.get("BLOCK", "").strip()
        road = top.get("ROAD", "").strip()
        building = top.get("BUILDINGNAME", "").strip()
        postal = top.get("POSTALCODE", "").strip()
        parts = []
        if block:
            parts.append(f"Blk {block}")
        if road:
            parts.append(road.title())
        addr = " ".join(parts) or building.title()
        return {"address": addr, "postal": postal}
    except Exception:
        return {"address": "", "postal": ""}
