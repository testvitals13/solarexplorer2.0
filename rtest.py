import rebound
names = ['Sun','Mercury','Venus','Earth','Mars','Jupiter','Saturn','Uranus','Neptune']

def build(date):
    sim = rebound.Simulation()
    sim.units = ('day', 'AU', 'Msun')
    for n in names:
        sim.add(n, date=date)        # data comes live from NASA JPL Horizons
    return sim

sim = build('2000-01-01 12:00')
sim.integrator = 'ias15'
sim.integrate(3652.5)                # 10 years, in days

ref = build('2010-01-01 12:00')      # NASA's own answer for that date
AU_KM = 149597870.7
print('Body        error vs NASA (km)')
for i in range(1, len(names)):
    a = sim.particles[i] - sim.particles[0]
    b = ref.particles[i] - ref.particles[0]
    err = ((a.x-b.x)**2 + (a.y-b.y)**2 + (a.z-b.z)**2) ** 0.5 * AU_KM
    print(f'{names[i]:10s}{err:16,.0f}')
