import os, subprocess
X = "https://cdn.jsdelivr.net/gh/jeromeetienne/threex.planets@master/images/"
FILES = {"2k_sun.jpg": "sunmap.jpg", "2k_stars_milky_way.jpg": "galaxy_starfield.png", "pluto.jpg": "plutomap1k.jpg"}
for name, src in FILES.items():
    path = "static/textures/" + name
    subprocess.run(["curl", "-L", "-f", "-s", "-o", path, X + src])
    ok = os.path.exists(path) and os.path.getsize(path) > 5000
    print("OK    " if ok else "FAILED", name)
