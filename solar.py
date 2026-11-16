from panda3d.core import loadPrcFileData
loadPrcFileData('', 'gl-version 3 2')
from ursina import *
from skyfield.api import load
import math

# --- NASA data (positions come from JPL's DE421 ephemeris) ---
ts = load.timescale()
eph = load('de421.bsp')
sun = eph['sun']

# name, ephemeris key, display size, color
PLANETS = [
    ('Mercury', 'mercury barycenter', 0.8, color.gray),
    ('Venus',   'venus barycenter',   1.4, color.orange),
    ('Earth',   'earth',              1.5, color.azure),
    ('Mars',    'mars barycenter',    1.1, color.red),
    ('Jupiter', 'jupiter barycenter', 4.5, color.brown),
    ('Saturn',  'saturn barycenter',  3.8, color.yellow),
    ('Uranus',  'uranus barycenter',  2.5, color.cyan),
    ('Neptune', 'neptune barycenter', 2.4, color.blue),
]

def planet_position(key, t):
    """Real position relative to the Sun, compressed so Neptune fits on screen."""
    x, y, z = (eph[key] - sun).at(t).position.au
    r = math.sqrt(x*x + y*y + z*z)
    shown = (r ** 0.5) * 12          # square-root scale: keeps inner planets visible
    k = shown / r
    return Vec3(x * k, z * k, y * k)  # swap axes so the orbits lie flat

app = Ursina()
window.color = color.black
window.title = 'Solar System'

now = ts.now()

Entity(model='sphere', color=color.yellow, scale=6)   # the Sun

for name, key, size, col in PLANETS:
    pos = planet_position(key, now)
    Entity(model='sphere', color=col, scale=size, position=pos)
    Text(name, position=pos + Vec3(0, size + 1, 0), billboard=True, scale=15)

ec = EditorCamera()      # right-click drag = rotate, scroll = zoom
ec.rotation_x = 40
camera.z = -150

Text(f'Positions for: {now.utc_strftime("%Y-%m-%d %H:%M")} UTC',
     position=(-0.85, 0.47), scale=1.2, color=color.white)

app.run()
