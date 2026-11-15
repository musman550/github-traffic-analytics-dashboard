# Changelog

## 4.0.0 - 2026-11-15
- Faster first paint: scripts load deferred and static assets are versioned, so updates never serve stale files
- Installable web app with offline cache for the last loaded data
- Crawlable repositories index with descriptions, languages, stars and traffic
- Public status page with the history of collection runs, plus alerts for failed runs, traffic spikes and finished weekly reports (GitHub issues, optional Telegram) and a daily watchdog
- Command palette (Ctrl/Cmd+K), chart PNG download and accessible data tables
- Social preview images for weekly reports, previous/next report links, changelog, CITATION.cff and search-engine verification hooks

## 3.0.0 - 2026-11-15
- Fixed charts breaking after a theme change and the wrong tab after closing a repository dialog
- Statistics now end two days back because GitHub finalises days after 24-48 hours
- Fixed fetch scheduling: clones no longer make every repository active; a full refresh dropped from 1,072 to about 680 API calls and normal days use roughly 250-350
- Settings panel, shareable filter URLs, gainers and decliners, 7-day average, calendar heatmap
- Weekly reports with Atom feed, FAQ, two guides, open data page, CSV downloads and badge endpoints
- Pre-publish site audit, CI, pinned GitHub Actions and IndexNow notifications

## 2.0.0 - 2026-11-14
- Tabbed dashboard with repository detail view, compare, filters, pagination and CSV export
- Automatic profile links, insights, metadata audit and richer structured data
- Private repositories removed from collection and publication entirely

## 1.0.0 - 2026-11-14
- First release: daily collection of views, clones, referrers and stars with permanent history on GitHub Pages

