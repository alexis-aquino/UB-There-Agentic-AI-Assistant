---
name: privacy-and-data
description: Use when building or changing anything that collects, stores, shares or deletes user data (signup, profiles, analytics, emails, payments, uploads, third-party SDKs), or when the app needs a privacy policy, terms, cookie consent or account deletion.
---

# Privacy and Data

Privacy problems come from collecting more than needed, not knowing where data goes, and not being able to delete it. This skill keeps a clear map of personal data and builds the user-facing rights in from the start. It is practical guidance, not legal advice: for health, financial, children's or biometric data, or a launch in a regulated market, tell the user to have a lawyer review it.

## 1. Keep a data map

Maintain `docs/data-map.md` and update it whenever a feature touches personal data. One row per data item:

| Data | Why collected | Where stored | Shared with | Retention | Sensitive? |
|---|---|---|---|---|---|
| Email | Login, receipts | users table | Auth provider, email service | Until account deleted | No |

- "Personal data" is anything that identifies a person directly or in combination: name, email, phone, IP address, device IDs, location, photos, payment info, usage history tied to an account.
- "Sensitive" (extra care, often explicit consent): health, precise location, biometrics, race or ethnicity, religion, sexual orientation, political views, government IDs, financial account details, data about children.
- List every third party that receives data, including SDKs: analytics, crash reporting, ads, email, payments, auth, hosting, AI/LLM APIs. Each is a "processor" the privacy policy must mention.

## 2. Collect less

- Before adding a field, ask what feature needs it. If the answer is "might be useful later", don't collect it.
- Prefer coarse over precise: city instead of GPS, birth year or an "I'm over 13/16/18" checkbox instead of birth date.
- Don't send personal data to analytics or LLM APIs unless needed; strip or pseudonymize it first.
- Never collect data from children under 13 (US COPPA) or under 16 in parts of the EU without a deliberate plan for parental consent. If the app could attract kids, add an age gate and say so to the user.

## 3. User rights to build in

These are required under GDPR (EU/UK), CCPA/CPRA (California) and similar laws, expected by app stores, and cheap if built early:

- **Account deletion** from inside the app, not only by emailing support. Apple and Google both require in-app deletion for apps with account creation. Deletion removes or anonymizes the user's data across the database, file storage, and third parties that support deletion via API; backups age out on a stated schedule.
- **Data export**: a "Download my data" action producing JSON or CSV of the user's data.
- **Edit and correct**: users can change their profile data.
- **Opt out of marketing**: unsubscribe link in every marketing email; transactional emails (receipts, password resets) are separate.
- **Do Not Sell/Share**: if any data goes to ad networks or data brokers, a "Do Not Sell or Share My Personal Information" option is needed for California users.

## 4. Consent and cookies

- Strictly necessary cookies (login session, CSRF, cart) need no consent.
- Analytics, advertising and tracking cookies or SDKs need opt-in consent for EU/UK visitors before they load. Use a consent manager or build a simple banner with Accept / Reject equally prominent, and actually block the scripts until accepted.
- Prefer privacy-friendly analytics (Plausible, Fathom, PostHog with cookieless mode, self-hosted Umami) to avoid needing a banner at all.
- Mobile: request OS permissions (location, camera, contacts, tracking via Apple ATT) only at the moment they are needed, with a one-line reason.
- Record consent: what was agreed, when, and which policy version.

## 5. Privacy policy and terms

Draft `PRIVACY.md` (published at `/privacy`) in plain language from the data map, covering:
- Who runs the app and how to contact them.
- What data is collected, why, and the legal basis (contract, consent, legitimate interest).
- Third parties that receive data, and if data leaves the user's country.
- How long data is kept.
- User rights and how to use them (delete, export, correct, opt out), plus how to complain.
- Cookies and tracking.
- Children's data stance.
- Date of last update.

Draft `TERMS.md` (published at `/terms`) covering acceptable use, accounts, payments and refunds if any, content ownership for user uploads, termination, disclaimers and limitation of liability, and governing law.

Mark both clearly as drafts to review, and keep them in sync with the data map: a new third-party SDK means a policy update.

## 6. App store privacy disclosures

- Apple App Store "privacy nutrition label" and Google Play "Data safety" form must match what the app and its SDKs actually collect. Generate the answers from the data map.
- Apple requires a privacy manifest (`PrivacyInfo.xcprivacy`) declaring tracking domains and required-reason APIs, including those used by SDKs.
- Both stores require a public privacy policy URL.

## 7. Storage and access

- Personal data lives only where the data map says. No copies in logs, analytics events, error reports, or test fixtures (use fake data in tests and seed scripts).
- Restrict internal and admin access to personal data; log admin access to user records.
- Set retention: delete inactive accounts, old logs and temporary uploads on a schedule.
- If there is a data breach, the user may have legal notification deadlines (72 hours under GDPR). Keep a short incident note in `docs/` with who to contact.
- Security details for protecting this data are in the secure-defaults skill.

## Workflow

1. New project: create the data map, decide analytics and cookie approach, add age stance.
2. Each feature touching personal data: update the data map, apply "collect less", wire it into delete and export.
3. Before launch: generate the privacy policy and terms drafts, fill app store disclosures, test account deletion and export end to end.
4. At the end of a change, note in 1-3 lines any new data collected, new third party, or policy update the user needs to make.
