from flask import Flask, jsonify, request, send_from_directory, send_file, abort
from skyfield.api import load
import numpy as np
import math
import os
import time
from collections import defaultdict, deque

from ask_helper import ask_gemini, chat_gemini     # the Gemini question box (the key is read from GEMINI_API_KEY, never stored here)

from surface_helper import search_surface, get_image   # real surface panoramas from NASA's public image library

app = Flask(__name__)

@app.after_request
def _cache_headers(resp):
    # pictures and libraries are kept by the browser for a week, so the page opens much faster the second time
    if request.path.startswith('/static/') and resp.status_code == 200:
        resp.headers['Cache-Control'] = 'public, max-age=604800'
    elif request.path == '/':
        resp.headers['Cache-Control'] = 'no-cache'
    return resp

# ---------- NASA data (JPL DE421 ephemeris, covers 1900-2050) ----------
ts = load.timescale()
eph = load('de421.bsp')
sun = eph['sun']

AU = 30.0                  # display units per astronomical unit. LINEAR = true proportions
J2000 = 2451545.0
OBL = math.radians(23.4392911)     # tilt between NASA's equator-based frame and the ecliptic
COSO, SINO = math.cos(OBL), math.sin(OBL)
MOON_DIST = 3.0            # the Moon's real orbit is too small to see at this scale, so it is exaggerated

# name, NASA key, display radius, color, kind
PLANETS = [
    ('Mercury', 'mercury barycenter', 0.5,  '#b5b5b5', 'planet'),
    ('Venus',   'venus barycenter',   0.9,  '#e8b869', 'planet'),
    ('Earth',   'earth',              1.0,  '#3b82f6', 'planet'),
    ('Mars',    'mars barycenter',    0.7,  '#d9532b', 'planet'),
    ('Jupiter', 'jupiter barycenter', 3.0,  '#c99b6d', 'planet'),
    ('Saturn',  'saturn barycenter',  2.6,  '#e6d3a3', 'planet'),
    ('Uranus',  'uranus barycenter',  1.7,  '#7fdbe0', 'planet'),
    ('Neptune', 'neptune barycenter', 1.7,  '#4766e0', 'planet'),
    ('Pluto',   'pluto barycenter',   0.45, '#c8b6a6', 'dwarf'),
]

# Bodies WE move with Kepler's equation, using published orbital elements:
# name, kind, radius, color, a (AU), e, inclination, node, arg. of perihelion, mean anomaly, epoch (JD)
KEPLER = [
    ('Ceres',    'dwarf', 0.35, '#a8a29e',  2.7656, 0.07958, 10.588,  80.250,  73.299, 231.540, 2461000.5),
    ('Haumea',   'dwarf', 0.40, '#d6d3d1', 42.961,  0.19703, 28.208, 121.825, 240.976, 221.566, 2460800.5),
    ('Makemake', 'dwarf', 0.40, '#d9a08a', 45.39,   0.16353, 29.034,  79.440, 296.070, 168.417, 2460600.5),
    ('Eris',     'dwarf', 0.50, '#e5e7eb', 68.145,  0.43196, 43.760,  36.071, 150.997, 208.762, 2460000.5),
    ('Halley',   'comet', 0.25, '#7dd3fc', 17.86,   0.9671, 162.19,   59.10,  112.05,    0.0,    2446470.94),
]

# Neptune and Pluto take longer to orbit than the NASA file covers, so their orbit LINES use elements
ELEMENTS = {'Neptune': (30.0699, 0.00859, 1.770, 131.784, 273.181),
            'Pluto':   (39.48,   0.2488,  17.14, 110.30,  113.76)}
PERIOD = {'Mercury': 88, 'Venus': 225, 'Earth': 365.25, 'Mars': 687,
          'Jupiter': 4333, 'Saturn': 10759, 'Uranus': 30687}

# Moons on simple circular orbits (our Moon comes from NASA).
# name, parent, distance, radius, color, period (days), start angle, tilt, direction
MOONS = [
    ('Io',       'Jupiter', 5.2, 0.28, '#e8d36a',  1.769,   0, 0.00,  1),
    ('Europa',   'Jupiter', 6.4, 0.25, '#d8c9a8',  3.551,  90, 0.00,  1),
    ('Ganymede', 'Jupiter', 7.8, 0.40, '#a89f91',  7.155, 180, 0.00,  1),
    ('Callisto', 'Jupiter', 9.4, 0.36, '#6d6459', 16.689, 270, 0.00,  1),
    ('Titan',    'Saturn',  9.5, 0.40, '#d9a441', 15.945,   0, 0.47,  1),
    ('Triton',   'Neptune', 3.8, 0.30, '#cfd8e3',  5.877,   0, 0.00, -1),
    ('Charon',   'Pluto',   1.3, 0.22, '#9a8f86',  6.387,   0, 0.00,  1),
]

