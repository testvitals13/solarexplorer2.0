import numpy as np
import rebound
from flask import jsonify, request
from skyfield.api import load

eph = load('de421.bsp')
ts = load.timescale()
AU_KM = 149597870.7
NAMES = ['Sun','Mercury','Venus','Earth','Mars','Jupiter','Saturn','Uranus','Neptune','Pluto']
KEYS = ['sun','mercury barycenter','venus barycenter','earth barycenter','mars barycenter',
        'jupiter barycenter','saturn barycenter','uranus barycenter','neptune barycenter','pluto barycenter']
# GM (km^3/s^2), NASA JPL values (planet + its moons)
GM_KM = [132712440041.94, 22031.868, 324858.592, 403503.236, 42828.376,
         126712764.8, 37940585.2, 5794556.4, 6836527.1, 975.5]
GM = np.array(GM_KM) * 86400.0**2 / AU_KM**3       # AU^3 / day^2
JD0 = 2451545.0                                     # 2000-01-01 12:00
_cache = {}

def nasa_state(jd):
    t = ts.tt_jd(jd)
    p = np.array([eph[k].at(t).position.au for k in KEYS])
    v = np.array([eph[k].at(t).velocity.au_per_d for k in KEYS])
    return p, v

def run_check(years):
    days = years * 365.25
    p0, v0 = nasa_state(JD0)                        # start: NASA's exact state
    sim = rebound.Simulation()
    sim.units = ('day', 'AU', 'Msun')
    sim.G = 1.0                                     # masses given as GM
    for i in range(len(NAMES)):
        sim.add(m=GM[i], x=p0[i][0], y=p0[i][1], z=p0[i][2],
                vx=v0[i][0], vy=v0[i][1], vz=v0[i][2])
    sim.integrator = 'ias15'
    sim.integrate(days)
    truth, _ = nasa_state(JD0 + days)               # NASA's answer for that date
    out = []
    for i in range(1, len(NAMES)):
        q = sim.particles[i]
        sim_pos = np.array([q.x, q.y, q.z])
        dist = float(np.linalg.norm(truth[i] - truth[0]) * AU_KM)
        err = float(np.linalg.norm(sim_pos - truth[i]) * AU_KM)
        out.append({'name': NAMES[i], 'error_km': round(err, 1),
                    'distance_km': round(dist), 'ppm': round(err / dist * 1e6, 3)})
    return out

PAGE = """<!doctype html><meta charset=utf-8><title>Physics check</title>
<style>body{background:#05070d;color:#dfe6f2;font-family:sans-serif;max-width:760px;margin:30px auto;padding:0 16px}
table{width:100%;border-collapse:collapse;margin-top:14px}td,th{padding:6px 10px;text-align:left;border-bottom:1px solid #223}
.bar{height:10px;background:#4da3ff;border-radius:5px}input,button{font-size:16px;padding:6px 10px}
a{color:#7db8ff}small{color:#8a97ad}</style>
<h2>Our gravity simulation vs NASA</h2>
<p>Start: NASA JPL DE421 positions and velocities on 1 Jan 2000. Engine: REBOUND (IAS15), a research-grade N-body code.
We simulate forward or backward, then compare with NASA's real positions for that date.</p>
Years from 2000 (-90 to 50): <input id=y type=number value=10 min=-90 max=50>
<button onclick=go()>Run simulation</button> <a href="/">back to the solar system</a>
<p id=st></p><table id=t></table>
<small>Error is the distance between our simulated planet and NASA's position. "Relative error" is that distance divided by the planet's distance from the Sun.</small>
<script>
async function go(){
  const y=document.getElementById('y').value;
  document.getElementById('st').textContent='Simulating '+y+' years...';
  const r=await (await fetch('/api/physics?years='+y)).json();
  if(r.error){document.getElementById('st').textContent=r.error;return}
  document.getElementById('st').textContent='Done: '+r.years+' years ('+r.date+')';
  const mx=Math.max(...r.bodies.map(b=>b.error_km));
  document.getElementById('t').innerHTML='<tr><th>Planet<th>Error (km)<th>Relative error<th>'+
    r.bodies.map(b=>'<tr><td>'+b.name+'<td>'+b.error_km.toLocaleString()+' km<td>'+b.ppm+' parts per million<td style="width:30%"><div class=bar style="width:'+Math.max(2,b.error_km/mx*100)+'%"></div>').join('');
}
go();
</script>"""

def register(app):
    @app.route('/api/physics')
    def physics_api():
        try:
            years = float(request.args.get('years', 10))
        except ValueError:
            return jsonify(error='years must be a number'), 400
        if not -90 <= years <= 50:
            return jsonify(error='NASA DE421 only covers about 1910 to 2050 here, so use -90 to 50 years'), 400
        key = round(years, 2)
        if key not in _cache:
            _cache[key] = run_check(key)
        t = ts.tt_jd(JD0 + key * 365.25)
        return jsonify(years=key, date=t.utc_strftime('%Y-%m-%d'), bodies=_cache[key])

    @app.route('/physics')
    def physics_page():
        return PAGE
