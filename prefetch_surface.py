"""
prefetch_surface.py - run this ONCE while you have internet:   python3 prefetch_surface.py
It downloads the best surface panoramas of Mars, the Moon and Venus into static/cache/surface/,
so the 360 viewer opens instantly (and works offline) from then on.

   python3 prefetch_surface.py            -> top 4 per body, quick + full-size versions
   python3 prefetch_surface.py --small    -> quick versions only (small download, good for hosting)
"""
import sys
from surface_helper import search_surface, get_image, QUERIES

small = "--small" in sys.argv
for body in QUERIES:
    print("\n==", body)
    data = search_surface(body)
    for item in data.get("items", [])[:4]:
        print("  ", item["title"][:70], flush=True)
        get_image(item["id"], "fast")
        if not small:
            get_image(item["id"], "full")
print("\nDone. The panoramas are saved in static/cache/surface/")
