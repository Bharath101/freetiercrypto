#!/usr/bin/env python3
"""Check every internal link/asset in dist/ resolves to a built file. Usage: python scripts/check_links.py [dist]"""
import json, os, sys
from pathlib import Path
from urllib.parse import urlparse
from bs4 import BeautifulSoup
ROOT = Path(__file__).resolve().parent.parent
dist = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "dist")
BASE = urlparse(os.environ.get("SITE_URL", json.loads((ROOT / "site.json").read_text())["base_url"])).path.rstrip("/")
bad, n = [], 0
for f in dist.rglob("*.html"):
    s = BeautifulSoup(f.read_text(), "lxml")
    for tag, attr in (("a", "href"), ("link", "href"), ("script", "src"), ("img", "src")):
        for el in s.find_all(tag):
            u = el.get(attr)
            if not u or u.startswith(("mailto:", "#", "javascript:")):
                continue
            p = urlparse(u)
            if p.scheme in ("http", "https"):
                continue
            n += 1
            if p.path.startswith("/") and BASE:
                if not (p.path == BASE or p.path.startswith(BASE + "/")):
                    bad.append((str(f.relative_to(dist)), u + "  (missing base path)")); continue
                p = p._replace(path=p.path[len(BASE):] or "/")
            path = p.path if p.path.startswith("/") else str(Path("/") / f.parent.relative_to(dist) / p.path)
            target = dist / path.lstrip("/")
            if path.endswith("/"):
                target = target / "index.html"
            if not target.exists():
                bad.append((str(f.relative_to(dist)), u))
print(f"checked {n} internal links across {len(list(dist.rglob('*.html')))} pages; broken: {len(bad)}")
for b in bad[:50]:
    print("  BROKEN", b)
sys.exit(1 if bad else 0)
