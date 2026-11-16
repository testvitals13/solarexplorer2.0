import os, urllib.request

RES = "8k"   # change to "2k" if your Mac gets slow later
BASE = "https://www.solarsystemscope.com/textures/download/"
OUT = os.path.expanduser("~/solar/static/textures")
os.makedirs(OUT, exist_ok=True)

FILES = [
    ("sun.jpg", RES + "_sun.jpg"),
    ("mercury.jpg", RES + "_mercury.jpg"),
    ("venus.jpg", RES + "_venus_surface.jpg"),
    ("venus_atmo.jpg", "2k_venus_atmosphere.jpg"),
    ("earth.jpg", RES + "_earth_daymap.jpg"),
    ("earth_night.jpg", RES + "_earth_nightmap.jpg"),
    ("earth_clouds.jpg", RES + "_earth_clouds.jpg"),
    ("earth_normal.tif", "2k_earth_normal_map.tif"),
    ("earth_spec.tif", "2k_earth_specular_map.tif"),
    ("moon.jpg", RES + "_moon.jpg"),
    ("mars.jpg", RES + "_mars.jpg"),
    ("jupiter.jpg", RES + "_jupiter.jpg"),
    ("saturn.jpg", RES + "_saturn.jpg"),
    ("saturn_ring.png", "2k_saturn_ring_alpha.png"),
    ("uranus.jpg", "2k_uranus.jpg"),
    ("neptune.jpg", "2k_neptune.jpg"),
    ("stars.jpg", RES + "_stars_milky_way.jpg"),
    ("ceres.jpg", "4k_ceres_fictional.jpg"),
    ("haumea.jpg", "4k_haumea_fictional.jpg"),
    ("makemake.jpg", "4k_makemake_fictional.jpg"),
    ("eris.jpg", "4k_eris_fictional.jpg"),
]

def fetch(remote, path):
    req = urllib.request.Request(BASE + remote, headers={
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.solarsystemscope.com/textures/"})
    data = urllib.request.urlopen(req, timeout=120).read()
    if len(data) < 20000:
        raise ValueError("too small, probably not an image")
    open(path, "wb").write(data)

for name, remote in FILES:
    path = os.path.join(OUT, name)
    if os.path.exists(path):
        print("have", name)
        continue
    try:
        fetch(remote, path)
        print("OK  ", name, round(os.path.getsize(path) / 1e6, 1), "MB")
    except Exception as e:
        print("FAIL", name, remote, e)

try:
    from PIL import Image
    for t in ("earth_normal", "earth_spec"):
        src = os.path.join(OUT, t + ".tif")
        if os.path.exists(src):
            Image.open(src).convert("RGB").save(os.path.join(OUT, t + ".jpg"), quality=92)
            print("converted", t)
except Exception as e:
    print("convert problem:", e)
print("DONE")
