import json, subprocess, time
import numpy as np

URL = "https://ssd.jpl.nasa.gov/api/horizons.api"

def horizons_state(command, start="2000-01-01 12:00", stop="2000-01-02 12:00"):
    """Position (AU) and velocity (AU/day) of a body from NASA Horizons,
    measured from the solar system barycentre (same frame as Skyfield)."""
    args = {
        "format": "json", "COMMAND": f"'{command}'", "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'", "EPHEM_TYPE": "'VECTORS'", "CENTER": "'500@0'",
        "START_TIME": f"'{start}'", "STOP_TIME": f"'{stop}'", "STEP_SIZE": "'1 d'",
        "VEC_TABLE": "'2'", "OUT_UNITS": "'AU-D'", "REF_PLANE": "'FRAME'",
        "CSV_FORMAT": "'YES'",
    }
    cmd = ["curl", "-sS", "-G", "--max-time", "120",
           "-w", "\n__HTTP__%{http_code}", URL]
    for k, v in args.items():
        cmd += ["--data-urlencode", f"{k}={v}"]
    problem = ""
    for attempt in range(3):
        r = subprocess.run(cmd, capture_output=True, text=True)
        body, _, code = r.stdout.rpartition("\n__HTTP__")
        try:
            text = json.loads(body)["result"]
            row = text.split("$$SOE")[1].split("$$EOE")[0].strip().splitlines()[0]
            v = [float(x) for x in row.split(",")[2:8]]
            return np.array(v[:3]), np.array(v[3:])
        except Exception:
            problem = (f"curl exit code {r.returncode}, HTTP status {code}, "
                       f"curl said: {r.stderr.strip()!r}, reply starts: {body[:300]!r}")
            print(f"  attempt {attempt + 1} failed, retrying...", flush=True)
            time.sleep(3)
    raise RuntimeError("Horizons gave no usable answer. " + problem)

if __name__ == "__main__":
    from nbody import ts, eph
    AU_KM = 149597870.7
    pos, vel = horizons_state("399")                 # 399 = Earth
    sky = eph["earth"].at(ts.tdb(2000, 1, 1, 12)).position.au
    print("Earth: Horizons vs Skyfield differ by", round(np.linalg.norm(pos - sky) * AU_KM, 1), "km")
    pos, vel = horizons_state("-31")                 # -31 = Voyager 1
    print("Voyager 1 on 2000-01-01:", np.linalg.norm(pos).round(2), "AU from the barycentre")
