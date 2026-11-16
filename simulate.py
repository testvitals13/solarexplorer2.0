import numpy as np
from nbody import ts, GM, NAMES, nasa_state

AU_KM = 149597870.7

def acceleration(pos):
    """Newton's gravity: acceleration of every body caused by all the others."""
    d = pos[None, :, :] - pos[:, None, :]        # d[i, j] = vector from body i to body j
    r2 = (d ** 2).sum(axis=2)                    # distance squared
    np.fill_diagonal(r2, 1.0)                    # a body does not pull on itself
    inv_r3 = r2 ** -1.5
    np.fill_diagonal(inv_r3, 0.0)
    return (GM[None, :, None] * d * inv_r3[:, :, None]).sum(axis=1)

def leapfrog(pos, vel, dt):
    """Kick - drift - kick. Second-order accurate."""
    vel = vel + 0.5 * dt * acceleration(pos)
    pos = pos + dt * vel
    vel = vel + 0.5 * dt * acceleration(pos)
    return pos, vel

W1 = 1.0 / (2.0 - 2.0 ** (1.0 / 3.0))
W0 = -(2.0 ** (1.0 / 3.0)) * W1

def yoshida4(pos, vel, dt):
    """Three leapfrog steps with special weights. Fourth-order accurate."""
    for w in (W1, W0, W1):
        pos, vel = leapfrog(pos, vel, w * dt)
    return pos, vel

def run(t0, days, dt, method):
    pos, vel = nasa_state(t0)                    # start from NASA's exact state
    for _ in range(int(round(days / dt))):
        pos, vel = method(pos, vel, dt)
    return pos, vel

if __name__ == '__main__':
    t0 = ts.utc(2000, 1, 1, 12)
    days = 3652.5                                # about 10 years
    t1 = ts.tt_jd(t0.tt + days)
    truth, _ = nasa_state(t1)                    # what NASA says at the end date
    p1, _ = run(t0, days, 0.1, leapfrog)
    p2, _ = run(t0, days, 0.5, yoshida4)
    print('Error after 10 years versus NASA (kilometres)')
    print(f'{"body":8s} {"leapfrog dt=0.1d":>18s} {"yoshida4 dt=0.5d":>18s}')
    for i, n in enumerate(NAMES):
        e1 = np.linalg.norm(p1[i] - truth[i]) * AU_KM
        e2 = np.linalg.norm(p2[i] - truth[i]) * AU_KM
        print(f'{n:8s} {e1:18.1f} {e2:18.1f}')
