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
- **Comments** via GitHub Discussions (giscus), loaded only when the Comments tab is opened

## How it works

1. `collect.yml` runs daily (and a full refresh weekly) on GitHub Actions.
2. `collector.py` reads views, clones, referrers and paths and merges them by date into `docs/data/series.json`.
3. `profile.py` refreshes the profile and links; `aggregator.py` builds `summary.json`; `insights.py` writes the insight sentences.
4. `site.py` renders every HTML page, structured data, `llms.txt`, sitemap and robots.
5. GitHub Pages serves `docs/`. Visitors read static JSON only; they never call the GitHub API.

## Rate limits

GitHub returns a rolling 14-day window per call, so repositories do not all need a daily fetch: active repositories are fetched daily, idle ones every 3 days and dormant ones weekly, staggered by a stable hash. Calls are sequential with retry and back-off, and the run stops and saves progress if the remaining hourly budget drops below a safety floor.

## Security

Content-Security-Policy with no inline scripts, all repository text escaped before rendering, `main` branch protected, CODEOWNERS, Dependabot, secret scanning with push protection, private vulnerability reporting (see [SECURITY.md](SECURITY.md)).

## Score

`score = views_30d + 0.5 × clones_30d + 2 × unique_visitors_14d + 3 × stars + 4 × forks`

## Run it for your own account

1. Fork this repository.
2. Create a token with the `repo` scope and save it as the secret `GH_PAT`.
3. Edit `config/config.json` (`site_url`, `repo_full_name`) and `.github/CODEOWNERS`.
4. Enable GitHub Pages: Settings → Pages → Deploy from branch → `main` / `docs`.
5. Run **Collect GitHub traffic** once from the Actions tab (tick *force_full*).

Tests: `PYTHONPATH=src python -m unittest discover -s tests`

## FAQ

**How can I see GitHub traffic older than 14 days?** GitHub does not provide it; it has to be stored daily, which is what this project does.

**Why are unique visitors not summed over weeks or months?** GitHub gives a deduplicated estimate for its 14-day window only; adding daily values would count the same person many times.

**Why do the newest days change?** GitHub can take 24-48 hours to finalise a day.

**Do clones include bots?** Yes: CI systems, mirrors and crawlers clone repositories too, so views are the stronger signal.

## License

MIT
