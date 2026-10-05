# JSST 2026 — conference presentation (20 min)

Slides for **"An Integrated CFD Workflow Platform for In-House Solvers: Modular
Architecture and AI-Assisted Implementation"** (Lu, Chen, Kuo — NCHC / NIAR).

Transcribed from `../JSST2026_v1.pdf` / `.docx` (the 2026-07-06 revision).

## Files

| File | What it is |
|---|---|
| `JSST2026_slides.pptx` | Editable PowerPoint, 16:9, 19 slides, speaker notes on every slide |
| `index.html` | Self-contained HTML deck — images embedded, no network needed |
| `JSST2026_slides.pdf` | Print/backup copy, generated from the HTML deck |
| `build_deck.py` | Regenerates all three from one content source |
| `figures/` | Cropped, optimised renders used on slides 7 and 9 |

## Presenting

**PowerPoint** — open the `.pptx`. Speaker notes are in the notes pane; use
Presenter View. **Note:** the real font is Arial everywhere, so it travels well.

**HTML** — open `index.html` in any browser, then press `F` for fullscreen.

| Key | Action |
|---|---|
| `→` / `Space` / `PageDown` | next slide |
| `←` / `PageUp` | previous slide |
| `Home` / `End` | first / last |
| `F` | fullscreen |
| `P` | print → PDF |
| `N` | dump the current slide's speaker notes to the console |

Deep-link to a slide with `index.html#12`. The progress bar at the top shows position.

## Talk structure (~20 min)

| # | Slide | ~min |
|---|---|---|
| 1 | Title | 0:30 |
| 2–3 | Problem: mature solvers, poor adoption; UNICONES | 2:00 |
| 4 | Three contributions | 1:00 |
| 5–9 | Architecture and the four modules | 5:00 |
| 10–11 | **The Solver Adapter** — the key idea | 3:00 |
| 12–15 | AI-assisted development methodology | 5:00 |
| 16 | The three layers of human oversight | 1:30 |
| 17 | Conclusion | 1:00 |
| 18 | Future work / thanks | 1:00 |

Slide 13 ("Text was not enough") is the strongest slide in the methodology half —
it's the concrete story, and worth spending an extra 30 s on if you have it.

## Editing

Content lives in the `SLIDES` list at the top of `build_deck.py` — one dict per
slide, with `notes` holding the speaker script. Edit there and re-run:

```bash
python3 build_deck.py
```

That rewrites the `.pptx` and `index.html`. The PDF is a separate step, since it
needs a browser:

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --disable-gpu --no-pdf-header-footer \
  --print-to-pdf="$PWD/JSST2026_slides.pdf" "file://$PWD/index.html"
```

Alternatively edit the `.pptx` directly in PowerPoint — but the HTML deck will then
diverge, since it is generated from `build_deck.py` rather than from the `.pptx`.

## Figures

Slides 7 and 9 use real platform output, taken from the repo and cropped:

| Slide | Source |
|---|---|
| 7 — Mesh Generator | `Results/png/ogrid.png` (`multiblock_ogrid`) |
| 9 — Results Visualization | `Results/pipeline/naca_demo_M.png` |

Both are matplotlib output from the platform itself, so they show what the pipeline
actually produces rather than an illustration of it. If you replace them, keep the
file names in `figures/` and re-run `build_deck.py`.

## Accuracy note

Every figure quoted on a slide is traceable to a sentence in the paper — the 5→1
tools, ~20→~5 steps, 2 weeks→2 days, <150 lines, ~70–80% AI-generated, 2–5
correction rounds, ~4–6 weeks, 69 files / 18,000 lines. Where the paper hedges
("estimated", "informal observation", "case-study observations rather than
controlled experimental results"), the slide keeps the hedge, and slides 14 and 15
state it explicitly. Nothing is rounded up.
