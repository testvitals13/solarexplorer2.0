import os, re, shutil
DL = os.path.expanduser("~/Downloads")
OUT = os.path.expanduser("~/solar/static/textures")
os.makedirs(OUT, exist_ok=True)
n = 0
for f in sorted(os.listdir(DL)):
    if re.match(r"^(2k|4k|8k)_.*\.(jpg|jpeg|png)$", f, re.I):
        shutil.move(os.path.join(DL, f), os.path.join(OUT, f))
        print("moved", f, os.path.getsize(os.path.join(OUT, f)) // 1024, "KB")
        n += 1
print(n, "file(s) moved into", OUT)
if n == 0: print("Nothing found in ~/Downloads. Did the downloads finish? Are the names like 8k_mars.jpg ?")
