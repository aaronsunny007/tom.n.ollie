# Hyperframes Composition Brief: Tom & Ollie

## Objective
Create a short launch-style brag video for Tom & Ollie's storefront relaunch.

## Output
- Composition directory: `brag-output/composition/`
- Rendered video: `brag-output/brag.mp4`
- Format: landscape — 1920x1080
- Duration: 20 seconds

## Source Material
- Project root: `/home/user/tom.n.ollie`
- Primary files read: `frontend/index.html`, `frontend/css/style.css`, `frontend/README.md`, `README.md`
- Product name: Tom & Ollie
- Tagline / strongest claim: "Small batches, honest ingredients, made the way we've always made them. Twenty lines, four ranges, one stall in Belfast."
- Key UI or visual moment to recreate: the three click-to-flip hero cards (front gradient face → real pack photo on flip), the category-filtered shop grid with tilt-on-hover product cards, and the basket drawer.
- Copy that must appear verbatim:
  - "Handmade hummus, pesto, olives & sweet pepper drops"
  - "St George's Market, Belfast"
  - "Twenty lines, four ranges, one stall in Belfast."
  - "Made in Belfast" / "Small batch" / "St George's Market" / "No shortcuts" (ticker)

## Creative Direction
- Tone preset: default
- Creative direction: a warm, handmade-market showcase — the stall's own energy (small batch, no shortcuts) translated to screen, not corporate e-commerce.
- Interpretation: playful but grounded — comfortable 3-5s scenes, mixed-case Young Serif/Hanken Grotesk type, crossfade/slide transitions, humor comes from the product's own charm (flip cards, real pack shots), not jokes.
- Angle: This isn't a startup pitch — it's a market stall that grew a website. The video should feel like the actual stall: warm, handmade, a little playful, grounded in real product photography.
- Hook: hero gradient fills frame, eyebrow "St George's Market, Belfast," then headline slams: "Handmade hummus, pesto, olives & sweet pepper drops."
- Outro / punchline: wordmark "Tom & Ollie" on the forest ground, tagline "Twenty lines, four ranges, one stall in Belfast."
- Avoid:
  - Generic SaaS language
  - Abstract filler visuals
  - Unrelated visual redesign — stay inside the shipped palette/type/asset system

## Visual Identity
- Background: `#f9f0e4` (cream); dark ground `#12251b` (forest)
- Text: `#12251b` on cream, `#f9f0e4` on forest
- Accent: `#e0522c` (orange, primary); `#b8d44f` (lime, secondary — fills/badges only, not text on cream)
- Category accents: hummus `#d9607a`, pesto `#5a9e4b`, olives `#1f6b52`, sweet pepper drops `#e0892c`
- Display font: Young Serif (headings, weight 400 only)
- Body font: Hanken Grotesk
- Visual references from the project: hero green→black→maroon gradient, three flip cards, product pack photography under `frontend/assets/products/`, logo at `frontend/assets/logo.png`

## Storyboard
Use the storyboard in `brag-output/brag-plan.md` as the creative contract.

Scene summary:
1. Hook — 2.65s — hero gradient, eyebrow, headline slam
2. Flip reveal — 3.69s — three hero cards tap-flip to reveal real pack photos
3. Shop the collection — 5.26s — category pills switch, product cards tilt in with real photography and prices
4. Add to basket — 4.21s — tap "Add," basket count increments, drawer slides in with subtotal
5. Outro — 4.19s — forest ground, wordmark, tagline, ticker fade

## Audio
- Audio role: warm bed, moderate SFX at key moments
- Audio arc: bed fades in under the hook, runs at moderate volume through the middle scenes, settles and fades out under the outro
- Music: `happy-beats-business-moves-vol-9-by-ende-dot-app.mp3`
- Music treatment: start at 0, volume ~0.35, ~0.4s fade-in, ~0.6s fade-out at the end
- Music cue guidance: bundled preset at `brag-output/composition/assets/music/cues/happy-beats-business-moves-vol-9-by-ende-dot-app.music-cues.json` (also see `.md`). Strong cues to consider for scene transitions: 2.65s, 6.34s, 11.60s, 15.81s (all strong_beat, intensity ~0.99-1.00).
- Audio-reactive treatment: subtle — hero glow/gradient warmth may breathe slightly with RMS; no waveform/equalizer visuals
- Audio-coupled moments:
  - Scene 2 flip-card taps — card/interface sound per flip, roughly on the beat grid
  - Scene 3 category pill switches — soft switch/toggle sound per switch; card-arrival accent on the strongest card of each set
  - Scene 4 add-to-basket — click on tap, light success accent on count increment
  - Scene 5 outro — one soft bell/impact accent as the wordmark lands, then music fade
- SFX selection guidance: match the visible gesture (flip → card sound, pill toggle → switch sound, tap → click sound); keep density moderate, no more than one accent per 0.5s
- SFX analysis guidance: `<skill-dir>/assets/sfx/sfx-analysis.md` — prefer low/medium high-frequency-risk files for these repeated, polished moments
- Exact SFX choice: Hyperframes should choose filenames, timestamps, density, and volume based on the implemented animation
- Audio files: music copied into `brag-output/composition/assets/music/`; Hyperframes copies any SFX it selects into the same `assets/` tree

## Hyperframes Instructions
Load the composition-building Hyperframes domain skills — `hyperframes-core` (composition contract + `data-*` timing), `hyperframes-animation` (motion), `hyperframes-creative` (design spec, beats, audio-reactive), `hyperframes-keyframes` (seek-safe keyframes), and `hyperframes-cli` (lint/check/render). `/brag` is its own workflow: do not enter the `hyperframes` entry-point intent interview and do not route into its generic promo/launch-video workflow. Prefer native Hyperframes conventions over anything in `/brag`.

Requirements:
- Show at least one real UI, copy, or visual element from the source project (flip cards, shop grid, basket drawer, real pack photography).
- Keep all text readable in the final render.
- Keep the video within 15-25 seconds (target 20s).
- Include the planned music/SFX layer.
- Treat `/brag` audio notes as guidance, not a fixed cue sheet. Choose SFX after the visual animation exists.
- Treat music cue metadata as optional timing hints; ignore cues that hurt readability, scene pacing, or the product story.
- Use 1-3 strong cue locks; sequential events (flip taps, pill switches, product cards) may snap to the beat grid within ±0.10s, per the reading-time floor for any text involved.
- Use local assets for audio and any required runtime/media dependencies.
- Run `hyperframes check` before render — it is brag's single gate.
