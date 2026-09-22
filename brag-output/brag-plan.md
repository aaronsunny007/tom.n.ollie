# Brag Plan: Tom & Ollie

## What is this app?
A storefront relaunch for Tom & Ollie — Belfast artisan makers of handmade hummus, pesto, olives and sweet pepper drops — with a live catalogue, basket and checkout built from a FastAPI backend, no framework, no build step.

## The angle
This isn't a startup pitch — it's a market stall that grew a website. The video should feel like the actual stall: warm, handmade, a little playful (the tap-to-reveal hero cards), grounded in real product photography, not generic e-commerce chrome.

## Hook (first 2-3 seconds)
The hero's green→black→maroon gradient fills the frame, eyebrow "St George's Market, Belfast" ticks in, then the headline slams: "Handmade hummus, pesto, olives & sweet pepper drops."

## Key moments (the middle)
- The three hero cards flipping — tap, flip, reveal real pack photography (Beetroot Hummus, Red Pepper Drops, House Mix olives).
- The shop grid: category pills switching (Hummus → Pesto → Olives → Sweet Pepper Drops), product cards tilting in with real pack shots and live prices.
- Add-to-basket: a card's "Add" is tapped, the basket icon count increments, the basket drawer slides in with a running subtotal.

## Outro / punchline
Wordmark "Tom & Ollie" on the forest ground, tagline beneath: "Twenty lines, four ranges, one stall in Belfast." Ticker loop fades under it.

## User flow worth showing
1. Entry — land on the hero, tap a flip card to reveal the product behind it.
2. Key action — browse the shop grid, filter by category.
3. Result — add a product to the basket; the basket count and drawer update live.

## Tone
- Preset: default
- Creative direction: a warm, handmade-market showcase — the stall's own energy (small batch, no shortcuts) translated to screen, not corporate e-commerce.
- Interpretation: playful but grounded — comfortable 3–5s scenes, mixed-case type, crossfade/slide transitions, humor comes from the product's own charm (flip cards, real pack shots) rather than jokes.

## Format: landscape — 1920x1080
## Duration: 20s

## Visual identity (from the project)
- Background: `#f9f0e4` (cream), dark ground `#12251b` (forest) for header/market/outro
- Accent: `#e0522c` (orange, primary action); `#b8d44f` (lime, secondary — text-unsafe on cream, use `--lime-dark`/fills only)
- Category accents: hummus `#d9607a`, pesto `#5a9e4b`, olives `#1f6b52`, sweet pepper drops `#e0892c`
- Text: forest `#12251b` on cream; cream `#f9f0e4` on forest
- Display font: Young Serif (headings, weight 400 only — never bold)
- Body font: Hanken Grotesk
- Strongest visual element: the three click-to-flip hero cards revealing real pack photography over the green→black→maroon gradient

## Share copy (draft)
Handmade hummus, pesto, olives & sweet pepper drops — twenty lines, four ranges, one stall in Belfast. Now live online. 🫒

## Audio direction
- Role: warm bed, moderate SFX at key moments
- Music: `happy-beats-business-moves-vol-9-by-ende-dot-app.mp3` — mid-energy, slightly laid-back, 114.84 BPM
- Music treatment: starts at 0, volume ~0.35, gentle fade-in over first 0.4s, fade-out in the last ~0.6s of the outro
- Music cue guidance: preset read (`vol-9.music-cues.md`). Strong-cue locks: scene transitions target 2.65s, 6.34s, 11.60s, 15.81s (all strong_beat, intensity ≥0.99). Scene durations below are set to land on these cues within tolerance.
- Audio-reactive treatment: subtle — hero glow/gradient warmth may breathe slightly with RMS; no waveform/equalizer visuals
- SFX posture: moderate — 4-5 cues at key moments (card flip, category switch, add-to-basket, outro)
- Audio-coupled moments: flip-card tap (interface/card sound), category pill switch (ui/switch), add-to-basket tap + basket count increment (interface/click + soft success accent)
- Restraint rule: never let SFX or beat-snap pull text off screen before its reading floor; card flips and pill switches get sound, but no more than one accent per 0.5s

## Storyboard

### Scene 1 — Hook — 2.65s
Full-bleed hero gradient (green→black→maroon). Eyebrow "St George's Market, Belfast" fades up first, then headline "Handmade hummus, pesto, olives & sweet pepper drops" slams in (mixed case, Young Serif).
Sequential/interaction: none
Audio intent: warm anticipation, the stall opening for the day
Audio-coupled idea: none — let the music bed carry the open
Music: mid-energy bed fades in
Transition mood: clean crossfade → Scene 2

### Scene 2 — Flip reveal — 3.69s (2.65–6.34s)
The three hero flip-cards arrive, then one by one a cursor taps each — the card flips (front gradient card → back real pack photo): Beetroot Hummus, Red Pepper Drops, House Mix olives.
Sequential/interaction: yes — three flip-card taps in quick succession, each flip completing before the next starts
Audio intent: playful discovery, like flipping through stall samples
Audio-coupled idea: a card-flip/interface sound on each tap, landing near the beat grid
Music: mid-energy bed continues
Transition mood: clean slide → Scene 3

### Scene 3 — Shop the collection — 5.26s (6.34–11.60s)
Category pills switch across the top (Hummus → Pesto → Olives → Sweet Pepper Drops), each switch triggering 2-3 product cards to tilt in with real pack-shot photography and a live price. Category-accent color bar on each card matches the active pill.
Sequential/interaction: yes — pill switches drive card sets arriving in sequence, cards tilt in on entrance
Audio intent: energetic browsing, the collection coming alive
Audio-coupled idea: a soft switch/toggle sound on each pill change, card-arrival sound on the strongest card of each set
Music: mid-energy bed, strongest section
Transition mood: clean slide → Scene 4

### Scene 4 — Add to basket — 4.21s (11.60–15.81s)
Cursor taps "Add" on a product card. The header basket icon's count increments (0→1). The basket drawer slides in from the right showing the item and a running subtotal.
Sequential/interaction: yes — simulated tap, then count increment, then drawer slide-in as one connected beat
Audio intent: satisfying completion, a small win
Audio-coupled idea: click sound on the tap, a light success accent when the count increments
Music: bed starts to settle toward the outro
Transition mood: soft crossfade → Scene 5

### Scene 5 — Outro — 4.19s (15.81–20.00s)
Cut to the forest ground. Logo mark + wordmark "Tom & Ollie" center, tagline beneath: "Twenty lines, four ranges, one stall in Belfast." Ticker strip ("Made in Belfast · Small batch · St George's Market · No shortcuts") loops faintly beneath before the final hold.
Sequential/interaction: none
Audio intent: warm close, confident but unhurried
Audio-coupled idea: one soft bell/impact accent as the wordmark lands, then music fades out
Music: fades out over the last ~0.6s
Transition mood: hold on black-forest → end

**Music mood for this video:** upbeat (mid-energy, business-warm)
**Audio summary:** A warm, mid-energy bed (vol-9) runs the full 20s at moderate volume with a gentle fade-in and fade-out; 4-5 tasteful SFX mark the flip-card taps, category switches, the basket add, and the final wordmark landing — nothing louder or busier than the actual product photography.
