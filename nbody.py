import numpy as np
from skyfield.api import load

eph = load('de421.bsp')
ts = load.timescale()

GM_SUN = 0.00029591220828559   # gravity strength of the Sun, AU^3/day^2

# (name, NASA key, Sun mass divided by this body's mass)
BODIES = [
    ('Sun',     'sun',                 1.0),
    ('Mercury', 'mercury barycenter',  6023600.0),
    ('Venus',   'venus barycenter',    408523.71),
    ('Earth',   'earth',               None),
    ('Moon',    'moon',                None),
    ('Mars',    'mars barycenter',     3098703.59),
    ('Jupiter', 'jupiter barycenter',  1047.348625),
    ('Saturn',  'saturn barycenter',   3497.9018),
    ('Uranus',  'uranus barycenter',   22902.98),
    ('Neptune', 'neptune barycenter',  19412.26),
    ('Pluto',   'pluto barycenter',    1.36566e8),
]
NAMES = [b[0] for b in BODIES]

def make_gm():
    gm = []
    gm_earth_moon = GM_SUN / 328900.5614
    gm_moon = gm_earth_moon / (1 + 81.30056)
    for name, key, ratio in BODIES:
        if name == 'Sun':
            gm.append(GM_SUN)
        elif name == 'Moon':
            gm.append(gm_moon)
        elif name == 'Earth':
            gm.append(gm_earth_moon - gm_moon)
        else:
            gm.append(GM_SUN / ratio)
    return np.array(gm)

GM = make_gm()

def nasa_state(t):
    """Position (AU) and velocity (AU/day) of every body, measured from the
    centre of mass of the solar system, straight from NASA."""
    pos, vel = [], []
    for name, key, ratio in BODIES:
        s = eph[key].at(t)
        pos.append(s.position.au)
        vel.append(s.velocity.au_per_d)
    return np.array(pos), np.array(vel)

if __name__ == '__main__':
    t = ts.utc(2000, 1, 1, 12)
    pos, vel = nasa_state(t)
    for n, p, v in zip(NAMES, pos, vel):
        print(f'{n:8s} pos {p[0]:9.4f} {p[1]:9.4f} {p[2]:9.4f} AU')
    com = (GM[:, None] * pos).sum(axis=0) / GM.sum()
    print('centre of mass (should be tiny):', com)
