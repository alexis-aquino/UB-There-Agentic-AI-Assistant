---
name: distinctive-frontend-design
description: Use when building or restyling any web UI, page, component, landing page or app frontend, so the result has a deliberate visual identity instead of a generic AI look.
---

# Distinctive Frontend Design

Generic AI frontends come from defaults: the first font, the first color, the first layout that comes to mind. This skill replaces defaults with decisions. Every visual choice should be one you could defend in a sentence.

## 1. Pick a direction before writing code

Before any markup, decide and state in 3-5 lines:

- **Who it is for and what it should feel like.** Use concrete adjectives ("clinical and calm", "loud, zine-like, irreverent", "warm editorial", "brutalist utility"), never "modern and clean".
- **One reference world** the design borrows from: a print magazine, a transit map, a terminal, a museum placard, a 70s record sleeve, Swiss posters, a lab notebook, a luxury catalog. Translate its traits into the UI.
- **One signature element** a visitor would remember: an oversized display headline, an unusual grid, a distinctive color, a custom cursor or hover, a textured background, a striking illustration style.

Commit to that direction at full strength. A bold idea done halfway reads as generic too. Match ambition to the content: a minimal direction is valid when it is precise (tight spacing, exact type, restraint), not just empty.

If the project already has a brand or design system, honor it and push expression within its rules instead of inventing a new identity.

## 2. Typography

Type carries most of the personality.

- **Never default to** Inter, Roboto, Arial, Helvetica, Open Sans, Lato, Montserrat, Poppins or plain `system-ui` as the only face. Also avoid reaching for the same "tasteful" alternative every time (for example Space Grotesk on every project).
- Pair a **characterful display face** with a **readable text face**. Good sources: Google Fonts, Fontshare, or local font files. Examples to explore, not to repeat: Fraunces, Instrument Serif, DM Serif Display, Playfair Display, Syne, Unbounded, Bricolage Grotesque, Clash Display, Cabinet Grotesk, Satoshi, General Sans, IBM Plex (Sans/Serif/Mono), JetBrains Mono, Newsreader, Libre Caslon, Archivo, Familjen Grotesk.
- Use a real **type scale** with strong contrast: headlines much larger than body (often 3-6x), not a timid 1.25 step everywhere.
- Tune details: tighter letter-spacing on large display text, generous line-height (1.5-1.7) on body, max line length around 60-75ch, `font-feature-settings` for tabular numbers in data, small caps or uppercase tracking for labels.

## 3. Color

- Define colors as CSS custom properties (`--bg`, `--surface`, `--text`, `--muted`, `--accent`, ...) and use them everywhere.
- Choose a **dominant palette with one sharp accent** rather than many evenly weighted colors. Let the background itself carry identity (off-white paper, deep ink, warm sand, saturated color) instead of pure `#fff` with gray cards.
- **Avoid**: purple-to-blue or purple-to-pink gradients on white, indigo/violet `#6366f1`-style primaries by default, neon gradient text, and the Tailwind default palette used as-is.
- Check contrast (WCAG AA: 4.5:1 for body text). Distinctive never means illegible.
- Provide a dark theme that is designed, not inverted: adjust accent saturation and surface layering.

## 4. Layout and composition

- **Avoid the stock SaaS template**: centered hero with a headline, subtext and two buttons, then a row of three icon cards, then logos, then pricing, then a footer. If the content needs those parts, compose them differently.
- Use a deliberate grid and break it on purpose: asymmetry, overlapping elements, an off-center hero, full-bleed sections next to narrow text columns, a sidebar index, numbered sections, large negative space.
- Vary rhythm: not every section should be the same height with the same padding and the same card treatment.
- Prefer content-specific structure (a timeline, a table, a specimen, a map, a ledger) over generic cards. Not everything needs to be in a rounded box with a shadow.
- Make it work at phone width without horizontal scroll; recompose for mobile instead of only stacking.

## 5. Motion and interaction

- Spend motion on a few high-impact moments: an orchestrated page-load reveal with staggered delays, a meaningful hover state, a scroll-linked detail. One great moment beats twenty scattered micro-animations.
- Prefer CSS transitions and animations; use a motion library only when choreography needs it.
- Use custom easing (e.g. `cubic-bezier(0.22, 1, 0.36, 1)`) instead of `ease` / `linear` everywhere.
- Respect `prefers-reduced-motion`.
- Give every interactive element visible hover, focus-visible and active states that fit the direction.

## 6. Surface and detail

Add atmosphere where the direction supports it: grain or noise texture, subtle patterns, layered transparencies, hairline rules, duotone or treated imagery, custom illustrations or SVG shapes, distinctive borders (thick, dashed, offset shadows), a considered favicon and selection color.

Write real, specific copy. Placeholder marketing lines ("Unlock your potential", "Seamless experience", "Revolutionize your workflow") make any design look generated.

## 7. Generic patterns to avoid (checklist)

Before finishing, scan the result and remove any of these unless the brief explicitly asks for them:

- [ ] Inter/Roboto/system font everywhere
- [ ] Purple or blue-violet gradient on a white page, gradient text headlines
- [ ] Centered hero + two CTAs + three feature cards with emoji or generic line icons
- [ ] Every element in a `rounded-2xl` card with a soft drop shadow
- [ ] Glassmorphism blur panels with no reason to exist
- [ ] Uniform gray (`#f9fafb`/`#6b7280`) neutrals with no temperature
- [ ] Sparkle/rocket/lightning emoji as decoration
- [ ] Identical section padding and layout repeated down the page
- [ ] Stock "testimonial carousel" and "trusted by" logo strip filled with fakes
- [ ] Vague buzzword copy and lorem ipsum
- [ ] Animations that are all the same fade-up on every element

## 8. Workflow

1. Read the request and any existing code, brand or design tokens.
2. Write the direction (section 1) and the token set: fonts, type scale, color variables, spacing scale, radius, easing.
3. Build the structure with those tokens only; no ad hoc hex values or font sizes.
4. Add the signature element and the motion moments.
5. Run the section 7 checklist, check contrast, keyboard focus, mobile width and reduced motion.
6. If you can render it (a browser or screenshot tool), look at it and fix what looks off before calling it done.
7. In your summary, state the direction in one or two sentences so the user can steer it.
