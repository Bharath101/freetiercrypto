#!/usr/bin/env python3
"""Static site generator for FreeTierCrypto (adapted from CryptoStack / GTMStack Tracker).
Usage: python scripts/build.py [--out dist]   (set SITE_URL to override site.json base_url)"""
import argparse, datetime as dt, html, json, os, re, shutil
from pathlib import Path
from urllib.parse import urlparse
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CATS = {
    "charting": ("Charting", "Charting platforms and trading terminals."),
    "screeners": ("Screeners & market data", "Coin screeners, market-data sites and their APIs."),
    "trading-bots": ("Trading bots", "Automated trading, grid and DCA bots that connect to exchanges."),
    "tax": ("Tax software", "Crypto tax calculators and report generators."),
    "wallets-hardware": ("Wallets & hardware", "Self-custody software wallets and hardware signers."),
    "onchain-analytics": ("On-chain analytics", "On-chain data, research dashboards and query tools."),
    "portfolio-trackers": ("Portfolio trackers", "Apps that track holdings across exchanges and wallets."),
    "alerts": ("Alerts", "Price, whale and on-chain alert services."),
    "dex-tools": ("DEX tools", "DEX pair screeners, terminals and DEX data APIs."),
    "multi-chain": ("Multi-chain & bridges", "Cross-chain swap aggregators, bridges and multi-chain APIs."),
}
STATUS_LABEL = {"verified": "Verified", "partial": "Partly verified", "unverified": "Unverified"}
STATUS_HELP = {
    "verified": "The free tier and the cheapest paid price were both read from the vendor's own pricing page on the date checked.",
    "partial": "Some fields were read from the vendor's pricing page; the rest are marked unverified.",
    "unverified": "We could not read the pricing page (blocked, broken or not rendered), so the pricing fields are marked unverified.",
}
U = "unverified"


def load():
    site = json.loads((ROOT / "site.json").read_text())
    site["base_url"] = os.environ.get("SITE_URL", site["base_url"]).rstrip("/")
    site["base_path"] = urlparse(site["base_url"]).path.rstrip("/")
    tools = json.loads((DATA / "tools.json").read_text())
    by_id = {t["id"]: t for t in tools}
    for t in tools:
        assert t["category"] in CATS, t["id"]
        t["cat_name"] = CATS[t["category"]][0]
        t["status_label"] = STATUS_LABEL[t["verification"]]
        t["status_help"] = STATUS_HELP[t["verification"]]
        t["price_text"] = t["cheapest_paid"] if t["cheapest_paid"] == U else t["cheapest_paid"]["text"]
        t["price_sort"] = "" if t["cheapest_paid"] == U or t["cheapest_paid"].get("usd_per_month") is None else t["cheapest_paid"]["usd_per_month"]
        t["alt"] = by_id[t["best_free_alternative"]]
    log = sorted(json.loads((DATA / "changelog.json").read_text()), key=lambda c: c["date"], reverse=True)
    return site, tools, log


ROOT_REL = re.compile(r'((?:href|src|action)=")/(?!/)')


def prefix_links(text, base_path):
    """Rewrite root-relative URLs (href="/x") to live under the GitHub Pages sub-path."""
    return ROOT_REL.sub(lambda m: m.group(1) + base_path + "/", text) if base_path else text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "dist"))
    out = Path(ap.parse_args().out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    site, tools, log = load()
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["html", "xml"]))
    env.filters["nicedate"] = lambda d: dt.date.fromisoformat(d).strftime("%b %-d, %Y")
    tools = sorted(tools, key=lambda t: t["name"].lower())
    cats = [{"slug": s, "name": n, "blurb": b, "tools": [t for t in tools if t["category"] == s]} for s, (n, b) in CATS.items()]
    last = max(t["date_checked"] for t in tools)
    stats = {"tools": len(tools), "last": last, "cats": len(cats),
             **{k: sum(t["verification"] == k for t in tools) for k in STATUS_LABEL},
             "free": sum(t["has_free_tier"] == "yes" for t in tools),
             "affiliate": sum(t["affiliate_program"] == "yes" for t in tools)}
    common = dict(site=site, cats=cats, stats=stats, year=dt.date.today().year, nl=site.get("newsletter", {}))
    sitemap = []

    def render(tpl, path, sitemap_on=True, lastmod=None, **ctx):
        p = out / path.strip("/") / "index.html" if not path.endswith(".html") else out / path.strip("/")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(prefix_links(env.get_template(tpl).render(**common, path=path, **ctx), site["base_path"]))
        if sitemap_on:
            sitemap.append((path, lastmod))

    render("index.html", "/", lastmod=last, tools=tools,
           title=f"{site['name']}: free vs paid tiers of {len(tools)} crypto tools, compared",
           description=f"What {len(tools)} crypto charting, bot, tax, wallet, on-chain and DEX tools give you for free, the cheapest paid plan in USD, and the best free alternative. Every price links to its source and date checked.")
    for c in cats:
        render("category.html", f"/category/{c['slug']}/", lastmod=last, cat=c, tools=c["tools"],
               title=f"{c['name']}: free tiers vs paid plans | {site['name']}",
               description=f"{c['blurb']} Free tier limits and cheapest paid plan for {len(c['tools'])} tools, each with a pricing-page source and date checked.")
    render("changes.html", "/changes/", lastmod=log[0]["date"] if log else last, log=log,
           title=f"Free tier changes log | {site['name']}",
           description="A dated log of changes to crypto tools' free tiers and entry-level paid plans, flagged by an automated pricing-page check and confirmed by hand.")
    render("about.html", "/about/", lastmod=last, title=f"About, affiliate disclosure & disclaimer | {site['name']}",
           description="How FreeTierCrypto collects pricing, what 'verified' means, our affiliate disclosure, and why nothing here is financial advice.")
    if site.get("newsletter", {}).get("enabled"): render("newsletter.html", "/newsletter/", lastmod=last, title=f"Newsletter: free tier change alerts | {site['name']}",
           description="Get an email when a crypto tool cuts or expands its free tier, or changes its cheapest paid plan.")
    render("404.html", "404.html", sitemap_on=False, title=f"Page not found | {site['name']}", description="Page not found")
    shutil.copytree(ROOT / "static", out / "static")
    (out / "data").mkdir()
    for name in ("tools.json", "changelog.json"):
        shutil.copy(DATA / name, out / "data" / name)
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p, lm in sitemap:
        sm.append(f"  <url><loc>{html.escape(site['base_url'] + p)}</loc>" + (f"<lastmod>{lm}</lastmod>" if lm else "") + "</url>")
    sm.append("</urlset>")
    (out / "sitemap.xml").write_text("\n".join(sm) + "\n")
    (out / "robots.txt").write_text(f"# {site['name']}\nUser-agent: *\nAllow: /\n\nSitemap: {site['base_url']}/sitemap.xml\n")
    (out / ".nojekyll").write_text("")
    print(f"Built {len(sitemap)} pages ({len(tools)} tools, {len(cats)} categories) -> {out}")


if __name__ == "__main__":
    main()
