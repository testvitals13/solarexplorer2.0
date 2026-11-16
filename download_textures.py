import os, subprocess
OUT = "static/textures"
os.makedirs(OUT, exist_ok=True)
T = "https://cdn.jsdelivr.net/gh/mrdoob/three.js@r160/examples/textures/planets/"
X = "https://cdn.jsdelivr.net/gh/jeromeetienne/threex.planets@master/images/"
FILES = {
 "2k_earth_daymap.jpg": [T+"earth_atmos_2048.jpg", X+"earthmap1k.jpg"],
 "2k_moon.jpg": [T+"moon_1024.jpg", X+"moonmap1k.jpg"],
 "2k_mercury.jpg": [X+"mercurymap.jpg"],
 "2k_venus_surface.jpg": [X+"venusmap.jpg"],
 "2k_mars.jpg": [X+"marsmap1k.jpg"],
 "2k_jupiter.jpg": [X+"jupitermap.jpg"],
 "2k_saturn.jpg": [X+"saturnmap.jpg"],
 "2k_uranus.jpg": [X+"uranusmap.jpg"],
 "2k_neptune.jpg": [X+"neptunemap.jpg"],
 "earth_clouds.png": [T+"earth_clouds_1024.png"],
 "earth_lights.png": [T+"earth_lights_2048.png"],
 "earth_normal.jpg": [T+"earth_normal_2048.jpg"],
 "earth_specular.jpg": [T+"earth_specular_2048.jpg"],
 "saturn_ring.jpg": [X+"saturnringcolor.jpg"],
}
ok = 0
for name, urls in FILES.items():
    path = os.path.join(OUT, name)
    done = False
    for u in urls:
        subprocess.run(["curl", "-L", "-f", "-s", "-o", path, u])
        if os.path.exists(path) and os.path.getsize(path) > 5000:
            print("OK    ", name, os.path.getsize(path) // 1024, "KB")
            done = True
            ok += 1
            break
    if not done:
        print("FAILED", name)
        if os.path.exists(path):
            os.remove(path)
print(ok, "of", len(FILES), "downloaded")
