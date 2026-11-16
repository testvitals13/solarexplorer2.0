"""
surface_helper.py - finds real panoramic photos taken on the surface of Mars, the Moon and Venus
(rovers, Apollo astronauts, Venera landers) using NASA's free public Image Library, and caches them
on disk so a panorama you have already opened still works with NO internet.

No API key is needed. Only the standard Python library is used.
"""

import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "static", "cache", "surface")
API = "https://images-api.nasa.gov"
MAX_ORIGINAL_BYTES = 45 * 1024 * 1024          # bigger originals fall back to the 'large' version

# what to look for, per body (several searches are merged)
QUERIES = {
    "Mars": ["Perseverance Mastcam-Z panorama 360", "Curiosity Mastcam panorama 360", "Mars panorama Pancam Spirit",
             "Mars Opportunity panorama", "Mars rover 360 degree panorama"],
    "Moon": ["Apollo 17 panorama", "Apollo 15 panorama", "Apollo 11 panorama", "Apollo 14 panorama",
             "Apollo lunar surface panorama 360"],
    "Venus": ["Venera panorama surface", "Venera 13 panorama", "Venus lander surface panorama"],
}
GOOD = re.compile(r"pano|360|mosaic|vista|full[- ]circle|surround", re.I)
BAD = re.compile(r"artist|concept|illustration|animation|diagram|infograph|logo|poster|map of|simulat|model of|"
                 r"rendering|training|crew portrait|launch|test", re.I)
INDEX_TTL = 12 * 3600                           # a saved list of panoramas is reused for 12 hours (instant, no waiting)
_mem = {}                                       # in-memory copy of the lists
SAFE_ID = re.compile(r"^[A-Za-z0-9_.\-]{3,120}$")


def _ensure_cache():
    os.makedirs(CACHE, exist_ok=True)


def _open(url, timeout=25):
    url = url.replace("http://", "https://")
    url = urllib.parse.quote(url, safe=":/?&=%~+,")
    req = urllib.request.Request(url, headers={"User-Agent": "solar-system-school-project/1.0"})
    return urllib.request.urlopen(req, timeout=timeout)


def _json(url):
    with _open(url) as r:
        return json.loads(r.read().decode("utf-8"))


def _score(title, desc):
    text = title + " " + desc
    if BAD.search(title):
        return -1
    score = 0
    if re.search(r"pano|360", title, re.I):
        score += 4
    if GOOD.search(title):
        score += 2
    if GOOD.search(desc):
        score += 1
    if re.search(r"mastcam|pancam|navcam|apollo|venera|perseverance|curiosity|spirit|opportunity", text, re.I):
        score += 1
    return score


def _one_query(q):
    try:
        url = API + "/search?media_type=image&page_size=30&q=" + urllib.parse.quote(q)
        return _json(url).get("collection", {}).get("items", [])
    except Exception as e:
        print("[surface] query failed:", q, type(e).__name__, str(e)[:80])
        return []


def _warm(items):
    """Download the quick version of the first pictures in the background, so clicking one is instant."""
    def work():
        for it in items[:2]:
            get_image(it["id"], "fast")
    threading.Thread(target=work, daemon=True).start()


def search_surface(body):
    """Returns {'items': [...], 'offline': bool}. Each item: id, title, date, thumb."""
    body = (body or "").strip().title()
    if body not in QUERIES:
        return {"items": [], "error": body + " has no solid surface photographed from the ground."}
    _ensure_cache()
    cache_file = os.path.join(CACHE, "index_" + body + ".json")
    now = time.time()
    if body in _mem and now - _mem[body][0] < INDEX_TTL:                       # 1. already in memory
        return {"items": _mem[body][1], "offline": False}
    if os.path.exists(cache_file) and now - os.path.getmtime(cache_file) < INDEX_TTL:   # 2. fresh on disk
        with open(cache_file, encoding="utf-8") as f:
            items = json.load(f)
        _mem[body] = (now, items)
        _warm(items)
        return {"items": items, "offline": False}
    found = {}
    with ThreadPoolExecutor(max_workers=len(QUERIES[body])) as pool:               # 3. ask NASA, all searches at once
        results = list(pool.map(_one_query, QUERIES[body]))
    for batch in results:
        for item in batch:
            data = (item.get("data") or [{}])[0]
            nid, title = data.get("nasa_id", ""), data.get("title", "")
            if not nid or not SAFE_ID.match(nid) or nid in found:
                continue
            sc = _score(title, (data.get("description") or "")[:600])
            if sc < 2:
                continue
            links = item.get("links") or [{}]
            found[nid] = {"id": nid, "title": title[:110], "date": (data.get("date_created") or "")[:10],
                          "thumb": (links[0].get("href") or "").replace("http://", "https://"), "score": sc}
    items = sorted(found.values(), key=lambda x: -x["score"])[:16]
    if items:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(items, f)
        _mem[body] = (now, items)
        _warm(items)
        return {"items": items, "offline": False}
    if os.path.exists(cache_file):                                                 # 4. no internet: use the old list
        with open(cache_file, encoding="utf-8") as f:
            items = json.load(f)
        have = {fn.split(".")[0] for fn in os.listdir(CACHE)}
        items = [i for i in items if i["id"] in have] or items
        return {"items": items, "offline": True}
    return {"items": [], "error": "Could not reach NASA's image library. Connect to the internet once to download panoramas."}


def _cached(nasa_id, quality):
    _ensure_cache()
    suffix = ".fast." if quality == "fast" else "."
    for fn in os.listdir(CACHE):
        if fn.startswith("index_"):
            continue
        if quality == "fast" and fn.startswith(nasa_id + ".fast."):
            return os.path.join(CACHE, fn)
        if quality == "full" and fn.startswith(nasa_id + ".") and not fn.startswith(nasa_id + ".fast."):
            return os.path.join(CACHE, fn)
    return None


def get_image(nasa_id, quality="full"):
    """Local path of the panorama picture (downloads it the first time). quality 'fast' = a small version that
    arrives quickly, 'full' = the original. Falls back to whatever is saved already. None if impossible."""
    if not SAFE_ID.match(nasa_id or ""):
        return None
    quality = "fast" if quality == "fast" else "full"
    hit = _cached(nasa_id, quality)
    if hit:
        return hit
    if quality == "full":                                   # offline? an already saved quick version is better than nothing
        fast = _cached(nasa_id, "fast")
    else:
        fast = None
    try:
        hrefs = [i.get("href", "") for i in _json(API + "/asset/" + urllib.parse.quote(nasa_id))
                 .get("collection", {}).get("items", [])]
        pick = lambda tag: next((h for h in hrefs if ("~" + tag + ".") in h and h.lower().endswith((".jpg", ".jpeg", ".png"))), None)
        order = [pick("large"), pick("medium")] if quality == "fast" else [pick("orig"), pick("large"), pick("medium")]
        for href in [h for h in order if h]:
            ext = href.rsplit(".", 1)[1].lower().replace("jpeg", "jpg")
            with _open(href, timeout=60) as r:
                size = int(r.headers.get("Content-Length") or 0)
                if size > MAX_ORIGINAL_BYTES:
                    continue
                blob = r.read()
            name = nasa_id + (".fast." if quality == "fast" else ".") + ext
            path = os.path.join(CACHE, name)
            with open(path, "wb") as f:
                f.write(blob)
            return path
    except Exception as e:
        print("[surface] download failed:", type(e).__name__, str(e)[:120])
    return fast or (_cached(nasa_id, "full") if quality == "fast" else None)
