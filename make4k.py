import os
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
T = os.path.expanduser("~/solar/static/textures")
PAIRS = {
 "8k_earth_daymap.jpg": "2k_earth_daymap.jpg",
 "8k_moon.jpg": "2k_moon.jpg",
 "8k_mars.jpg": "2k_mars.jpg",
 "8k_mercury.jpg": "2k_mercury.jpg",
 "8k_venus_surface.jpg": "2k_venus_surface.jpg",
 "8k_jupiter.jpg": "2k_jupiter.jpg",
 "8k_saturn.jpg": "2k_saturn.jpg",
 "8k_sun.jpg": "2k_sun.jpg",
 "8k_stars_milky_way.jpg": "2k_stars_milky_way.jpg",
}
for big, name in PAIRS.items():
    src = os.path.join(T, big)
    dst = os.path.join(T, name)
    if not os.path.exists(src):
        print("missing", big)
        continue
    bak = os.path.join(T, "backup_" + name)
    if os.path.exists(dst) and not os.path.exists(bak):
        os.rename(dst, bak)
    im = Image.open(src).convert("RGB").resize((4096, 2048), Image.LANCZOS)
    im.save(dst, quality=93)
    print("ok", name, im.size)
print("DONE")
