# Security policy

## Reporting a vulnerability
Please report security issues privately through
[GitHub security advisories](https://github.com/musman550/github-traffic-analytics-dashboard/security/advisories/new).
Do not open a public issue for vulnerabilities.

## Scope and design
- The site is static (GitHub Pages) and enforces a strict Content-Security-Policy.
- All repository text is HTML-escaped before it is rendered.
- Only public repositories are collected; private repositories are never read or stored.
- Only the repository owner can change code and data; `main` is protected.