# ---------- our own math ----------
def ecl(x, y, z):
    """NASA's frame is based on Earth's equator; rotate it to the ecliptic (the plane of Earth's orbit)."""
    return x, y * COSO + z * SINO, -y * SINO + z * COSO

def disp(x, y, z):
    """Ecliptic AU -> display units. Y is up, orbits lie flat, planets go counter-clockwise seen from above."""
    return x * AU, z * AU, -y * AU

def orbit_to_ecliptic(xv, yv, inc, node, argp):
    """Rotate a point from the orbit's own plane into the ecliptic (3 rotations)."""
    i, O, w = np.radians(inc), np.radians(node), np.radians(argp)
    cO, sO, cw, sw, ci, si = np.cos(O), np.sin(O), np.cos(w), np.sin(w), np.cos(i), np.sin(i)
    x = (cO * cw - sO * sw * ci) * xv + (-cO * sw - sO * cw * ci) * yv
    y = (sO * cw + cO * sw * ci) * xv + (-sO * sw + cO * cw * ci) * yv
    z = (sw * si) * xv + (cw * si) * yv
    return x, y, z

def kepler_xyz(a, e, inc, node, argp, M0, epoch, jd):
    """Position (AU) of a body on a Kepler orbit at Julian date jd. Works on single bodies or whole arrays."""
    a, e, M0, epoch = (np.asarray(v, dtype=float) for v in (a, e, M0, epoch))
    n = 0.9856076686 / a ** 1.5                            # mean motion in degrees per day
    M = np.radians((M0 + n * (jd - epoch)) % 360.0)        # mean anomaly now
    E = np.where(e > 0.8, np.pi, M)                        # first guess for the eccentric anomaly
    for _ in range(40):                                    # Newton's method on Kepler's equation  E - e*sin(E) = M
        E = E - (E - e * np.sin(E) - M) / (1 - e * np.cos(E))
    xv = a * (np.cos(E) - e)                               # position inside the orbit plane
    yv = a * np.sqrt(1 - e * e) * np.sin(E)
    return orbit_to_ecliptic(xv, yv, inc, node, argp)

def ellipse(a, e, inc, node, argp, n=720):
    """Points along a whole orbit, used for drawing the orbit line."""
    E = np.linspace(0, 2 * np.pi, n, endpoint=False)
    xv, yv = a * (np.cos(E) - e), a * math.sqrt(1 - e * e) * np.sin(E)
    return np.column_stack(disp(*orbit_to_ecliptic(xv, yv, inc, node, argp)))

# ---------- generated populations (fixed random seed, so they look the same every run) ----------
rng = np.random.default_rng(2026)

def population(a, e, inc):
    n = len(a)
    return dict(a=a, e=np.clip(e, 0, 0.9), inc=inc, node=rng.uniform(0, 360, n),
                argp=rng.uniform(0, 360, n), M0=rng.uniform(0, 360, n))

def make_main_belt():
    a = rng.uniform(2.1, 3.3, 4000)
    for gap in (2.50, 2.82, 2.96):                  # Kirkwood gaps: orbits that Jupiter's gravity clears out
        a = a[np.abs(a - gap) > 0.03]
    a = a[:2500]
    n = len(a)
    return population(a, np.clip(np.abs(rng.normal(0, 0.08, n)), 0, 0.25), np.abs(rng.normal(0, 7, n)))

def make_kuiper_belt():
    a = np.concatenate([rng.uniform(41, 47, 1400),           # the classical Kuiper belt
                        rng.normal(39.4, 0.25, 300)])        # "plutinos", locked to Neptune like Pluto
    e = np.concatenate([np.abs(rng.normal(0, 0.06, 1400)), rng.uniform(0.1, 0.27, 300)])
    return population(a, e, np.abs(rng.normal(0, 9, 1700)))

MAIN_BELT = make_main_belt()
KUIPER = make_kuiper_belt()
TROJAN_PHI = np.where(rng.random(500) < 0.5, 60.0, -60.0) + rng.normal(0, 9, 500)   # 60 degrees ahead / behind Jupiter
TROJAN_R = 1 + rng.normal(0, 0.03, 500)
TROJAN_Z = rng.normal(0, 0.2, 500)

def pop_xyz(P, jd):
    return kepler_xyz(P['a'], P['e'], P['inc'], P['node'], P['argp'], P['M0'], J2000, jd)

def flat(x, y, z):
    return np.round(np.column_stack(disp(x, y, z)), 1).ravel().tolist()

