# GitHub Traffic Analytics Dashboard

**Free, open-source GitHub traffic analytics dashboard.** Track repository views, clones, referrers (Google, Bing, Reddit…) and stars for all your public repositories, with daily, weekly, monthly and yearly history that goes far beyond GitHub's 14-day traffic limit. No server, no database and no cost: it runs on GitHub Actions and GitHub Pages, and the dashboard opens without any login.

**Live dashboard:** https://musman550.github.io/github-traffic-analytics-dashboard/

## Features

- **Permanent history** of views, clones and unique visitors for every public repository you own
- **Trends:** daily / weekly / monthly / yearly charts, weekday pattern, stars and forks growth, new repositories per day
- **Sources:** referrers with Google share over time, most viewed pages
- **Repositories:** search, filter (tier, language), sort, paginate, export CSV, compare up to 4 repositories, open any repository in a detail view with a shareable link (`#repo/<name>`)
- **Insights:** rule-based sentences computed from your numbers (momentum, concentration, spikes, busiest weekday, publishing cadence), language and topic breakdowns
- **Metadata audit:** transparent 0-100 checklist per repository (description, topics, license, homepage, recent push)
- **Tabs and deep links** instead of one long page; responsive header, body and footer; light and dark theme; keyboard shortcut `/` to search
- **Profile links added automatically** from your GitHub profile, social accounts and profile README, refreshed daily
- **Search / AI visibility:** server-rendered facts, JSON-LD (WebSite, WebApplication, Dataset, FAQPage, Organization), `llms.txt` and `llms-full.txt`, sitemap, robots rules for AI crawlers, open Graph image, methodology, about and privacy pages
- **Private repositories are never read, stored or shown**
- **Settings panel:** theme, start tab, rows per page, compact density, hide forks, reduce motion (saved only in your browser); shareable filter URLs such as `#repos?q=ai&tier=top`
- **Also:** 7-day moving average, calendar heatmap, biggest gainers and decliners, stale-data warning
- **Crawlable content:** weekly report pages (`/reports/`) with an Atom feed, FAQ, two guides, open-data page, CSV downloads and Shields.io badge endpoints
- **v4:** installable web app with offline cache, command palette (Ctrl/Cmd+K), chart PNG download and data tables, crawlable repositories index, public status page with run history, alert issues (failed runs, spikes, weekly reports; optional Telegram) and a daily watchdog, per-report social images, changelog and `CITATION.cff`
- **Comments** via GitHub Discussions (giscus), loaded only when the Comments tab is opened

## Badges

```
![views](https://img.shields.io/endpoint?url=https://musman550.github.io/github-traffic-analytics-dashboard/badges/views-30d.json)
```
Also available: `clones-30d.json`, `stars.json`, `repos.json`.

## How it works

1. `collect.yml` runs daily (and a full refresh weekly) on GitHub Actions.
2. `collector.py` reads views, clones, referrers and paths and merges them by date into `docs/data/series.json`.
3. `profile.py` refreshes the profile and links; `aggregator.py` builds `summary.json`; `insights.py` writes the insight sentences.
4. `site.py` renders every HTML page, structured data, `llms.txt`, sitemap and robots.
5. GitHub Pages serves `docs/`. Visitors read static JSON only; they never call the GitHub API.

## Rate limits

GitHub returns a rolling 14-day window per call, so repositories do not all need a daily fetch: repositories with views in the last 14 days are fetched daily (with referrers and paths), others every 3 days and dormant ones weekly. First fetches are spread over the cadence window. A typical day uses about 250-350 calls; a full weekly refresh about 700 of the 5,000 hourly allowance. Calls are sequential with retry and back-off, and the run stops and saves progress if the remaining hourly budget drops below a safety floor.

## Security

Content-Security-Policy with no inline scripts, all repository text escaped before rendering, `main` branch protected, CODEOWNERS, Dependabot, secret scanning with push protection, private vulnerability reporting (see [SECURITY.md](SECURITY.md)).

## Score

`score = views_30d + 0.5 × clones_30d + 2 × unique_visitors_14d + 3 × stars + 4 × forks`

## AI optimizer

An automatic, auditable optimizer (`optimize.yml`, Monday and Thursday) improves the metadata of public repositories:

- Picks up to 10 repositories (weak metadata first), skips forks, archived, excluded and generated-README repositories
- Descriptions are replaced only when weak; topics are only added when grounded in the README; clear junk topics are removed
- README summary, FAQ and related projects go in a marked block through a pull request (auto-merge after 3 days unless closed)
- Open-weight models through a fallback chain: keyless OVHcloud and Pollinations tiers work out of the box; Groq, Cerebras, GitHub Models, OpenRouter, Hugging Face, Mistral and Cloudflare are used when their keys exist; cooldowns, daily budgets, caching and stub detection; rule-based fallback when no model is available. `python -m ghintel.cli probe` (workflow *AI provider probe*) tests every provider live
- Output is sanitized (invalid parts are dropped: no links or hype, topics and numbers must be grounded in the README) and scored by a fact-check call on a different model
- Metadata changes are rolled back automatically after a clear traffic drop; everything is logged on the public [optimizer page](https://musman550.github.io/github-traffic-analytics-dashboard/optimizer/)

Optional provider keys (repository secrets): `GROQ_API_KEY`, `CEREBRAS_API_KEY`, `OPENROUTER_API_KEY`, `HF_TOKEN`, `MISTRAL_API_KEY`, `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID`. Manual runs default to a dry run.

## Optional settings

- `config/config.json` → `verification`: paste your Google Search Console or Bing Webmaster verification codes
- `notifications`: turn issue alerts or Telegram messages on or off; Telegram needs the secrets `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`

## Run it for your own account

1. Fork this repository.
2. Create a token with the `repo` scope and save it as the secret `GH_PAT`.
3. Edit `config/config.json` (`site_url`, `repo_full_name`) and `.github/CODEOWNERS`.
4. Enable GitHub Pages: Settings → Pages → Deploy from branch → `main` / `docs`.
5. Run **Collect GitHub traffic** once from the Actions tab (tick *force_full*).

Tests: `PYTHONPATH=src python -m unittest discover -s tests`. Before publishing, the workflow runs `scripts/audit_site.py` (strict HTML parse, duplicate ids, internal links, JSON-LD, sitemap targets, private-data markers); a failure blocks the commit.

## FAQ

**How can I see GitHub traffic older than 14 days?** GitHub does not provide it; it has to be stored daily, which is what this project does.

**Why are unique visitors not summed over weeks or months?** GitHub gives a deduplicated estimate for its 14-day window only; adding daily values would count the same person many times.

**Why do the newest days change?** GitHub can take 24-48 hours to finalise a day.

**Do clones include bots?** Yes: CI systems, mirrors and crawlers clone repositories too, so views are the stronger signal.

## License

MIT
