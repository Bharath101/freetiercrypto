#!/usr/bin/env python3
"""Re-fetch every tool's pricing page, compare it with the last snapshot and flag differences.

Usage:
  python scripts/check_pricing.py                 # check all tools
  python scripts/check_pricing.py --only koinly   # check some tools (comma-separated ids)
  python scripts/check_pricing.py --fail-on-change

For each tool in data/tools.json it fetches `price_source_url` (plain HTTP first, then headless
Chrome if CHROME_BIN is set and the page looks empty), keeps only lines that look like pricing
(prices, plan words, limits), and compares them with data/snapshots/<id>.json.

Outputs:
  data/snapshots/<id>.json  latest pricing lines + hash (only rewritten on a clean fetch)
  data/pricing_diffs.json   tools whose pricing lines changed in this run (added/removed lines)

A flagged diff is NOT a confirmed change: pages change for sale banners, layout and geo-currency.
Confirm by hand, update data/tools.json, then add an entry to data/changelog.json.
"""
import argparse, datetime as dt, hashlib, json, os, re, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SNAP = DATA / "snapshots"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
PRICE_RE = re.compile(r"(?:[$€£₹]\s?\d[\d,]*(?:\.\d+)?|\d[\d,]*(?:\.\d+)?\s?(?:USD|EUR|USDC)\b)", re.I)
PLAN_RE = re.compile(r"\b(free|trial|per month|/mo\b|/month|/year|/yr|annual|yearly|monthly|billed|plan|tier|"
                     r"credits?|calls?|requests?|alerts?|transactions?|limit|unlimited|one-time|tax year)\b", re.I)
CHALLENGE_RE = re.compile(r"(verify you are human|checking your browser|performing security verification|"
                          r"attention required|enable javascript and cookies|access denied|captcha)", re.I)
MIN_LINES = 3


def fetch_http(url):
    r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}, timeout=30)
    r.raise_for_status()
    return r.text


def fetch_chrome(url):
    chrome = os.environ.get("CHROME_BIN")
    if not chrome:
        return ""
    with tempfile.TemporaryDirectory() as prof:
        out = subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", f"--user-data-dir={prof}",
                              "--virtual-time-budget=15000", f"--user-agent={UA}", "--lang=en-US", "--dump-dom", url],
                             capture_output=True, text=True, timeout=120)
    return out.stdout


def pricing_lines(html):
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    seen, keep = set(), []
    for line in soup.get_text("\n").split("\n"):
        line = re.sub(r"\s+", " ", line).strip()
        if not line or len(line) > 220 or line in seen:
            continue
        if PRICE_RE.search(line) or (PLAN_RE.search(line) and len(line) < 120):
            seen.add(line)
            keep.append(line)
    return keep


def check(tool):
    url, err, lines, html = tool["price_source_url"], None, [], ""
    for fetch in (fetch_http, fetch_chrome):
        try:
            html = fetch(url)
        except Exception as e:  # noqa: BLE001 - report and try the next fetcher
            err = f"{fetch.__name__}: {e.__class__.__name__}: {e}"[:300]
            continue
        if html and CHALLENGE_RE.search(html[:20000]) and len(pricing_lines(html)) < MIN_LINES:
            err = f"{fetch.__name__}: bot challenge page"
            continue
        lines = pricing_lines(html) if html else []
        if len(lines) >= MIN_LINES:
            err = None
            break
        err = err or f"{fetch.__name__}: only {len(lines)} pricing lines"
    return tool, lines, err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--fail-on-change", action="store_true")
    args = ap.parse_args()
    tools = json.loads((DATA / "tools.json").read_text())
    if args.only:
        want = set(args.only.split(","))
        tools = [t for t in tools if t["id"] in want]
    SNAP.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    diffs, failed, baselined, same = [], [], [], 0
    with ThreadPoolExecutor(args.workers) as ex:
        results = list(ex.map(check, tools))
    for tool, lines, err in results:
        path = SNAP / f"{tool['id']}.json"
        if err:
            failed.append({"id": tool["id"], "url": tool["price_source_url"], "error": err})
            continue
        digest = hashlib.sha256("\n".join(lines).encode()).hexdigest()
        snap = {"id": tool["id"], "url": tool["price_source_url"], "fetched_at": now, "sha256": digest, "lines": lines}
        if not path.exists():
            baselined.append(tool["id"])
        else:
            old = json.loads(path.read_text())
            if old["sha256"] == digest:
                same += 1
                continue
            before, after = set(old["lines"]), set(lines)
            diffs.append({"id": tool["id"], "name": tool["name"], "url": tool["price_source_url"],
                          "previous_fetch": old["fetched_at"], "fetched_at": now,
                          "added": [l for l in lines if l not in before],
                          "removed": [l for l in old["lines"] if l not in after]})
        path.write_text(json.dumps(snap, indent=1, ensure_ascii=False) + "\n")
    report = {"checked_at": now, "checked": len(tools), "unchanged": same, "baselined": baselined,
              "changed": diffs, "failed": failed}
    (DATA / "pricing_diffs.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    print(f"checked {len(tools)}: {same} unchanged, {len(baselined)} baselined, {len(diffs)} changed, {len(failed)} failed")
    for d in diffs:
        print(f"  CHANGED {d['id']}: +{len(d['added'])} -{len(d['removed'])}  {d['url']}")
    for f in failed:
        print(f"  FAILED  {f['id']}: {f['error']}")
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a") as fh:
            fh.write(f"changed={len(diffs)}\n")
    sys.exit(1 if (args.fail_on_change and diffs) else 0)


if __name__ == "__main__":
    main()