# ---------- the web part ----------
def snapshot(t):
    jd = float(t.tt)
    days = jd - J2000
    out, pos, au = [], {}, {}

    def add(name, kind, radius, color, p, dist):
        pos[name], au[name] = p, dist
        out.append({'name': name, 'kind': kind, 'radius': radius, 'color': color,
                    'pos': [round(float(v), 3) for v in p], 'au': round(float(dist), 3)})

    for name, key, radius, color, kind in PLANETS:           # straight from NASA
        x, y, z = ecl(*(eph[key] - sun).at(t).position.au)
        add(name, kind, radius, color, disp(x, y, z), math.sqrt(x * x + y * y + z * z))

    for name, kind, radius, color, *elements in KEPLER:      # moved by our own Kepler solver
        x, y, z = kepler_xyz(*elements, jd)
        add(name, kind, radius, color, disp(x, y, z), math.sqrt(x * x + y * y + z * z))

    mx, my, mz = ecl(*(eph['moon'] - eph['earth']).at(t).position.au)   # the Moon: real direction from NASA
    ox, oy, oz = disp(mx, my, mz)
    k = MOON_DIST / (math.sqrt(mx * mx + my * my + mz * mz) * AU)       # shrink the distance so it fits
    ep = pos['Earth']
    add('Moon', 'moon', 0.3, '#c9c9c9', (ep[0] + ox * k, ep[1] + oy * k, ep[2] + oz * k), au['Earth'])

    for name, parent, dist, radius, color, period, phase, tilt, direction in MOONS:
        ang = math.radians(phase + direction * 360.0 * days / period)
        dx, dz = dist * math.cos(ang), dist * math.sin(ang)
        p = pos[parent]
        add(name, 'moon', radius, color,
            (p[0] + dx, p[1] - dz * math.sin(tilt), p[2] + dz * math.cos(tilt)), au[parent])

    belts = {'main': flat(*pop_xyz(MAIN_BELT, jd)), 'kuiper': flat(*pop_xyz(KUIPER, jd))}
    jx, jy, jz = ecl(*(eph['jupiter barycenter'] - sun).at(t).position.au)
    ph = np.radians(TROJAN_PHI)                                          # Trojans ride along with Jupiter
    belts['trojans'] = flat((jx * np.cos(ph) - jy * np.sin(ph)) * TROJAN_R,
                            (jx * np.sin(ph) + jy * np.cos(ph)) * TROJAN_R,
                            jz * TROJAN_R + TROJAN_Z)
    return out, belts

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/planets')
def planets():
    date = request.args.get('date')          # format YYYY-MM-DD
    try:
        if date:
            yr, mo, dy = (int(v) for v in date.split('-'))
            t = ts.utc(yr, mo, dy, 12)
        else:
            t = ts.now()
        bodies, belts = snapshot(t)
    except Exception as ex:
        return jsonify(error=str(ex)), 400
    return jsonify(date=t.utc_strftime('%Y-%m-%d %H:%M UTC'), bodies=bodies, belts=belts)

_orbit_cache = {}

@app.route('/api/orbits')
def orbits():
    if not _orbit_cache:
        start = ts.utc(1950, 1, 1).tt
        for name, key, radius, color, kind in PLANETS:
            if name in ELEMENTS:
                pts = ellipse(*ELEMENTS[name])
            else:                                                    # sample NASA's own positions over one orbit
                t = ts.tt_jd(np.linspace(start, start + PERIOD[name], 400, endpoint=False))
                x, y, z = ecl(*(eph[key] - sun).at(t).position.au)
                pts = np.column_stack(disp(x, y, z))
            _orbit_cache[name] = {'kind': kind, 'pts': pts.round(2).tolist()}
        for name, kind, radius, color, a, e, inc, node, argp, M0, epoch in KEPLER:
            _orbit_cache[name] = {'kind': kind, 'pts': ellipse(a, e, inc, node, argp).round(2).tolist()}
    return jsonify(_orbit_cache)

@app.route('/api/ask', methods=['POST'])
def ask():
    result, status = ask_gemini(request.get_json(silent=True) or {})
    return jsonify(result), status

# ---- fair-use limits per visitor, so a public link cannot use up your free Gemini quota
_hits = defaultdict(deque)
LIMITS = ((60, 12), (86400, 300))          # at most 12 questions a minute and 300 a day for each visitor

def _visitor():
    return (request.headers.get('X-Forwarded-For', request.remote_addr or '?').split(',')[0].strip())

def _allowed():
    now, q = time.time(), _hits[_visitor()]
    while q and now - q[0] > 86400:
        q.popleft()
    for window, cap in LIMITS:
        if sum(1 for t in q if now - t < window) >= cap:
            return False
    q.append(now)
    return True

@app.route('/api/assistant', methods=['POST'])
def assistant():
    if not _allowed():
        return jsonify(error='You are asking very quickly. Please wait a moment and try again.'), 429
    result, status = chat_gemini(request.get_json(silent=True) or {})
    return jsonify(result), status

@app.route('/api/surface/search')
def surface_search():
    return jsonify(search_surface(request.args.get('body', '')))

@app.route('/api/surface/image/<nasa_id>')
def surface_image(nasa_id):
    path = get_image(nasa_id, request.args.get('q', 'full'))
    if not path:
        abort(404)
    return send_file(path, max_age=86400)

@app.route('/healthz')
def healthz():
    return 'ok'

if __name__ == '__main__':
    app.run(host=os.environ.get('HOST', '127.0.0.1'), port=int(os.environ.get('PORT', 8000)))
