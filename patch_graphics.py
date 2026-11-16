import shutil, os
F = "index.html"
if not os.path.exists("index.html.bak"): shutil.copy(F, "index.html.bak")
s = open("index.html.bak").read()
def rep(old, new):
    global s
    assert s.count(old) == 1, "NOT FOUND: " + old[:50]
    s = s.replace(old, new)
rep("Uranus: '2k_uranus.jpg', Neptune: '2k_neptune.jpg' };",
    "Uranus: '2k_uranus.jpg', Neptune: '2k_neptune.jpg', Pluto: 'pluto.jpg' };")
rep("  loader.load('/static/textures/' + file, apply, undefined, () => {});",
    "  loader.load('/static/textures/' + file, t => { t.anisotropy = renderer.capabilities.getMaxAnisotropy(); apply(t); }, undefined, () => {});")
rep("new THREE.MeshBasicMaterial({ map: t, side: THREE.BackSide })",
    "new THREE.MeshBasicMaterial({ map: t, color: 0xb0b0c0, side: THREE.BackSide })")
rep("sun.add(glow);", """sun.add(glow);
const corona = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(), color: 0xff9a3c,
  blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, opacity: 0.5 }));
corona.scale.set(70, 70, 1); sun.add(corona);
tryTexture('2k_sun.jpg', t => {
  t.colorSpace = THREE.SRGBColorSpace;
  sunShell = new THREE.Mesh(new THREE.SphereGeometry(4.06, 64, 64), new THREE.MeshBasicMaterial({
    map: t, color: 0xff8a30, transparent: true, opacity: 0.5, blending: THREE.AdditiveBlending, depthWrite: false }));
  sunShell.rotation.x = 0.6; sun.add(sunShell);
});""")
rep("// ---------- planets, dwarf planets, comet and moons ----------", open("gfx_earth.js").read() + "// ---------- planets, dwarf planets, comet and moons ----------")
rep("""  const m = new THREE.Mesh(new THREE.SphereGeometry(b.radius, 32, 32),
                           new THREE.MeshStandardMaterial({ color: b.color }));""",
"""  const m = new THREE.Mesh(new THREE.SphereGeometry(b.radius, 96, 96),
    b.name === 'Earth' ? new THREE.MeshPhongMaterial({ color: b.color, shininess: 28, specular: new THREE.Color(0x444444) })
                       : new THREE.MeshStandardMaterial({ color: b.color }));""")
i = s.index("    const ring = new THREE.Mesh(\n      new THREE.RingGeometry")
j = s.index("    m.add(ring);")
s = s[:i] + "    const ring = makeRing(b.radius);\n    ring.rotation.x = Math.PI / 2 + 0.47;\n" + s[j:]
rep("  decorate(m, b);\n  scene.add(m);\n}\n\nlet navBuilt", "  if (b.name === 'Earth') addEarthLayers(m, b);\n  decorate(m, b);\n  scene.add(m);\n}\n\nlet navBuilt")
rep("  controls.update();\n  for (const m of Object.values(bodies)) {",
    "  controls.update();\n  if (earthClouds) earthClouds.rotation.y += 0.0004;\n  sun.rotation.y += 0.0015;\n  if (sunShell) sunShell.rotation.y -= 0.0035;\n  glow.scale.setScalar(26 + Math.sin(performance.now() * 0.002) * 1.5);\n  for (const m of Object.values(bodies)) {")
open(F, "w").write(s)
print("DONE - index.html upgraded (backup: index.html.bak)")
