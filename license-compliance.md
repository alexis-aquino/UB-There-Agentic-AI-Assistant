---
name: license-compliance
description: Use when starting a project, adding or upgrading dependencies, copying code or assets from elsewhere, or preparing a release, so the app's own license, third-party licenses and attribution obligations are handled correctly.
---

# License Compliance

Every dependency, font, icon, image and snippet comes with a license, and some licenses impose duties on the app that ships them. This skill keeps those duties visible and met. It is practical guidance, not legal advice: when something is genuinely ambiguous or high-stakes (a commercial launch built on a copyleft dependency, a dispute, a dual-licensing deal), say so and recommend the user check with a lawyer.

## 1. Choose the project's own license early

Ask the user once, before the first public commit, whether the app is:

- **Closed source / commercial** (code stays private): no `LICENSE` grants rights; add a short `LICENSE` stating "Copyright (c) <year> <owner>. All rights reserved." so the intent is explicit.
- **Open source, permissive** (anyone can reuse, including commercially): **MIT** by default; **Apache-2.0** if patent protection matters or contributors are expected.
- **Open source, copyleft** (derivatives must stay open): **GPL-3.0** for apps distributed to users, **AGPL-3.0** if network/SaaS use should also trigger sharing, **MPL-2.0** for file-level copyleft.

Then:
- Put the full license text in `LICENSE` at the repo root (use the canonical text from choosealicense.com or spdx.org, never paraphrase).
- Set the SPDX identifier in the package manifest (`"license": "MIT"` in package.json, `license = "MIT"` in pyproject.toml/Cargo.toml) or `"UNLICENSED"` / `private: true` for closed source.
- Never change the license of code the user doesn't own.

## 2. Know the license categories

| Category | Examples | Usable in a closed commercial app? | Main obligations |
|---|---|---|---|
| Permissive | MIT, BSD-2/3, ISC, Apache-2.0, Zlib, 0BSD, Unlicense, CC0 | Yes | Keep copyright and license notice; Apache-2.0 also requires keeping NOTICE files and stating changes |
| Weak copyleft | LGPL-2.1/3.0, MPL-2.0, EPL-2.0 | Usually yes, with care | Share changes to the library itself; LGPL needs dynamic linking or relinkable objects |
| Strong copyleft | GPL-2.0, GPL-3.0 | Not if you distribute the app (desktop, mobile, on-prem) without releasing your source | Entire combined work under GPL when distributed |
| Network copyleft | AGPL-3.0, SSPL | Not for SaaS without releasing source | Triggered by users interacting over a network |
| Source-available / non-commercial | BSL/BUSL, Elastic License, Commons Clause, PolyForm Noncommercial, CC BY-NC | Often no | Read terms: often bans competing hosted services or commercial use |
| No license | Code on GitHub with no LICENSE file, StackOverflow-era snippets without clear terms | No | All rights reserved by default; don't use |

Key nuances to state when relevant:
- GPL obligations trigger on **distribution**. A web backend that is never distributed can use GPL code; a mobile or desktop app cannot (without open-sourcing). AGPL closes that SaaS gap.
- Apple's App Store terms are generally considered incompatible with GPL; avoid GPL code in iOS apps.
- Dev-only tools (linters, test runners, build tools not bundled into output) rarely create obligations for the shipped app.
- Dual-licensed packages ("MIT OR Apache-2.0") let you pick either.

## 3. Before adding a dependency

1. Check its license (package registry page, the repo's LICENSE file, or `npm view <pkg> license`).
2. If it is copyleft, source-available, non-commercial, unknown or missing, stop and tell the user before adding it, with one or two permissively licensed alternatives.
3. Note that the license can differ between versions; a package relicensed from open source to BSL (as several databases and tools have done) may only be safe at an older version.

## 4. Audit existing dependencies

Run the ecosystem's tool, including transitive dependencies:

- JavaScript/TypeScript: `npx license-checker-rseidelsohn --summary` (or `license-checker`), `pnpm licenses list`
- Python: `pip-licenses --from=mixed --order=license`
- Rust: `cargo deny check licenses` (or `cargo-about`)
- Go: `go-licenses report ./...`
- Ruby: `license_finder`
- Java/Kotlin: Gradle `com.github.jk1.dependency-license-report` or Maven `license-maven-plugin`
- Multi-language / containers: `syft` to produce an SBOM, or ScanCode Toolkit for deep scans

Report as a short table grouped by category, and flag anything copyleft, unknown, or not matching the project's chosen license policy. For ongoing protection, propose an allowlist in CI (`license-checker --onlyAllow "MIT;ISC;BSD-2-Clause;BSD-3-Clause;Apache-2.0;0BSD;CC0-1.0;Unlicense"`, `cargo deny`, or GitHub's dependency review action with `allow-licenses`).

## 5. Third-party notices (attribution)

Most permissive licenses require shipping their copyright and license text with the app. Before release:

- Generate `THIRD_PARTY_NOTICES.md` (or `.txt`) listing each production dependency, its version, license, copyright line and full license text, using the audit tool's output (for example `license-checker --production --out THIRD_PARTY_NOTICES.txt`, `cargo about generate`, `pip-licenses --with-license-file --format=plain-vertical`).
- Include contents of any Apache-2.0 `NOTICE` files verbatim.
- Make it reachable by end users: an "Open source licenses" / "Acknowledgements" screen in mobile and desktop apps, a `/licenses` page or footer link for web apps, and the file bundled in downloadable builds.
- Regenerate it on every release; a stale notices file is a common gap.

## 6. Code, assets and AI output from elsewhere

- **Copied code snippets** (blog posts, gists, Stack Overflow, other repos): only use if the license is known and compatible. Stack Overflow content is CC BY-SA, which requires attribution; add a comment with the source URL and license, or rewrite it independently.
- **Fonts**: Google Fonts are mostly SIL OFL (fine for apps, keep the license). Commercial fonts often limit web embedding, app embedding or pageviews; check the specific license tier.
- **Icons and illustrations**: Lucide, Heroicons, Tabler, Phosphor are permissive; Font Awesome Free is mixed (icons CC BY 4.0, code MIT, fonts OFL); many packs require attribution.
- **Images, video, audio**: stock licenses vary (Unsplash and Pexels have their own permissive licenses; others restrict resale or require credits). Don't use images found via search without a clear license.
- **AI-generated code and assets**: review for verbatim copies of licensed code (especially long, distinctive blocks) and never include output that reproduces someone else's licensed work with its notice stripped.
- Record each non-code asset and its license in an `ASSETS.md` or in the notices file.

## 7. Contributions and ownership

- If others will contribute, state the inbound terms: a simple "contributions are licensed under the project license" line in CONTRIBUTING.md (inbound = outbound), or a DCO sign-off; a CLA only if the user plans to relicense or dual-license.
- If contractors or friends write code for a commercial app, remind the user that ownership should be assigned in writing.

## 8. Also on the release checklist

- **Terms of Service and Privacy Policy** are separate from code licenses but needed for most apps that have accounts or collect data; flag them if missing.
- **Trademarks**: a permissive license does not grant use of a project's name or logo (Apache-2.0 says so explicitly). Don't name the app after, or use the logo of, another product.
- **Export / crypto**: shipping strong encryption may require an export compliance answer in app store submissions (Apple asks every upload).

## Workflow

1. New project: settle the project license (section 1) and add a license allowlist to CI.
2. Every new dependency, font, icon set or copied snippet: check its license first (sections 3 and 6).
3. Before each release: run the audit (section 4), regenerate third-party notices (section 5), and summarize in 2-4 lines what was checked, anything flagged, and anything the user must decide.
