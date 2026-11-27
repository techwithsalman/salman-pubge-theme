import urllib.request
from pathlib import Path

BASE_DIR = Path(r"c:\Users\Abdulwahab\Downloads\2mcrafters.com")
urls = [
    "images/mohamedandaloussi/laptop/portrait-jacket-1448.webp",
    "images/mohamedandaloussi/laptop/portrait-jacket-1080.webp",
    "images/mohamedandaloussi/laptop/portrait-jacket-720.webp",
    "icons/icon-192.png",
    "icons/icon-512.png"
]

for p in urls:
    url = f"https://2mcrafters.com/{p}"
    lp = BASE_DIR / p.replace("/", "\\")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
            lp.parent.mkdir(parents=True, exist_ok=True)
            with open(lp, "wb") as f:
                f.write(data)
            print(f"[OK] {p} ({len(data)} bytes)")
    except Exception as e:
        print(f"[FAIL] {p}: {e}")
