import os, subprocess

BASE = "https://www.solarsystemscope.com/textures/download/"
REF = "https://www.solarsystemscope.com/textures/"
OUT = os.path.expanduser("~/solar/static/textures")
os.makedirs(OUT, exist_ok=True)

NAMES = [
    "2k_sun.jpg", "2k_stars_milky_way.jpg", "2k_uranus.jpg",
    "2k_venus_atmosphere.jpg", "2k_saturn_ring_alpha.png",
    "8k_earth_daymap.jpg", "8k_earth_nightmap.jpg", "8k_earth_clouds.jpg",
    "8k_moon.jpg", "8k_mars.jpg", "8k_mercury.jpg", "8k_venus_surface.jpg",
    "8k_jupiter.jpg", "8k_saturn.jpg", "8k_sun.jpg", "8k_stars_milky_way.jpg",
    "4k_ceres_fictional.jpg", "4k_haumea_fictional.jpg",
    "4k_makemake_fictional.jpg", "4k_eris_fictional.jpg",
]

for name in NAMES:
    path = os.path.join(OUT, name)
    if os.path.exists(path) and os.path.getsize(path) > 50000:
        print("have", name)
        continue
    subprocess.run(["curl", "-L", "-f", "-s", "--max-time", "400",
                    "-A", "Mozilla/5.0", "-e", REF, "-o", path, BASE + name])
    if os.path.exists(path) and os.path.getsize(path) > 20000:
        print("OK  ", name, os.path.getsize(path) // 1024, "KB")
    else:
        print("FAIL", name)
        if os.path.exists(path):
            os.remove(path)
print("DONE")
