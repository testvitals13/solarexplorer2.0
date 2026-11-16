import numpy as np
import rebound
from skyfield.api import load

eph = load('de421.bsp')
ts = load.timescale()
AU_KM = 149597870.7

NAMES = ['Sun','Mercury','Venus','Earth','Mars','Jupiter','Saturn','Uranus','Neptune','Pluto']
KEYS = ['sun','mercury barycenter','venus barycenter','earth barycenter','mars barycenter',
        'jupiter barycenter','saturn barycenter','uranus barycenter','neptune barycenter','pluto barycenter']
# GM (km^3/s^2) from NASA JPL DE values (planet + its moons)
GM_KM = [132712440041.94, 22031.868, 324858.592, 403503.236, 42828.376,
         126712764.8, 37940585.2, 5794556.4, 6836527.1, 975.5]
GM = np.array(GM_KM) * 86400.0**2 / AU_KM**3      # AU^3 / day^2

def nasa_state(jd):
    t = ts.tt_jd(jd)
    p = [eph[k].at(t).position.au for k in KEYS]
    v = [eph[k].at(t).velocity.au_per_d for k in KEYS]
    return np.array(p), np.array(v)

jd0 = 2451545.0                                    # 2000-01-01 12:00
days = 3652.5                                      # 10 years
p0, v0 = nasa_state(jd0)

sim = rebound.Simulation()
sim.units = ('day', 'AU', 'Msun')
sim.G = 1.0                                        # we give masses as GM, so G = 1
for i in range(len(NAMES)):
    sim.add(m=GM[i], x=p0[i][0], y=p0[i][1], z=p0[i][2],
            vx=v0[i][0], vy=v0[i][1], vz=v0[i][2])
sim.integrator = 'ias15'
sim.integrate(days)

truth, _ = nasa_state(jd0 + days)
print('REBOUND vs NASA after 10 years')
print(f'{"body":9s}{"error (km)":>14s}')
for i in range(1, len(NAMES)):
    q = sim.particles[i]
    sim_pos = np.array([q.x, q.y, q.z])
    err = np.linalg.norm(sim_pos - truth[i]) * AU_KM
    print(f'{NAMES[i]:9s}{err:14,.1f}')
