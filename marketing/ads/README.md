# Villainy ads (Reddit and Tumblr)

Four simple ads, each in three sizes, in `out/`:

| Size | File suffix | Use it for |
|---|---|---|
| 1200×628 | `-land-` | Reddit feed (landscape) |
| 1080×1080 | `-sq-` | Reddit or Tumblr (safe everywhere) |
| 1080×1350 | `-tall-` | Tumblr dashboard, Reddit mobile feed (4:5) |

Click-through for all of them: `https://villainy.win`. Call-to-action button on
Reddit: **Sign Up**.

## Post text

**Ad 1: Every evil plan needs a plan.**
- Reddit headline: Every evil plan needs a plan. Villainy turns your grand scheme into a skill tree you can actually finish.
- Tumblr: every evil plan needs a plan 🦹 villainy splits your plot into schemes and stacks the machinations in tiers. tick them off, watch them fill. #productivity #planning #villain #adhd

**Ad 2: World domination, one tier at a time.**
- Reddit headline: World domination, one tier at a time. A planner for big, sprawling projects where the next tier only opens when the last is done.
- Tumblr: world domination, one tier at a time. a planner for grand many-stranded schemes (or just your 14 half-finished projects) #productivity #villaincore #planning

**Ad 3: Henchmen not included.**
- Reddit headline: Henchmen not included. Everything else you need to finally finish the scheme you started three months ago.
- Tumblr: henchmen not included. everything else you need to finish the scheme you abandoned in march. #productivity #adhd #villain #projects

**Ad 4: Monologue less. Machinate more.**
- Reddit headline: Monologue less. Machinate more. Turn your sprawling master plan into a skill tree you can tick off.
- Tumblr: monologue less. machinate more. villainy turns the master plan into a skill tree. #villaincore #productivity #planning

## Editing or re-rendering

`ad.html` is the template (`?ad=1..4&fmt=land|sq|tall`); the headline and
subline for each ad are in its `ADS` object (the subline is no longer drawn). To re-render all twelve PNGs:

```bash
cd marketing/ads && node render.js
```

It needs Playwright and network access to Google Fonts (Manrope).
