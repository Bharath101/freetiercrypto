# FreeTierCrypto

A static site that tracks what crypto tools give away for free and what their cheapest paid plan costs.
It covers charting, screeners, trading bots, tax software, wallets and hardware, on-chain analytics,
portfolio trackers, alerts, DEX tools, multi-chain and bridge tools, and token safety.

Each price comes from the vendor's own pricing page and links to it with the date it was checked.
Any field that could not be read there is marked `unverified`.

## Layout

| Path | What it is |
| --- | --- |
| `data/tools.json` | The dataset. Fields: name, url, category, chains, free tier limits, cheapest paid plan, source URL, date checked, best free alternative, affiliate program |
| `data/changelog.json` | Confirmed free tier changes. Starts empty |
| `site.json` | Site name, `base_url`, newsletter settings |
| `templates/` | Jinja2 templates: home table, category, changes, about, newsletter, 404 |
| `scripts/build.py` | Renders `dist/`, plus `sitemap.xml`, `robots.txt` and `.nojekyll` |
| `scripts/check_links.py` | Fails if any internal link in `dist/` is broken |
| `scripts/check_pricing.py` | Re-fetches each pricing page and diffs it against `data/snapshots/` |
| `.github/workflows/deploy.yml` | Builds and deploys to GitHub Pages on push to `main` |
| `.github/workflows/pricing-check.yml` | Daily at 08:00 IST: runs the pricing check, commits snapshots, opens an issue if anything changed |

## Local build

```bash
./run.sh            # builds into dist/ and serves it at http://localhost:8000/
```

In CI, `SITE_URL` comes from `actions/configure-pages`, so links work under `/<repo>/` on GitHub Pages.
Locally it falls back to `base_url` in `site.json`.

## Pricing checks

```bash
python scripts/check_pricing.py                  # all tools
python scripts/check_pricing.py --only koinly    # one tool
```

The first run saves a baseline snapshot for every page.
Later runs write the lines that changed to `data/pricing_diffs.json`.

A flagged diff is not a confirmed change. Sale banners, layout edits and prices shown in the visitor's
local currency also trigger it. To record a real change:

1. Open the source page and confirm the change.
2. Update `data/tools.json`.
3. Add an entry to `data/changelog.json` with `date`, `title`, `summary` and `source_url`.

## Newsletter

The newsletter uses the same mechanism as GTMStack Tracker, a beehiiv embed.
Until `newsletter.form_id` is set in `site.json`, the page shows a disabled placeholder form that collects nothing.
To go live:

1. Create a beehiiv publication.
2. Copy the form ID into `site.json`.
3. Rebuild.

## Rules

- Prices come only from the vendor's own pricing page or docs. Anything else is marked `unverified`.
- No wallet addresses, private keys, seed phrases or personal financial details anywhere in this repo.
- Not financial advice.
