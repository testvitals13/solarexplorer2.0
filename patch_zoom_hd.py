import shutil, os
F = "index.html"
s = open(F).read()
if "zoomSpeed" in s:
    print("Already patched - nothing to do."); raise SystemExit
shutil.copy(F, "index.html.bak2")
def rep(old, new, n=1):
    global s
    assert s.count(old) == n, "NOT FOUND: " + old[:60]
    s = s.replace(old, new)
rep("controls.maxDistance = 14000;", "controls.maxDistance = 14000;\ncontrols.zoomSpeed = 5;      // bigger number = faster zoom\ncontrols.rotateSpeed = 0.9;")
rep("  loader.load('/static/textures/' + file, t => { t.anisotropy = renderer.capabilities.getMaxAnisotropy(); apply(t); }, undefined, () => {});",
"""  const list = Array.isArray(file) ? file : [file];   // a list = try the best picture first
  const go = i => {
    if (i >= list.length) return;
    loader.load('/static/textures/' + list[i], t => {
      t.anisotropy = renderer.capabilities.getMaxAnisotropy();
      console.log('texture loaded:', list[i]);
      apply(t);
    }, undefined, () => go(i + 1));
  };
  go(0);""")
i = s.index("const TEX = {"); j = s.index("};", i) + 2
s = s[:i] + """const best = n => ['8k_', '4k_', '2k_'].map(p => p + n);   // use the sharpest file that exists
const TEX = { Mercury: best('mercury.jpg'), Venus: best('venus_surface.jpg'), Earth: best('earth_daymap.jpg'),
  Moon: best('moon.jpg'), Mars: best('mars.jpg'), Jupiter: best('jupiter.jpg'), Saturn: best('saturn.jpg'),
  Uranus: best('uranus.jpg'), Neptune: best('neptune.jpg'), Pluto: ['pluto.jpg'] };""" + s[j:]
rep("tryTexture('2k_sun.jpg'", "tryTexture(['8k_sun.jpg', '4k_sun.jpg', '2k_sun.jpg']", 2)
rep("tryTexture('2k_stars_milky_way.jpg'", "tryTexture(['8k_stars_milky_way.jpg', '4k_stars_milky_way.jpg', '2k_stars_milky_way.jpg']")
rep("tryTexture('earth_clouds.png'", "tryTexture(['8k_earth_clouds.jpg', '4k_earth_clouds.jpg', '2k_earth_clouds.jpg', 'earth_clouds.png']")
rep("tryTexture('earth_lights.png'", "tryTexture(['8k_earth_nightmap.jpg', '4k_earth_nightmap.jpg', '2k_earth_nightmap.jpg', 'earth_lights.png']")
rep("const c = document.createElement('canvas'); c.width = t.image.width; c.height = t.image.height;\n    const x = c.getContext('2d'); x.drawImage(t.image, 0, 0);",
    "const sc = Math.min(1, 4096 / t.image.width), c = document.createElement('canvas');\n    c.width = Math.round(t.image.width * sc); c.height = Math.round(t.image.height * sc);\n    const x = c.getContext('2d'); x.drawImage(t.image, 0, 0, c.width, c.height);")
open(F, "w").write(s)
print("DONE - zoom fixed and HD texture loader installed (backup: index.html.bak2)")
