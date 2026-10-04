---
name: release-readiness
description: Use when preparing to launch, deploy to production, submit to an app store, or ship a major release, to run a pre-launch check covering config, security, data, monitoring, legal and store requirements.
---

# Release Readiness

Launches go wrong in predictable ways: a debug flag left on, a missing environment variable, no backups, no way to know the app is down, a store rejection. This skill runs a structured pre-launch check, fixes what can be fixed in code, and gives the user a short list of what only they can do.

## How to run it

1. Detect what applies: web app, API, mobile (iOS/Android), desktop; hosting provider; database; payments; user accounts.
2. Go through each section below, skipping items that don't apply.
3. For each item: check it in the code or config, fix it if it's a code change, otherwise add it to the user's list.
4. Write the result to `docs/release-checklist.md` with each item marked ✅ done, ⚠️ needs the user, or ➖ not applicable, and summarize in the reply: blockers first, then the user's to-do list.

Treat anything that could lose data, leak data, or take the app down as a **blocker**.

## 1. Configuration

- All required environment variables are documented in `.env.example` and set in production. The app fails fast with a clear message if one is missing.
- Debug mode, verbose errors, dev tools and test routes are off in production.
- Separate keys and databases for development, staging and production. No production secrets on developer machines or in CI logs.
- Live (not test) keys for payments, email, and auth providers in production, and webhook endpoints pointed at the production URL.
- Feature flags for unfinished work are off.

## 2. Security

- Run `/security-review` on the release branch and the dependency audit (`npm audit`, `pip-audit`, etc.); no high or critical findings left.
- Spot-check the secure-defaults essentials: secrets not in code, auth on every non-public route, row-level authorization, rate limits on login and paid-API endpoints, security headers, CORS allowlist.
- Default and test accounts removed; admin access protected.
- Repo has secret scanning and Dependabot or Renovate turned on.

## 3. Data and backups

- Automated database backups are on, with a known retention period, and a restore has been tested at least once. (Blocker if missing.)
- Migrations run cleanly on a copy of production data; destructive migrations have a rollback plan.
- User-uploaded files are in durable storage, not the server's local disk.
- Account deletion and data export work end to end (privacy-and-data skill).

## 4. Reliability and monitoring

- Error and crash reporting (Sentry, Bugsnag, Crashlytics, or the host's built-in) is installed and verified by triggering a test error.
- Uptime monitoring on the main URL and a `/health` endpoint, with alerts going to the user's email or phone (UptimeRobot, Better Stack, Checkly, or the host's).
- Logs are retained and searchable, with no secrets or personal data in them.
- Spending alerts and hard limits set on cloud, database and paid APIs (especially LLM APIs) to avoid surprise bills.
- Basic load check on the most expensive page or endpoint if a launch spike is expected.

## 5. Domain, hosting and delivery

- Custom domain configured, HTTPS everywhere, HTTP redirects to HTTPS, certificate auto-renews.
- `www` and apex domain both resolve and one redirects to the other.
- Transactional email domain has SPF, DKIM and DMARC records so emails don't land in spam.
- Static assets compressed and cached; images optimized.
- A rollback path exists: previous deploy can be restored in one step.

## 6. Product basics

- Custom 404 and error pages; empty states and loading states don't look broken.
- Main flows tested on real devices and browsers: signup, login, password reset, core feature, payment, logout, delete account.
- Basic accessibility pass: keyboard navigation, visible focus, alt text, contrast.
- Page title, meta description, favicon, social share image (Open Graph) set; `robots.txt` and sitemap for public sites; staging sites blocked from indexing.
- Support contact visible somewhere in the app.

## 7. Legal

- Privacy policy and terms published and linked from signup and the footer (privacy-and-data skill).
- Cookie consent in place if tracking scripts are used with EU/UK visitors.
- Third-party license notices generated and reachable (license-compliance skill); dependency license audit clean.
- Payments: refund policy stated; tax and sales tax handling decided (Stripe Tax, Paddle or Lemon Squeezy as merchant of record, etc.).

## 8. App store submission (mobile)

- **Both stores**: privacy policy URL, accurate privacy disclosures (Apple privacy label, Google Data safety), in-app account deletion if accounts exist, screenshots and descriptions, support URL, age rating questionnaire, demo account credentials for reviewers if login is required.
- **Apple**: privacy manifest present, App Tracking Transparency prompt if tracking, export compliance (encryption) answer, in-app purchases used for digital goods (Apple guideline 3.1), Sign in with Apple offered if other social logins are.
- **Google**: target API level meets the current Play requirement, closed testing requirements met for new personal developer accounts, Play Billing for digital goods.
- Version and build numbers incremented; release notes written.

## 9. After launch

- Watch error reports and uptime for the first 48 hours.
- Confirm backups ran and alerts arrive.
- Note anything skipped as follow-up in `docs/release-checklist.md` so it isn't lost.

## Summary format

End with:
- **Blockers** (must fix before launch), each with what's wrong and the fix.
- **Your to-do list**: items only the user can do (set a production secret, buy a domain, fill a store form, have a lawyer review terms).
- **Done**: one line with the count of items checked and fixed.
