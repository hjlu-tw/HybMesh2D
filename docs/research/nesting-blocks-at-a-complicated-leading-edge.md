# Nesting blocks at a complicated leading edge

**A RESEARCH NOTE, like the ten beside it.** Not `.claude/rules/*.md` (what the rule is), not
`docs/design_notes/` (why a shipped rule was chosen). It records what two vendor videos and the
vendor's own pages say about a method this repo has only read about secondhand. Nothing here is
binding; no rule, gate, test or source file was changed to write it. 2026-11-09.

**What was asked.** Two YouTube URLs, and "記錄下方法" — write down the method they teach.

**What the two videos are.** Both belong to **GridPro** (channel `@GridProHexa`), and both open on
the same series card, *Multi-block structures and their applications*:

| id | title | published | duration |
|----|-------|-----------|----------|
| `4Jeu-EUXXmo` | **C-Grid Mesh and Topology in GridPro** | 2022-04-19 | 2 min 10 s |
| `2FYLCyg8VSA` | **Meshing Airfoil with Icing** | 2022-03-29 | 3 min 33 s |

**[V]** — both titles from YouTube's own oEmbed endpoint and from the watch page's
`og:title` / `itemprop="name"` meta tags; dates from `itemprop="uploadDate"`; durations from
`itemprop="duration"` (`PT2M10S`, `PT3M33S`).

## How to read the markers

- **[V]** verified in a primary source I read myself (the vendor's own page, the video's own
  published frames, an HTTP response I made), or measured by me.
- **[I]** my own inference from a **[V]** fact. Stated as reasoning, not as fact.

**I could not read either transcript, and nothing below paraphrases a voiceover.** Each video
carries exactly one caption track and it is `kind=asr` — YouTube's machine transcription, not the
author's — and the `timedtext` endpoint returned **0 bytes** for every format I asked for
(default, `json3`, `srv3`, `vtt`). A second route (addressing the player API as a mobile client)
was refused by this environment's policy and was not pursued. **[V]** So the method below comes
from three places that are not the voiceover: the videos' own **burned-in on-screen captions and
status bars**, read off YouTube's published frames; **GridPro's own application article** for the
icing case; and the GridPro documentation this repo has already quoted in
`gridpro-blocking-method.md` and `cell-size-range-within-a-block.md`.

---

## 1. The two videos are one argument in two steps

**Taken together the pair teaches one thing: when a leading edge becomes geometrically
complicated, you add blocks *locally* around the feature rather than refining the grid
globally — and the C-grid is the baseline that makes room for it.** The C-grid video is the
simple case (a clean section, 57 blocks); the icing video is the same topology family with the
nose rebuilt (421 blocks), and its one legible on-screen caption names the operation that
does it. **[I]**, from the two **[V]** readings in §2 and §3.

## 2. The C-grid video: what it shows, and GridPro's own stated reason for it

**The case finishes at 57 blocks and 3,648 cells, in GridPro Workspace v8.1.** Read off the
status bar of the video's own published final frame
(`https://i.ytimg.com/vi/4Jeu-EUXXmo/maxresdefault.jpg`, 1280 x 720): `Num Blocks : 57`,
`Num Cells : 3648`, title bar `GridPro Workspace v8.1`. **[V]**

**3,648 is exactly 57 x 64, so every block in that case carries an 8 x 8 grid — the uniform
default, untouched.** **[I]** from the two **[V]** counts. For scale, GridPro's own 2-D airfoil
tutorial — already measured in `gridpro-blocking-method.md` §3 — is **14 blocks / 4,608 cells**,
i.e. 329 cells per block. The video is a *finer blocking at a coarser density* than the tutorial
of the same geometry family. **[I]**

**The video states, on screen, why a C and not an O: "The orthogonality of the mesh in this
region has improved when compared to the O-grid."** Verbatim from the burned-in caption in frame
`maxres2.jpg`. **[V]** That is the vendor's claim, and this repo already holds the vendor's own
long-form version of it: the *Art and Science of Meshing Airfoil* blog says an O-type grid
"creates **highly skewed cells for zero thickness trailing edge airfoils**… For a single
cell-to-cell step, it **nearly creates a 360-degree turn in one step**… For this reason, **many
prefer to go with the C-type grid and live with the excessive cells in the wake region**"
(quoted **[V]** in `gridpro-blocking-method.md` §2a). **The video's one-line reason and the
blog's paragraph agree, and I read them in two independent places.** **[I]**

**The procedure itself is not new to this repo and I did not re-derive it from the video.**
GridPro's own tutorial text — `Tutorials/Medium/Tutorial_1_Airfoil/Tutorial_1_Airfoil.pdf`,
retrieved from the Internet Archive and measured in `gridpro-blocking-method.md` §3b — gives it
in GridPro's words: create a coarse wireframe *around* the aerofoil with Corner and Link; "**Expand
the existing wireframe … which represents a C-Shaped wireframe to get a C-grid**"; group the outer
corners; **Wrap (O Grid)** at "Wrap length %: 200.000"; "**Drag the corners and position them
approximately**"; assign one corner group to the aerofoil and one to the outer circle. **[V]** in
that note. Anyone wanting the steps should read §3 there, not this section.

### 2a. One number on screen does NOT belong to this case, and it would be easy to quote wrongly

Frame `maxres2.jpg` also shows a **Grid Quality** dialog over the aerofoil, reading
`Blocks 8`, `Cells 1344`, `Surface Folds 0`, `Volume Folds 0`, and under *Skew*
`Minimum 0.003 / Average 0.052 / Maximum 0.410`, with *Range* `0.0`–`1.0` unchecked and the
buttons `Export Grid` / `Cancel` / `Evaluate`. **[V]** — all legible at 1280 x 720.

**Those figures are not the C-grid's.** The dialog's own *File Name* field reads
`…m/Tutorial_3_2D_Y_Exhaust/blk.tmp` — a **Y-exhaust** directory, not an aerofoil one — and
`8 / 1344` contradicts the same screen's status bar of `57 / 3648`. **[V]** on both readings.
**[I]** the dialog is showing a previous evaluation of a different grid, so **the skew figures
0.003 / 0.052 / 0.410 cannot be attributed to this C-grid**, and this note does not attribute
them. I record them only so that nobody later quotes them off the same frame as if they were.

## 3. The icing video: the method, and the one word it puts on screen

**The operation has a name and the video says it: "The forward nest creates a local nesting
(loopback structure)".** Verbatim from the burned-in caption in frame
`https://i.ytimg.com/vi/2FYLCyg8VSA/maxres2.jpg`. **[V]** The same frame shows what it means: a
zoomed view of the *wireframe*, with the iced surface drawn in cyan and the topology in orange —
a dense band of corners and links wrapping the nose and **turning back on itself**, embedded
inside a far coarser outer wireframe of maybe five or six radial lines. **[V]**, read off the
image.

**"Forward nest" is the UI name of the `nest` the FAQ documents, and "reverse" is its opposite.**
This repo already holds GridPro's own FAQ wording **[V]** (`cell-size-range-within-a-block.md`
§L4): `nest` "helps in refining the grid by creating more blocks near the geometry **without
affecting the far field**", while `reverse_nest` "will reduce the number of blocks and thereby
reducing the cell count". A pair named *forward* and *reverse* is the same pair. **[I]**

**The "loopback structure" is what Eiseman calls a clamp.** GridPro's founder, in the NASA paper
this repo already cites **[V]** (`cell-size-range-within-a-block.md`, quoting
`ntrs.nasa.gov/citations/19950022314`): "We often call such loop structures '**clamps**' or as in
the case of the trailing edge structure '**a collar**.'" A nested loop of blocks closed around
the leading edge is that structure. **[I]**

### 3a. GridPro's own page for this exact case, and it corroborates the video to the cell

**GridPro publishes an application article for this case, and its two headline numbers are
exactly the two I read off the video's final frame.** The article
`https://www.gridpro.com/application/article/airfoil-with-icing/` is **404 live**; I read the
Internet Archive capture `20240813124309`. It states, in its own *Grid Details* table:

> Volume cells **96,768** · Blocks **421** · Time to generate the grid (by expert) **~ 1.5 hours**

**[V]** And the video's own final frame
(`https://i.ytimg.com/vi/2FYLCyg8VSA/maxresdefault.jpg`) reads `Num Blocks : 421`,
`Num Cells : 96768`. **[V]** **Two independent sources, the same two numbers.** **[I]**

**96,768 / 421 is 229.9, not an integer, so unlike the C-grid case these blocks do *not* all
carry the same density.** **[I]** from the two **[V]** counts. That is the nest being used for
what the FAQ says it is for: density that changes from block to block without the far field
following along.

**The article's eight figure captions are GridPro's own description of the method, and three of
them name the nesting.** Verbatim, in page order: *Entire computational domain* · *Fine mesh
around airfoil* · *Surface mesh near leading edge* · *Surface mesh near leading edge with color by
blocks* · **Nested grid around the leading edge** · **Smooth grids around the complex crevices of
the airfoil-icing profile** · *Blocks used to generate the grid* · **Nested blocks at the leading
edge**. **[V]** — each caption sits immediately after its own `<img>` in the HTML, so the pairing
is the page's, not mine.

### 3b. What those figures show, read off the images

I downloaded all eight (`res.cloudinary.com/hrqxgjfxx/…`, still live) and read four.

**The far field is a circle, and the wake leaves it as a single seam.** *Entire computational
domain* shows a circular outer boundary with the body a short white sliver at the centre and one
straight line running from it to the right-hand edge. **[V]**, read off the image. **[I]** that
line is the wake cut, which is what makes it a C rather than an O. This also settles, for this
one case, a question `gridpro-blocking-method.md` §18d left open after retracting its own
rectangle reading: **the only far-field shape any GridPro source here shows for a single 2-D
section is a circle**, in both the tutorial (radius 3, **[V]** in §3a there) and this article.

**The block boundaries coarsen outward in steps, and the steps are concentrated at the nose.**
*Blocks used to generate the grid* and *Nested blocks at the leading edge* draw block edges only,
colour-cycled. Around the mid-chord there are a handful of thin block rings hugging the surface
inside a coarse outer field; at the leading edge that becomes a tight cluster of small blocks, and
**the number of block layers crossed on a radial line is larger at the nose than along the
chord**. **[V]**, read off the images. **[I]** that is exactly the nest: layers inserted locally
and removed again before the far field, so the nose's resolution is not paid for everywhere.

**The jaggedness of the ice does not reach the field.** *Smooth grids around the complex crevices
of the airfoil-icing profile* shows the scalloped ice surface with the grid lines leaving it
nearly normal, and the surface's wiggles damped out within a visibly small number of cells; the
outer part of the frame is smooth. *Surface mesh near leading edge with color by blocks* shows the
same thing one level up, with the near-surface blocks following each lobe and the next ring out
already smooth. **[V]**, read off the images. **[I]** This is the thing worth taking from the
pair: the blocking absorbs the geometry's roughness in the first ring or two, and nothing
downstream of that ring knows the ice is there.

**I deliberately give no block or cell counts read off these pictures.**
`gridpro-blocking-method.md` §23a records three attempts to count blocks or density off a GridPro
image, all of which failed their own controls, and §18e and §24c record two counts it had to
retract. I am not adding a fourth.

### 3c. The geometry itself is not obtainable

The video's description offers it — "The Airfoil with Icing geometry is available here for
download. https://bit.ly/3tWNKWt" **[V]**, verbatim from the watch page's `shortDescription`
field — and **the link is dead**. It 301s to `sp.gridpro.com/Youtube_cases/airfoil_icing`, then to
`gridpro.com/Youtube_cases/airfoil_icing`, which answers **HTTP 404**; the Wayback CDX index has
no capture of either path. **[V]** So the ice shape in these figures is unidentified: GridPro
names no source for it, and I did not try to match it against a published ice accretion.

---

## 4. What this repo's declaration model could and could not express

Offered because the maintainer asked for it, and kept to what is checkable on both sides.

**It could declare the arrangement. It could not produce it the way GridPro does.** A
`MESH_MODE 1` topology document is just corners, edges and blocks as `[south, east, north, west]`,
so 421 of them is a long file and nothing more; and `curve` / `follows` edges mean a block
boundary can *be* a declared curve rather than a chord (`CLAUDE.md`, and
`.claude/rules/mesher-multiblock.md`). **[V]** What differs is everything about how the positions
are arrived at:

- **GridPro's corner is an initial guess; ours is a fact.** The whole GridPro method is that the
  wireframe may sit in the wrong place and the solver pulls it onto the geometry — the tutorial's
  own instruction is "**Drag the corners and position them approximately**" **[V]**
  (`gridpro-blocking-method.md` §3b), and this repo's rule is the opposite: a declared corner is a
  DECLARATION, and `.claude/rules/mesher-smoothing.md` freezes "every DECLARED CORNER" and every
  node of a shared edge with a declared shape. **[V]** Placing 421 blocks' worth of corners around
  an iced nose would therefore be 421 blocks' worth of *exact* authoring here, where GridPro
  authors approximately and solves. **[I]**
- **`nest`'s defining property has no counterpart.** The FAQ's claim is more blocks near the
  geometry "**without affecting the far field**" **[V]**; here
  `.claude/rules/mesher-multiblock.md` states "**THE COUNT FIX IS THE EQUIVALENCE CLASS's, NEVER
  THE EDGE's**" **[V]**, so a count is shared along the whole chain of welded edges and refining
  the nose refines the row. `cell-size-range-within-a-block.md` §3 and §L4 reached this same
  conclusion from the FAQ before these videos existed; the videos are the same fact seen from the
  outside. **[I]**
- **The two steps in §1 split cleanly along that line.** The C-grid video's content — a C
  topology, a wake cut shared by both wake blocks, a frozen declared trailing-edge corner — is
  already shipped (`config/multiblock_cgrid.dat`, per `CLAUDE.md`). The icing video's content —
  insert layers locally and take them away again — is the half this repo does not have. **[I]**

**I am not claiming the repo should acquire it.** Nothing here was measured against a HybMesh2D
run; this section is a mapping between two documented models, no more.

---

## 5. What I could not verify

1. **Neither transcript.** ASR-only caption tracks, and `timedtext` returned 0 bytes for four
   formats. The only words of either video I have are the burned-in captions in the two content
   frames, quoted verbatim above, plus the title cards "Welcome back" (`4Jeu-EUXXmo`) and "Hey
   everyone!!" (`2FYLCyg8VSA`). Everything a voiceover might add is missing, and nothing above
   fills that gap by guessing.
2. **Only two content frames per video exist to read.** YouTube publishes `maxres1/2/3.jpg`
   alongside `maxresdefault.jpg`; for both videos frames 1 and 3 landed on the GridPro logo card
   and frame 2 on the application. I did **not** verify at what timestamps those frames are
   sampled, so I make no claim about *when* in the video a caption appears, only that it does.
   Storyboard tiles exist but top out at 160 x 90 per tile — too small for text — so there is no
   further frame coverage I could reach.
3. **No GridPro write-up of the C-grid video.** `gridpro.com/video/` redirects to the YouTube
   channel; there is no `application/article/` entry for a single-element aerofoil C-grid in the
   Wayback index (the only two aerofoil articles are `airfoil-with-icing` and
   `mda-3-element-configuration`). So the C-grid video's 57 / 3648 has **no second source**,
   unlike the icing case's 421 / 96,768.
4. **GridPro's own C-grid tutorial package is gone.** CFD-Online's GridPro forum thread 142231,
   *How to create C-grid in GridPro* (Sep 2014), has a GridPro staff answer linking
   `https://db.tt/f4xSP9fw`, which still 302s to
   `…/Tutorials/Draft/2D TUTORIALS/Airfoil Tutorial/Sharp_Edge/Airfoil_Sharp_edge.zip` and then
   **404s**; a 2018 reply adds a second Dropbox link that the forum truncates to `…_edge.pdf`.
   **[V]** on both. The redirect target is good evidence that a *Sharp_Edge* airfoil tutorial
   exists under that name, and I could not obtain it. (The repo's §3 material comes from a
   different package, `ws_Tutorials.zip`.)
5. **"Automatic nested refinement" as an Eiseman paper.** A search summary attributed that phrase
   and a description of recursively nested topology to Eiseman's work, and **I never found the
   document**, so it is not cited above. The nesting claims in §3 rest on the FAQ and on the 1995
   NASA paper instead, both of which this repo has read directly.
6. **The ice geometry.** Dead download, no name on GridPro's page, not matched against anything.
7. **`cfd-online.com` answers HTTP 403** to WebFetch, and `web.archive.org` is not fetchable by
   WebFetch in this environment; the forum thread was read through `curl` against the Wayback
   capture `20251015075538` instead.

---

## 6. The method, applied — a mesh, and what it cost

Added 2026-11-10, after the note above. §4 said what this repo's model could and could not
express and marked the hard part **[I]**. This section builds it instead, so the parts that were
inferred are now measured. Everything here is **[V]** unless marked.

**Result: `gridpro_ch_iced.{json,dat}`, 128 blocks, 24720 cells, 0 inverted.** Figure
`iced_leading_edge.png`. **Quality is poor and the case header says so**: non-orthogonality max
**76.3°**, mean **10.3°**, against 50.1° and 1.8° for the same topology on the clean section. It
is a mesh, not a good mesh.

### 6a. The geometry is mine

§5 says GridPro's iced section is not obtainable, so `make_iced_body.py` builds one: a glaze-ice
**double horn**, two convex tips at (0.009, ±0.076) with a concave valley between them at the
stagnation point, displacing a NACA 0012 along its own normals. The horn angles and heights are
round numbers chosen to make a leading edge that is *complicated*; **nothing about the shape is
claimed to match GridPro's**, and no figure of theirs was measured to produce it. An earlier
version parametrised the ice by angle about the leading edge and grew ice on the TRAILING edge
too — the trailing edge sits at the same angle — caught because the written file reached
x = 1.0121.

### 6b. The far-field map refuses, and the alternative folds the CLEAN section

The generator places each station's far-field corner where the body's own **outward normal**
lands, and requires that map to stay ordered. Across the ice valley two neighbouring normals
converge and their landings swap, so it refuses — **at every `--turn-blend` from 0.0 to 1.0**, so
it is the map and not the station law.

The one alternative already described in the generator's own comments is arc length, monotone by
construction. It folds: **1786 inverted of 14320 on the CLEAN section**, mean 42.4°. That control
is what shows the folding is the map and not the ice — the iced case under the same map is 2334.

### 6c. The repair that worked, and the control that makes it trustworthy

`--far-monotone` keeps the cast and repairs only the stations that reverse, by isotonic
regression — the nearest non-decreasing sequence, so anything the cast already ordered is left
exactly where the cast put it. **On the clean section it is byte-identical and the mesh is
unchanged to six decimals**, which is the control: the option costs nothing when it is not
needed. On the iced section it moves **58 of 81** stations, worst move 12.4% of the far-field
path — which is a rewrite, not a repair, and the section says so rather than calling it minimal.

### 6d. A station LAW cannot put a corner on a feature

With the map repaired the mesh had **8 inverted cells**, and the worst sat at **(0.016, 0.074)** —
the upper horn's tip. Every station law here spaces stations by a rule, so a block corner lands on
a salient feature only by luck, while **the whole point of the videos' method is that the
complicated part gets corners BECAUSE it is complicated**. `--pin-tips 1` snaps one station onto
each surface's sharpest convex feature: **8 → 1**.

I had excluded concave features on the assumption that a corner declared inside one folds the
block there. **Tested, and it makes no difference** — `--pin-concave` leaves the count at 1 and
`nonortho_max` identical to six decimals, so the assumption was neither right nor load-bearing.
The flag stays, with that recorded at its own definition.

### 6e. The last fold was the first layer, not the blocking

The remaining cell had positive area but a reflex corner, at **(0.0487, 0.0988)** — the concave
shoulder behind the horn, inside a first layer 0.05 chords thick. **A layer thicker than the
feature's concave radius must fold there**, and the sweep is monotone in exactly that way:
`--wall-band` 0.05 → 1 inverted, 0.03 → 1, **0.02 → 0**, 0.015 → 187, 0.010 → 415.

### 6f. MORE BLOCKS AT THE FEATURE MAKES IT WORSE — which is the method's own premise failing

`--split` 32 → 48 → 64 gives **8 → 25 → 99** inverted cells. Adding blocks at the complicated
part, which is the one thing both videos teach, moves this generator the wrong way.

**The mechanism is not the one §4 inferred.** §4's **[I]** was about node counts: a `count` is
fixed for a whole equivalence class, so refining the nose refines the row. That is still
plausible and is still not measured here. What this section measured is a different obstacle in
the same place: **every added block adds a far-field station that must be ordered**, so each one
is a new chance for the cast to reverse and a longer run for the repair to average. GridPro does
not have this failure mode because its far-field positions are **relaxed by the solver**, not cast
from the body — the tutorial's own instruction is "Drag the corners and position them
approximately" (§4). So the two models diverge exactly where the method needs them to agree.
**[I]** on the attribution; **[V]** on the 8/25/99 and on everything in 6b–6e.

### 6h. What the picture shows that the numbers did not **[V]**

Looking at `iced_leading_edge.png`'s global panel: **several block boundaries have collapsed onto
one another** — a cluster of near-coincident heavy lines below the nose, doubled vertical seams
downstream — and the far field carries slivers beside huge wedges. That is 6c's "rewrite, not a
repair" seen directly: isotonic regression pools a violating run to ONE value, so the stations in
it coincide and their blocks come out epsilon-wide.

**The obvious fix makes it much worse.** Spreading each pooled run evenly across the gap its
neighbours leave, instead of separating the run by a bare epsilon, takes the case from **0
inverted cells to 106**, mean 10.3° to 14.2°, and the worst adjacent area ratio from 4.5 to
**939**. The pooled value is the least-squares answer and moving a station off it costs more than
the sliver does. Reverted; the slivers stay, and are now a named cost rather than something the
figure quietly shows and the text does not mention. **[V]**

### 6g. What is shipped

`make_iced_body.py` (the section), four new generator options — `--body`, `--far-monotone`,
`--pin-tips`/`--pin-concave`, and `--far-by-arc`, which is kept **because it is the measurement in
6b** — and `gridpro_ch_iced.{json,dat}`. **Every one is behind a flag and the clean default was
re-verified byte-identical after each**, so none of the eight cases in `gridpro-blocking-method.md`
moved.


---

## 7. The same method on a CLEAN section, at the video's own scale

The iced case above was asked for and then set aside; this is the other half, and it is the half
the C-grid video actually shows. Added 2026-11-10. Everything here is **[V]**.

**Target: 57 blocks / 3648 cells**, the C-grid video's own status bar (§2). **Built:
`gridpro_ch_video.{json,dat}` — 56 blocks, 3692 quads, 0 inverted, non-orthogonality max
52.3°, mean 3.10°.** Figures `video_scale_cgrid.png` and `vs_video_frame.png`. The cell count
is 1.2% from theirs, and §7d is why the blocking is 2 layers × 8 and not 1 × 22.

### 7a. 56 and not 57, and it is structural

Measured across **18 combinations** of layers, split and wake, exact in every one:

> **blocks = 2 × LAYERS × (SPLIT + WAKE)**

So **every block count this generator can produce is even**, and 57 is unreachable by
construction rather than by tuning. The reason is visible in the formula: the topology is
mirror-symmetric about the wake line, so its blocks come in top/bottom pairs. **GridPro's 57 is
odd, so theirs is not** — somewhere in it is a block with no mirror twin, and nothing in the
published frames says where. **[I]** on what that block is; **[V]** on the parity argument and on
the 18 measurements.

### 7b. Two things that nearly went in wrong

**The cell count was out by exactly 2×.** The case inherited `MB_SPLIT_QUADS 1` from the file it
was copied from, so the mesher reported 7276 against GridPro's 3648. GridPro's published grids are
quad and 3648 is a quad count, so comparing would have been 7276 triangles against 3648 quads.
This is the one case in the directory that sets `MB_SPLIT_QUADS 0`, and the header says why.
Caught because the number was exactly twice the swept one.

**There is no vendor quality figure for this case.** §2a already established that the Grid Quality
dialog legible on the same frame belongs to a different tutorial — its own File Name field points
at a Y-exhaust directory. So 58.5° / 3.81° are reported against nothing, and no GridPro skew is
quoted beside them.

### 7d. Is it like the video's mesh? Matching the COUNT did not match the BLOCKING **[V]**

`vs_video_frame.png` puts the video's own frame and the case at one window —
x ∈ [−0.38, +2.00], y ∈ [−0.47, +0.63] chords, derived by measuring the aerofoil in the frame at
**406 px chord and 48 px thick, t/c = 0.118**, which is NACA 0012 and confirms the frame is to
scale. Unlike `fig6` (§28e of the other note), this frame has both the extent and the resolution
to show block structure, so the comparison is real.

**The first version matched both numbers and looked nothing like it.** 56 blocks as
`--layers 1 --split 22` is twenty-two chordwise slivers per surface, each running the entire
radial span. GridPro's frame shows the opposite: the nose wrapped in **concentric bands**, with
only about five or six chordwise cuts crossing the whole view.

**Spending the same 56 blocks as `--layers 2 --split 8` is closer AND better on every measure:**

| | blocks | cells | inverted | non-ortho max | mean |
|---|--------|-------|----------|---------------|------|
| GridPro, stated | 57 | 3648 | — | — (no figure exists, §2a) | — |
| 1 layer × 22 per surface | 56 | 3638 | 0 | 58.490° | 3.814° |
| **2 layers × 8 per surface** | 56 | 3692 | 0 | **52.289°** | **3.095°** |

So the honest answer to "is it like the video's" is: **the counts matched from the start and the
blocking did not, and the picture is what caught it.** What still differs after the change is
visible in the figure — GridPro's cells are more uniform where mine stay clustered against the
wall, and its bands curve round the nose more than my wedges do. **[I]** on those two, which are
read off the frame and not measured.

### 7c. What is new in the generator

`--node-scale`, which multiplies the five node counts without touching the blocking, so a case can
be built at another grid's SIZE to compare counts. At 1.0 it is inert and the clean default was
re-verified byte-identical, as with every other option added in §6.


---

## 8. The other video's blocking, compared

`vs_icing_video_blocking.png` (`plot_vs_icing_video.py`). §7d compared the C-grid video's
blocking; this is the icing video's.

### 8a. That frame is a WIREFRAME, which is better for this than a mesh **[V]**

`2FYLCyg8VSA`'s content frame does not show a filled grid at all: it shows **GridPro's block
wireframe** — yellow block edges, orange square block corners, the iced surface in cyan — with the
burned-in caption **"The forward nest creates a local nesting (loopback structure)"**. So for a
blocking comparison it is the better of the two frames: the blocking is the only thing on it.

### 8b. The scale CANNOT be matched, unlike §7d's **[V]**

§7d could align its window because the aerofoil in that frame measures 406 px chord and 48 px
thick, **t/c = 0.118**, which identifies it as NACA 0012 and fixes the scale. **This frame has no
such anchor**: the body runs off the right edge of the inset panel (cyan spans x 308…829 against a
panel edge at 830), so the chord is not in view, and GridPro's own ice geometry is not obtainable
(§5), so there is no known dimension to scale by. **This comparison is therefore structural only,
and is not drawn at a matched scale.** Saying so is the difference between this and §28e of the
other note, where a sub-pixel claim nearly went in.

A second mismatch is mine, not theirs: **their ice is an asymmetric single horn** — one tip
jutting forward and up, a notch behind it, a smooth lower surface — where the section I built is a
**symmetric double horn**. That is a shape I chose (§6a), not one measured from them.

### 8c. What the two blockings actually differ in **[V]** on both readings

**GridPro's refinement TERMINATES.** Around the horn its wireframe packs several nested arcs of
small blocks, and a few block-widths out it is coarse again. The caption names the mechanism —
a *local* nesting, a *loopback*.

**Mine does not terminate.** Every block boundary at my nose is a line that runs outward and off
the frame; there is no nesting, and the nose blocks are thin wedges spanning the whole radial
extent. The picture is §6f's measurement seen directly: adding blocks at the feature took the
case 8 → 25 → 99 inverted cells, because **every block added at the nose adds a far-field station
that must be ordered**. GridPro has no such coupling, so it can stop refining wherever it likes.

So the two videos' comparisons land on the same sentence from opposite ends. §7d: on a clean
section I can match the block COUNT and still spend it differently. §8: on a complicated one I
cannot spend it the way they do at all, and the wireframe shows why in one picture — **their extra
blocks stay near the body; mine reach the far field by construction.** **[I]** on the attribution,
which rests on §6f's measurement rather than on this frame.


---

## 9. Is the NEAR-WALL method learnable? Half of it **[V]**

Asked directly, and the answer splits cleanly. Figure `near_wall_method.png` is the icing frame's
near-wall band at pixel zoom.

**What the frame shows.** Orange squares are block corners, yellow lines block edges, the pale
line the surface. Three things are going on: **block corners sit ON the surface**; **several
block ROWS are stacked normal to it**; and **the number of rows CHANGES along the surface** — five
or six where the horn is, about three a short way downstream, with the extra rows terminating
through the diagonal edges between.

**The first two this repo already does.** Corners on the body are `on_geometry` corners, and
stacked rows are `--layers`; §7d ships three of them.

> **§10 RETRACTS THE CONCLUSION BELOW.** The format does NOT forbid a terminating row; my test
> used the wrong construction. A row terminates at a **valence-3 corner** — three blocks sharing
> one point — and there every edge is still a side of exactly two blocks, so nothing in the
> format is violated. Built, 144 quads, 0 inverted (§10). The refusal quoted below is real and
> its reading is correct; what was wrong is concluding from it that the capability is absent.
> Kept rather than rewritten, like §60's specimen in the other note.

**The third it cannot do, and that is the one that makes the method worth having.** To terminate a
row, one block's side must be shared with TWO blocks on the other side. In this topology a block
is `[south, east, north, west]` — **one edge per side** — and an `interface` must be a side of
exactly two blocks. Tested on a minimal three-block case, with a control:

| topology | result |
|----------|--------|
| two rows on the left, two on the right — the row runs all the way across | **meshes**: 256 cells, 0 inverted, 0.000° non-orthogonality |
| two rows on the left, ONE block on the right — the row terminates | **REFUSED**: `edge 'lo_e' is declared kind 'interface' but is a side of 1 block(s) — the east of block 'b_lo'` |

Same corners, same intent, one difference, and the control is what makes the refusal mean
termination rather than a mistake in my test file. **[V]**

**So:** the near-wall *drawing* is learnable and is already in §7d's case. The *nesting* is not a
technique to copy but a capability the format lacks, and the refusal above is where it is lost.
This is §6f and §8c reached a third time and finally at the level of the data model rather than
the generator: **§6f measured that adding blocks at the nose makes the mesh worse, §8c showed
their wireframe keeping the refinement local, and §9 names the line in the format that forbids
it.** **[I]** on tying the three together; **[V]** on each separately.

A caveat on scope: this says nothing about whether the format COULD be extended — only that as it
stands, one edge per side is what blocks it. That is a design question for the repo, not a reading
of GridPro.


---

## 10. Learning to draw it — the terminating row, built

"學著畫畫看". Figure `terminating_row.png`, topology `terminating_row.json`, generator
`make_terminating_row.py`. **144 quads, 0 inverted.** And it retracts §9.

### 10a. §9's conclusion was wrong, and the error was in my construction **[V]**

§9 concluded the format forbids a block row from terminating. It does not. My test had the big
block's west side spanning BOTH left blocks' east sides — one edge covering two — which is
correctly refused and is simply not how it is done.

Zooming the icing frame further shows the actual construction: **valence-3 nodes**, three edges
meeting at a point. At such a node three blocks share one corner, and each of the three edges
leaving it is a side of exactly two of them — **the rule §9 quoted is never broken**.

Checked in two steps, each 0 inverted: **[V]**

| test | result |
|------|--------|
| a hexagon split into three quads by spokes to alternate vertices — the minimal valence-3 node | **384 cells, 0 inverted** |
| a wall strip with TWO rows on the left and ONE block on the right, meeting at a valence-3 corner | **144 quads, 0 inverted**, max 51.7°, mean 16.4° |

The second is the thing itself: an extra near-wall row that stops in the middle of the wall.

### 10b. What it cost to make it hold **[V]**

A single valence-3 termination **has to open steeply**. Sweeping the height the extra row's outer
edge reaches at the transition, against a layer thickness of 0.6:

| outer edge reaches | inverted |
|--------------------|----------|
| 0.70 | 3 |
| 0.80 | 3 |
| 0.90 | 2 |
| 1.00 | 2 |
| **1.10** | **0** |

So the transition must open to nearly **twice the layer thickness** before it stops folding; a
flat one does not work. GridPro's frame spreads its transition over several diagonal edges rather
than one, which is presumably why — **[I]**, read off the frame.

### 10c. What this does and does not change

**It changes §9's verdict**: the near-wall method is learnable in full, not half. The mechanism
exists in this format and is now built and shipped as a minimal case.

**It does not yet change §6f.** That measured the ICED AEROFOIL case getting worse as blocks were
added (8 → 25 → 99 inverted), and the cause named there was the far-field map, not the block
grammar. Nothing in this section was run on an aerofoil; the strip above is flat and has no far
field. Whether a valence-3 nest actually fixes §6f is **untested**, and §10 does not claim it. The
honest statement is that the construction this repo was said to lack turns out to exist, and the
obvious next step — putting one into `make_ch.py`'s near-wall layers — has not been taken.


---

## 11. On an aerofoil — the nest, built

§10c named the untaken step: put a valence-3 nest into an actual aerofoil mesh. Done.
`nested_wall.json`, generator `make_nested_wall.py`, figure `nested_wall.png`. **26 blocks, 648
quads, 0 inverted.** A 24-station O-ring round the NACA 0012 with a far-field circle at r = 3,
and an extra near-wall row that exists over three stations and terminates at a valence-3 corner at
each end.

### 11a. The step that makes it conformal **[V]**

**At each termination station the FAR-FIELD corner must be OMITTED.** Keep it and the three edges
around that point enclose a triangular region no quad can fill. Four arrangements were worked
through and the other three all left that triangle somewhere; this is the one that closes.

Three refusals were hit and each named its own cause, which is how the arrangement was found:
a `count: null` written instead of omitted; **every station pair being its own circumferential
class** — a block's opposite sides are (body, far) and (radial, radial), so the radials chain
round the ring as one class and the circumferential ones do not chain at all, needing one seed
each; and the ring winding clockwise, because the shipped polyline runs over the upper surface
first.

### 11b. The measured limit: the nest cannot be THIN **[V]**

Sweeping where the nested ring sits, as a fraction of the body-to-far-field gap:

| band | inverted |
|------|----------|
| 0.02 | 9 |
| 0.04 | 7 |
| 0.06 | 2 |
| 0.10 | 2 |
| **0.15** | **0** |

This is §10b's constraint again on a ring instead of a strip: **a single valence-3 termination
cannot support a thin nest.** So the construction exists, but at one termination per end it does
not yet reach boundary-layer thickness — and GridPro's frame spreads each transition over several
diagonal edges rather than one, which is the obvious thing to try next and was not tried here.
**[I]** on that being the reason; **[V]** on the sweep.

### 11c. What this is and is not

It is a **topology demonstrator**: 24 stations, straight radials from the body to a circle, no
clustering and no curvature, so the quality is poor — max 89.6°, mean 30.5°. **It shows that the
construction holds on an aerofoil, not that it produces a usable mesh.** Nothing here has been put
into `make_ch.py`, and §6f — the iced case getting worse as blocks were added — is still
unaddressed, because the cause named there was the far-field map and this section did not touch
it.


---

## 12. Into a GOOD mesh — gate 1 passes, gate 2 does not

§11 built the nest on a purpose-made ring whose mesh was poor by construction. This puts it into
§27's C/H, which is the best mesh in this work, and the result is a clear negative.

`gridpro_ch_nested.{json,dat}`, spliced by `nest_into.py`. **make_ch.py is not touched** — the
nest is spliced into its OUTPUT — so the eight cases beside it cannot regress and the wall
clustering, curvature and far field are all §27's.

### 12a. The nest goes in the OUTER layer, and that is structural **[V]**

§11a's rule is that each termination station's corner on the ring ABOVE must be omitted. In the
outermost layer that ring is the **far field**, where the two circumferential edges either side
merge into one and nothing propagates further — there is nothing outside it. Put the nest against
the wall instead and the omission must be merged through every layer outside it.

### 12b. Gate 1 passes, and it looks like a good mesh **[V]**

| | §27, no nest | §12, nested |
|---|--------------|-------------|
| blocks | 176 | 162 (+6 spliced, −20 merged) |
| cells | 28640 | 28704 |
| inverted | 0 | **0** |
| non-orthogonality mean | 1.840° | 3.250° |
| wall first cell | 0.0276 | **0.0276, unchanged** |
| non-orthogonality max | 50.062° | **89.918°** |

### 12c. GATE 2 FAILS **[V]**

`run_pipeline.sh` on the same chain every other case here uses: **32 NaN in the error norms, and
the solve prints two iteration headers before dying.** Not a marginal result and not a
substring false positive — the matches are `eL2 error norm for int. region = NAN NAN NAN NAN`,
word-bounded.

So the mesh has **zero inverted cells, a respectable mean, an untouched wall spacing — and the
solver cannot run on it.** Gate 1 is not gate 2, and this is the sharpest example of that in the
whole note.

### 12d. The bad corner is the transition, and two fixes failed **[V]**

The 89.9° sits in the **left transition block at (0.036, −0.971)** and it does not move:

| where the nested ring sits | non-ortho max | inverted |
|----------------------------|---------------|----------|
| band 0.15 | 89.984 | 0 |
| band 0.30 | 89.918 | 0 |
| band 0.45 | 89.869 | 0 |
| band 0.60 | 89.726 | 4 |
| band 0.80 | 89.570 | 7 |

So it is the transition itself, not the depth. **Grading the two end stations back toward the far
field** — the obvious fix, and what GridPro's frame appears to do by spreading each transition
over several diagonals — makes it **worse**: `--taper` 0.3 / 0.5 / 0.7 gives **7 / 13 / 26**
inverted cells.

### 12e. Where that leaves the question **[I]**

Asked to produce a good mesh with this method, I have not. Every route tried costs something the
measurements catch: adding blocks at an iced nose made it worse (§6f), the nest cannot be made
thin (§11b), and spliced into the best mesh here it passes gate 1 and fails gate 2 (§12c).

That is three independent negative results, which is itself the strongest reason to think **the
benefit is real and I am not measuring the thing it buys** — the maintainer's own question. What
GridPro states the method is for is being researched separately; this section deliberately does
not guess at it.


---

## 13. The benefit was never on my instrument — and here it is

`docs/research/why-local-nesting.md` answers the maintainer's question from primary sources, and
the answer makes §§6–12 legible. Summarised here with the one measurement it let me finally make.

### 13a. What the method is claimed to buy, in the vendor's own words **[V]**

GridPro's *WS GUI Manual* v1.0 §4.8.2 — in the same Internet Archive capture this work has been
citing all along, in a section nobody here had read:

> "Nest is very useful when you are handling geometries with **large-scale differences**…
> Conventional meshing techniques on geometries with scale differences create grids with **large
> aspect ratio especially near the smaller features**… **The refinement near the geometry is
> necessary, but limiting because refinement propagates to the far field.** This limitation can be
> overcome by using nesting. It helps to increase number of grid points near the geometry of
> concentration locally, with one to one connectivity, **without increasing the points
> elsewhere**."

**The claim is denominated in CELLS and ASPECT RATIO.** §6f held `--split` fixed and counted
inverted cells. §11 counted inverted cells, mean 30.5° and max 89.6°. §12 counted inverted cells
and non-orthogonality. **None of those is cells-at-a-required-resolution and none is aspect
ratio. The claim was never on the instrument**, which is what §12e guessed and could not show.

And no source claims nesting improves folds or orthogonality: GridPro attributes unfolding to its
**relaxer**, not to the nest. So the quantity §6f reported was never the nest's job.

### 13b. Measured, on the right instrument, at last **[V]**

Cell-shape (midline) ratio in a disc of radius 0.8 about the nest, §27's C/H against §12's
spliced one — the same mesh but for the nest:

| | cells in the disc | median | p95 | max |
|---|-------------------|--------|-----|-----|
| no nest | 859 | **24.955** | 60.337 | 273.601 |
| nested | 959 | **17.258** | 53.605 | 274.914 |

**Median aspect ratio falls 31% where the nest is, for 64 more cells in the whole mesh** — 28640
→ 28704, **+0.2%**. Globally the p95 is unchanged to six decimals (81.554689 both), because the
worst-shaped cells are in the wake and the nest does not reach them.

That is the claimed benefit, reproduced: **better aspect ratio locally, bought without paying for
it elsewhere.** It is the first positive result in this chain, and it only appeared once the
measurement matched the claim.

### 13c. It is still not a usable mesh, and the literature says why **[V]**

§12c stands: 32 NaN, gate 2 fails. The research names the mechanism independently. Tchon,
Dompierre & Camarero (IMR11, 2002), cited by GridPro's own IMR12 paper:

> "the corner configurations located at the extremities of the layers degrade mesh quality. **This
> phenomenon is even more acute when several layers terminate at the same location.**"

— which is §12d's 89.9° corner, predicted. Their named remedies are quadtree-style balancing and,
twice, **thicker layers**. And the nest's own ratio law is **1:3ⁿ per level**, GridPro's worked
example using **five** levels: so **a nest is a BAND, and §11/§12 built a single level — the
thinnest and weakest member of the family.** §11b measured that from the other side when it could
not make the nest thin.

### 13d. Where this leaves it

**The method does what it says.** My three negative results were measuring something it never
claimed, and the one time I measured what it does claim, it delivered.

**I still have not produced a usable nested mesh**, and the next step is now named rather than
guessed: more levels and thicker bands, with the transition corner — not the nest — as the thing
to fix. **SUPERSEDED BY §15 (same day): neither more levels nor thicker
bands can move the quantity that defines the method, because this declaration model cannot
express a count-reducing termination at all — and §15d has the mesher's refusal.** What this work has is the construction (§10), it on an aerofoil (§11), it in a good mesh
(§12), the benefit measured (§13b), and a gate-2 failure localised to one corner the literature
predicts (§12d, §13c).

One honest counterweight, from the research rather than from me: **NASA Glenn's published practice
for iced aerofoils is not nesting** — it is a thick wrap-around plus overset coupling, which buys
the no-propagation property from the solver instead. **[V]** So the method is one answer to this
problem, not the answer.


---

## 14. DECIDED: this repo does NOT acquire local nesting — and what it took instead

**2026-11-10.** §13d named a next step ("more levels and thicker bands, with the transition
corner — not the nest — as the thing to fix"). **That step is not being taken, and this section
exists so the sentence above is not read as a live to-do by the next session.** The question was
put to the maintainer as a design review and settled branch by branch; what follows is the
outcome, not a summary of the argument.

### 14a. The decision

**No local nesting in the repo.** The question that started this work —
"如果沒有比較好的話為什麼影片中要用這個方法?" — is a question about UNDERSTANDING, and §13 answered it: the
method delivers what it claims (a 31% local median aspect-ratio reduction for +0.2% cells,
§13b), and the three earlier negative results were measuring something it never claimed. An
answered question is not a reason to build the thing.

The concrete grounds, each measured in this note rather than assumed:

1. **No target geometry.** Nothing on this repo's roadmap is a large-scale-difference case. The
   motivating one — an iced aerofoil — has a published standard practice that is NOT nesting
   (§13d, and `why-local-nesting.md` §1).
2. **Gate 2 fails** (§12c: 32 NaN). The one nested mesh spliced into a good mesh is not solvable.
3. **What would have to be built is not an extension of what exists.** §13c: a nest is a BAND at
   1:3ⁿ per level and GridPro's own worked example uses FIVE; §§11–12 built ONE, which is the
   thinnest and weakest member of the family. Five levels plus thicker bands is a rewrite of
   `nest_into.py`, not a parameter on it.

### 14b. The restart condition, stated so this can be reopened on evidence

Two conditions, both required: **a named target geometry**, and **gate 2 as a hard precondition**
— no nesting code leaves `docs/research/` until some nested mesh runs through the solver. The
next step itself is already named in §13d and does not need rediscovering.

### 14c. What WAS taken, and it is shipped

The research produced one thing worth keeping, and it is not the nest. `why-local-nesting.md`
§3.4 names a **published, checkable criterion about block boundaries** — Chi et al.'s "grid
spacing from contiguous blocks will be comparable in size at all block boundaries" — and points
it at an instrument this repo already had. **Shipped as issue #183**: the mesher's existing
`adjacent_area_ratio` figure is now reported again over the pairs that cross a block boundary and
over the pairs that do not (`across seams` / `within blocks`), on every `MESH_MODE 1` run.

It was cheap because the seam pairs were already being measured and merely averaged away — and
it paid immediately: the elliptic smoother's cost to that ratio lands **on the seam** on both
two-ring cases and **inside blocks** on the C-grid and O-grid, which the mixed figure could not
say. Rules: `.claude/rules/mesher-quality.md`. Why: `docs/design_notes/mesher.md`, "THE SIZE
JUMP, SPLIT AT THE BLOCK SEAM".

**Building the ruler is the part that survives the decision not to build the thing.**

### 14d. One candidate kept, deliberately decoupled from ice

`why-local-nesting.md` §3.4's other cheap takeaway is the **transition layer** — absorb a
surface's jaggedness in one band so the transfinite fill never sees it, which Chi et al. state
against TFI generators BY NAME, and `MESH_MODE 1` is one.

It was nearly discarded with the nesting decision because its motivating geometry is an iced
aerofoil. **That binding is wrong, and the repo's own output says so**: a shipped O-grid run
warns that edge `w0`'s 25 nodes sample a 40-facet polyline at 1.667 facets per interval, so "the
polyline's own turning does not fall equally on the nodes", and that **"about half of that
reaches the non-orthogonality of the cells along this edge"** — 4.050° against the 3.750° an even
sampling would give. That is a discrete surface's jaggedness propagating into the mesh, with a
number on it, in a case this repo ships today. The transition layer is the named remedy for that
class.

**Not built.** Recorded as a candidate hanging off an existing warning, to compete on its own
evidence rather than on ice.

### 14e. A reading discipline, written down because it is what this whole chain cost

§13b only worked once the measurement matched the claim. The generalisation, for the next local
method anyone evaluates here:

**A local improvement must show the local figure improving AND the global figure not worsening,
and both must be in the unit the claim is denominated in.** The mesher already prints both —
per-block rows under `Cell shape`, and the whole-mesh headline beside them — so this needs no
tool and no flag. What it needs is for the pair to be read together. §§6f, 11 and 12 each reported
a single number in a unit nobody had claimed, and produced three negative results about a method
that works.

### 14f. What this section does NOT retract

§§1–13 stand as written. The three negative results are real measurements of real defects —
§6f's rising inverted count is a cast far-field map, §11b's fold-when-thin is a predicted
property of a one-level conformal transition, §12c's 32 NaN is a mesh the solver cannot run. What
§13 established, and this section acts on, is that none of them tests the method's own claim.


---

## 15. Reproducing the video's nest — the model REFUSES it, in its own words

**2026-11-10, the same day as §14.** §13d named the next step as "more levels and thicker
bands". **That is superseded here, and not by an opinion**: in this declaration model neither
one can produce the property that defines the method, and the mesher says so when asked.

### 15a. What a nest IS, as a measurable property **[V]**

§8c read it off GridPro's wireframe by eye — "their extra blocks stay near the body; mine reach
the far field by construction". That sentence is a quantity:

> **N(r)** = how many block-partition lines cross a circle of radius *r*.
> A terminating (nested) blocking **FALLS**. One whose counts propagate is **FLAT**.

The shape is scale-free, which is what makes it the right instrument against a video frame with
no measurable chord (§8b). Tool: `measure_block_partition.py`. It reads the `block` cell field
(#106) out of a `MB_SPLIT_QUADS 0` mesh, so it needs no second parse of the declaration.

### 15b. Measured, on this repo's own blockings **[V]**

| N(r) | r = 0.5 | 1 | 2 | 5 |
|------|---------|---|---|---|
| shipped C-grid, 4 blocks | 4 | 4 | 4 | 4 |
| the §27 C/H, 160 blocks | 70 | 68 | 68 | 5 |
| the same + §12's nest, 162 blocks | 70 | 68 | 68 | 5 |

**Both are flat.** The C/H holds 68 lines from the body out to four chords; its fall at r = 5 is
the domain ending (body-to-far is 6.5), not termination. Figure `blocking_termination.png`.

> **A FALLING ROW EXISTS NOW — §16c, 2026-11-12.** The reducing O-grid built for #192 goes 16 at
> r = 0.6 to 8 at r = 3 and is the first blocking in this repo that does. §16c also measures that
> N(r) is NOT sufficient: the smallest count-reducing annulus is FLAT at 4 while its node count
> falls 72 to 48.

**And §12's nest moves that curve at ONE radius in 260** — +1 line at r = 1.08, a chord out,
not at the feature. §12a had to put it in the OUTERMOST layer; 15d says why that was never a
quirk of that case.

### 15c. §11's nest CONSERVES the line count, by construction **[V]**

On the ring demonstrator, N(r) = **24 at every radius from the body to the far field**. The
bookkeeping is exact and is in the generated document:

> 24 body corners → **2 far corners OMITTED** (stations 5 and 7) → 22 radials, **+ 2 transition
> diagonals** (`tL`, `tR`) → **24**.

Every terminated radial is replaced one for one by the diagonal that closes its transition.
So what §§11–12 built is a **local radial subdivision with a conformal closure**, not a nest:
the refinement still reaches the far field. Nothing in §11 or §12 measured this, and the
fold-when-thin of §11b is a separate and lesser problem.

**Two figures in those sections do not reproduce today** and the discrepancy is recorded rather
than chased: §11 quotes **648 quads, 0 inverted**; the committed `nested_wall.json` meshes to
3528 quads with **36** inverted, and the generator re-run at today's defaults gives 3528 with
**4**. The generator's defaults moved after §11 was written. **[V]**

### 15d. The model cannot express a count-REDUCING termination, and the mesher says so **[V]**

For N(r) to fall, a termination must remove more lines than it adds. The minimal such request is
two blocks below, one above, the radial between them terminating. Declared by hand
(`make_merge_refusal.py`, which writes the document and the config) and handed to the real
mesher:

> `[ERROR] edge 'n1' is declared kind 'interface' but is a side of 1 block(s) — the north of
> block 'R'. ... an 'interface' ... and a 'cut' ... are each a side of exactly two.`
> `HYBMESH_ERROR 8 TOPOLOGY`

**A block has four sides, each exactly ONE edge.** The block above can name `n0` or `n1`, never
both, so the one it does not name is a side of a single block and the arity rule refuses it.
A circumferential line therefore cannot be split below and whole above — and a radial can never
terminate without a replacement. **That is 15c's one-for-one, stated as a general law instead of
an accident of one construction.**

**It is also exactly what the vendor describes.** The *WS GUI Manual* §4.8.2: "for each layer
**three corners are substituted for each corner on the previous layer**" — three lines becoming
one is the operation refused above. **[V]**

**NOT A BUG. Do not "fix" the arity rule.** It is what makes welding allocation rather than
comparison (`.claude/rules/mesher-multiblock.md`), which is load bearing for a path with a 1e-7
wall spacing beside a 1e-1 far-field one. What this section concludes is that a terminating nest
needs a different EXPRESSIVENESS — a block side that is a CHAIN of edges — and that is a schema
decision, not a parameter.

> **SUPERSEDED IN PART, 2026-11-11 (#190), and kept as the record of why.** The schema decision
> above was taken: a side may now be an ordered list of edges joined end to end, and the SAME
> document `make_merge_refusal.py` writes meshes with zero inverted cells when T's south is
> declared `["n0", "n1"]`. What is superseded is "the model CANNOT express it". What is NOT
> superseded is everything else here: the arity rule was not touched and still produces the
> refusal quoted above for the one-edge spelling, the vendor reading is unchanged, and **§14's
> decision not to acquire local nesting stands on its own grounds** — the capability was built
> for refining a feature without the far field inheriting it, which §15e's own N(r) curve is the
> case for, and a declined method is not its consumer. Rules:
> `.claude/rules/mesher-block-side.md`. Decision and the rejected alternatives:
> `docs/adr/0003-a-block-side-may-be-a-chain-and-counts-propagate-out-of-it-never-into-it.md`.
>
> **AND SUPERSEDED IN FULL, 2026-11-12 (#192 steps 2-4), by §16.** The half #190 left standing —
> that this model cannot make a count FALL — is false too. The device is a corner shared by three
> blocks, the reduction is twice the ring's radial depth per corner block, and one such mesh runs
> the solver at the C-grid's operating point without NaN. The arity rule was not touched for that
> either, and the one-edge spelling above still produces the refusal quoted.

### 15e. The three zones, and where ours stops being like theirs **[V]** on ours, **[I]** on theirs

`blocking_three_zones.png`. Read off the icing wireframe: (1) a dense NEST hugging the ice,
(2) a TERMINATION where those rows end — the caption's own "loopback" — and (3) a sparse FAN
out to a rectangular far field. Ours has (3) and nothing else: the same lines that form the fan
run all the way in to the ice. **Measured on our iced case**: N(r) rises from 5 at r = 0.03 to
**51 at r = 2 and still 51 at r = 3**. It never falls. **[V]**

**So "radial fan" is not the difference** — both have one. The difference is zone 2.

**[I]** GridPro's model must therefore admit something this one does not; their wireframe is a
corner graph from which blocks are inferred, rather than a per-block list of four named edges.
**I did not verify that**, and no source read here states it.

### 15f. What this supersedes, and what it does not

- **SUPERSEDES §13d's "more levels and thicker bands".** Neither moves N(r) in this model. The
  blocker is expressiveness, not depth.
- **Does NOT supersede §14.** The decision not to acquire local nesting stands, on §14's own
  grounds; 15d adds a fourth that is stronger than the other three.
- **Does NOT retract §11b or §12c.** The fold-when-thin and the 32 NaN are real. They are now
  known to be downstream of a construction that was never the method.
- **The restart condition in §14b gains a prerequisite**: before a named target geometry is even
  worth discussing, the model would need a side that is a chain of edges.
- **§16 is the continuation**, written after #190 took the chain and #192 step 1 wrote down the
  three-block corner: it builds the count-reducing ring this section said could not exist, prices
  it in blocks per line ended, and runs one of them through gate 2.

### 15g. Named limits of this section

- **GridPro's own N(r) is NOT plotted anywhere here.** Their mesh is a picture; the icing frame is
  a wireframe and the C-grid frame a JPEG. Every number in 15b, 15c and 15e is from our own
  topologies. The zones in 15e are read off a frame and are marked as such.
- **"Four rows" in `blocking_three_zones.png` is a READ, not a measurement.** At the horn they
  merge into a band too dense to count at that resolution, and no number is supplied for it.
- **The ray method behind 15e has a tolerance** (35° of perpendicular) chosen to separate a ring
  from a radial. Nothing calibrates it; a blocking whose layers meet the body obliquely would be
  miscounted, and none of ours does.
- **TWO OF THE THREE FIGURES CANNOT BE REGENERATED from this repo**, and that is a property of
  the evidence rather than an oversight: `blocking_three_zones.png` and the left panel of
  `nest_refused.png`'s companion embed a crop of the YouTube frame, which §5 records as fetched
  and never committed (there is no licence to redistribute it). The NUMBERS they illustrate are
  all reproducible — `measure_block_partition.py` prints every one of them — and
  `blocking_termination.png` needs only the shipped and research topologies. A figure that cannot
  be rebuilt is a quotation; the instrument beside it is not.
- **An earlier draft of this section said our iced blocking had "one row"** and was wrong — the
  crop that produced the picture had cut off the rings at d = 0.93 and 1.99. Kept here because
  the error was in the FRAMING, not the measurement, and a figure that chooses its own window is
  the specimen worth remembering.


---

## 16. The count-reducing blocking, BUILT and PRICED — #192 steps 2 to 4

**2026-11-12.** §15d said this model cannot express a count-reducing termination and #190
superseded half of that. #192 step 1 then wrote down the device that can — a corner shared by
THREE blocks — and left the price unmeasured. This section is the price, and it supersedes §15d's
remaining half: **a count-reducing annulus is expressible, it meshes with zero inverted cells, its
N(r) falls, and one of them runs the solver at the C-grid's own operating point without NaN.**
Generators: `gridpro-blocking-method/make_reducing_annulus.py` and `make_reducing_cgrid.py`.
**Each committed document carries the command that wrote it in its own header**, because these
four differ from the generators' defaults in up to seven flags and a figure recorded against one
of them cannot be checked against another. Nothing in `config/`, `examples/`, `src/` or `include/`
was changed to write any of it. **[V]**

### 16a. The construction, and the law it obeys **[V]**

One UNIT of a reducing ring is two kinds of block:

- the **CORNER BLOCK** — two of its four sides are on the ring's INNER boundary and none is on the
  outer, so both of its radials end at one APEX and the three blocks that meet there are #192
  step 1's device;
- the **ORDINARY BLOCK** — one inner side, one outer side, two radials.

Opposite sides carry equal counts, so with *a* radial intervals and *m* on an ordinary side, a
ring of *K* units carries `K(2a + qm)` intervals on the inside and `Kqm` on the outside:

> **The reduction is `2 x K x a` — TWICE THE RING'S OWN RADIAL DEPTH, PER CORNER BLOCK.**

That is **not** one line per irregular node, and the correction matters because #192's body, the
step-1 rule and the step-1 design note all state the cost the other way. Taking the shipped
C-grid's aerofoil from 97 nodes to 193 while holding the far field at 145 needs 96 lines ended,
and that is **two corner blocks at depth 24, or four at depth 12** — not 96 of anything. The
smallest ring measured here ends **24** lines with **ONE** corner block and 2 off-valence nodes.

**WHY THE NODE-LOCAL READING DOES NOT ADD UP, since it is the one a reader arrives with.** A
valence-3 node is locally where one quad layer terminates, and that is not false. What is false is
summing it: **the lines a corner block removes do not end AT its irregular nodes, they TURN inside
it.** The corner block is the neighbouring blocks rotated a quarter turn — the grid lines entering
its two inner arcs leave through its two radials and run circumferentially around the ring — and
its two off-valence nodes are where that rotation is sewn to the blocks either side, not where
anything stops. So the bookkeeping is the block's `2a`, and the eight irregular nodes of 16d's
mesh account for 96 ended lines between them rather than eight.

**K CORNER BLOCKS MAKE K RADIAL CLASSES**, which is step 1's "N blocks at a corner make N count
classes" arriving a second time and from the other side: a corner block links each of its radials
to one of its own inner arcs rather than to the other radial, so the relation does not pass
through it. A ring of four units seeded once is refused, naming the group with no count. **[V]**

### 16b. The SMALLEST count-reducing annulus, and what it does NOT contain **[V]**

`reducing_annulus.json` — 4 blocks between two circles, one corner block and three ordinary,
inner 72 intervals and outer 48. Through the real binary at `MB_SPLIT_QUADS 0`:

| ring depth *a* | inner | outer | reduction | cells | inverted | nonortho max |
|---|---|---|---|---|---|---|
| 4 | 56 | 48 | 8 | 208 | 1 | 83.6 |
| 8 | 64 | 48 | 16 | 448 | 1 | 84.4 |
| 12 | 72 | 48 | 24 | 720 | 3 | 89.5 |
| 24 | 96 | 48 | 48 | 1728 | 171 | 90.0 |

The reduction is `2a` at every row, exactly, and at the committed row that is **4 blocks for 24
lines ended — 0.167 blocks per line**, the cheapest figure anywhere in this section and the one
16d's complete meshes have to be read against. **It contains NO interior irregular node at all** —
every interior node is valence 4, and the two nodes off the regular valence are both on the
BOUNDARY: the apex, where three blocks meet, at valence 4 on the outer circle, and the FOLD
between the corner block's two inner arcs, at valence **2** on the inner one. A valence-2 node on
a smooth boundary has exactly ONE cell spanning that boundary's own 180 degrees, which is the
89.5-degree non-orthogonality above. **No smoother removes it** (20 sweeps take 3 inverted cells
to 1 and 85 degrees; 100 sweeps give 35 and 90, which is §12's "converging is worse" again) and
**no embedding removes it either**: wrapping the ring in two ordinary rings leaves the fold cell
still spanning 180 of the 360 degrees at that node. What removes it is NOTCHING the fold inward
so the boundary TURNS there — available only when the ring's inner boundary is an INTERFACE,
never when it is the wall. **[V]**

**THE RING'S THICKNESS IS A QUALITY KNOB AND IT WAS NEARLY MISSED.** The same document at an outer
radius of 1.8 instead of 3.0 gives **48** inverted cells and a mean of 39.7 degrees against 3 and
23.8 — the corner block tapers from two inner arcs to one point across the ring, so a thin ring
taper is a sharp one. The figures in the table are at radius 3.0, which is the generator's default
and is the value the committed document's own header records. **[V]**

### 16c. N(r) DOES NOT REGISTER THE SMALLEST ONE, and that is a finding about the instrument **[V]**

`reduction_termination.png`. The smallest reducing annulus is **FLAT at 4** while its node count
falls 72 to 48, because all four of its block-partition lines do reach the outer boundary: the
count falls INSIDE the corner block, where the grid lines leaving its two inner arcs turn and
leave through its two radials. §15a's instrument measures where block BOUNDARIES end, and that is
not the same question as where grid LINES end.

The embedded reducing O-grid below **does** fall, and its full shape is **16 out to r = 0.79, then
20 to r = 0.99, then 12 to r = 1.79, then 8 to the far field** — it RISES once, over the notched
folds, before it falls. It is **the first blocking in this repo whose N(r) falls**, against the
FLAT rows §15b records for the shipped C-grid and the 160-block C/H. So the two reducing documents
disagree with each other on the instrument, which is the honest reading of both: N(r) is necessary
for a nest and is not sufficient for a count reduction.

**AND THE INSTRUMENT SPIKES WHERE A BLOCK BOUNDARY *IS* THE CIRCLE — 109 at exactly r = 1 and 105
at exactly r = 1.8**, the two ring interfaces, because every edge lying on the circle counts as
crossing it. That is N(r)'s own artefact and not a property of the blocking. The first draft of
`reduction_termination.png` sampled 40 points, missed both spikes AND the rise to 20, and showed a
clean staircase that is not what the mesh does; the figure now samples 400 and draws the two
interface radii as dotted lines with their values excluded. **A curve that looks tidy at the
sample rate you chose is the sample rate's shape, not the mesh's.**

### 16d. PRICED on a complete mesh: the reducing O-grid, and gate 2 PASSES **[V]**

`reducing_ogrid.json` — the shipped `circle_body.dat` and `circle_farfield.dat`, unchanged and
with their own boundary conditions, a body ring, a reducing ring and a far ring. The body carries
**192** intervals, twice the shipped O-grid's, and the far field carries the shipped O-grid's
**96**: #188's user story 1, on a circle. 36 blocks, 7872 quads, **0 inverted**, non-orthogonality
max 53.6 and mean 4.70 degrees, and exactly **8 interior irregular nodes — four of valence 3 at
the folds and four of valence 5 at the apexes**, which is the equation
`sum_interior (4 - d) = sum_boundary (d - 3)` balancing with nothing left on the boundary.

Blocks per grid line ended, measured rather than estimated, holding body 192 and far field 96, all
rows at `MB_SMOOTH_ITERS` 20 (the shipped default) and each at the best of four notch depths:

| folds *K* | depth *a* | blocks | **blocks per line ended** | cells | inverted | nonortho max / mean |
|---|---|---|---|---|---|---|
| 4 | 12 | 36 | **0.375** | 7872 | 0 | 53.6 / 4.70 |
| 8 | 6 | 72 | 0.750 | 7008 | 0 | 68.3 / 3.65 |
| 12 | 4 | 108 | 1.125 | 6720 | 0 | 78.4 / 3.09 |
| 16 | 3 | 144 | 1.500 | 6576 | 0 | 81.9 / 2.89 |
| 24 | 2 | 216 | 2.250 | 6432 | **144** | 87.6 / 6.88 |

Blocks per line ended is `9 / (2a)` for this family and depends on the ring's DEPTH alone, not on
how many folds it is spread over. More folds buy a lower MEAN and cost a higher MAX, until at 24
folds of depth 2 no notch tried keeps the smoother from inverting cells. **The cheapest row is
also the best one**, which is not what the quality trend alone would predict and is why the table
is here rather than one row of it. The shipped four-block O-grid's own figures for scale are 4608
quads, 2.02 max and 1.88 mean — so every row above is an order of magnitude worse at the worst
cell, and buys twice the body resolution for 1.4 to 1.7 times the cells.

**GATE 2, run 2026-11-12** through `reducing_ogrid_demo.json`, at the C-grid's own operating point
— M 0.2, Re 200, zero incidence, cfl 0.6 constant, `num_half_iter` 100, `print_convg_per_niter`
10, laminar NS:

    mesher    EXIT 0   15744 triangles, 0 inverted, nonortho max 53.58 mean 4.70
    getPGrid  EXIT 0   8016 vertices, 15744 elements, 288 boundary elements,
                       288 boundary condition flags
    unicones  EXIT 0   last printed "Global Iteration count 90" at
                       print_convg_per_niter 10 with num_half_iter 100 — 100
                       iterations. Residuals finite and O(1e-4) at 90. NO NaN.

The one NAN anywhere is in `tWall_values`' zeroth record, at t = 0 before any iteration — and the
shipped four-block C-grid, re-run the same day through `config/pipeline/multiblock_cgrid_demo.json`,
writes **the same NAN on the same line**. It is the solver's, not this mesh's. **[V]**

### 16e. PRICED on the shipped C-GRID: the cells are bought, gate 2 is NOT **[V]**

`reducing_cgrid.json` — the shipped `naca0012_cgrid.dat` and `cgrid_farfield.dat`, the chain
case's own seam ellipse (centre (1, 0), a = 2, b = 1) cut at 24 stations, a reducing band of 6
units out to a second ellipse, and an ordinary band to the far field. 97 nodes per aerofoil
surface, the four-block case's far-field counts, 40 radial intervals in all — the same budget the
shipped cases spend. 60 blocks. Against #191's own three-row table, in **the same bins and with
the same ruler** (that gate's `_bin_cells` and `_body_polyline`, imported rather than
re-implemented by `bin_added_cells.py` beside the generators, which is what makes the table
re-derivable rather than quoted; the shipped chain row below reproduces #191's figures to the cell,
which is what makes the new rows comparable). **The baseline is the shipped four-block C-grid AS
SHIPPED, at `MB_SMOOTH_ITERS` 20, while the two rows this work adds are at 0** — because at 20 the
reducing document has 120 inverted cells. The ADDED TOTALS cannot be affected by that, since a mesh
has the cell count its counts give it; which BIN a cell near a boundary lands in can be, and nothing
here corrects for it:

| | added | < 1 chord | 1-5 chords | > 5 chords |
|---|---|---|---|---|
| #191's CONTROL (four blocks, aerofoil raised to 97) | 3840 | 2480 (64.6%) | 880 (22.9%) | 480 (12.5%) |
| #191's SHIPPED CHAIN CASE | 3840 | 3042 (79.2%) | 772 (20.1%) | 26 (0.7%) |
| this work's own CONTROL (the same three bands, NO corner block) | 3840 | 2400 (62.5%) | 948 (24.7%) | 492 (12.8%) |
| **the REDUCING C-grid** | **2688** | **2402 (89.4%)** | **274 (10.2%)** | **12 (0.4%)** |

**The reduction buys 1152 quads, 30% of what the refinement costs**, and it is the first row in
this chain that adds FEWER cells rather than the same 3840 moved about. 89.4% of what it does add
lands within one chord. Its own control — the same three bands, the same radial counts, the same
curves and station placement, with the corner blocks replaced by ordinary ones — adds the same
3840 as every other row, which is what makes the 2688 the REDUCTION's and not the construction's.

**GATE 1 passes only with the smoother OFF.** At `MB_SMOOTH_ITERS 0` the reducing document has 0
inverted cells; at the shipped default of 20 it has 120. The figures above are at 0.

**GATE 2 FAILS: `Average norm is a nan, exiting....` at iteration 20** — and **so does its
control, at the same iteration**, which is the whole of what that measures. The NaN belongs to
this three-band C-grid construction and not to the reduction: both meshes carry a mean
non-orthogonality of 22 to 24 degrees against the shipped cases' 3.8 and 5.3, both report
`wall_first_cell_worst_rel` 0.924 against their 0.001, and that figure does not move when the
radial budget is raised from 40 to 64, so it is a defect in how this document places its wall
spacing rather than a resolution. **It was not chased.** Per #192 step 4, **no reduction on the
C-grid leaves `docs/research/`**; the reducing O-GRID is the one that passed, and it is the one
the device is cleared on.

### 16h. ONE RING IS A STEP; A STACK IS A STAIRCASE **[V]**

**2026-11-12, asked for on sight of 16d's own picture.** The reducing O-grid stops changing a
chord and a half off the body: beyond r = 1.8 it is one ordinary band of 8 blocks running all the
way to r = 10. The count falls ONCE. `make_reducing_stack.py` stacks the rings instead, with an
ordinary band between each pair, and the question it answers is whether the device composes.

**IT DOES, AND THE ARITHMETIC IS WHY IT CLOSES.** With two ordinary blocks per unit a reducing
ring takes `K(2a + 2m)` inner intervals to `2Km`, and `4K` inner stations to `2K`. Setting the
ring's radial depth `a` equal to its arc count `m` makes both exactly HALVE, so the next ring up
needs `K/2` folds to meet it and a stack is K, K/2, K/4… **`a = m` is not a choice**: the corner
block forces its two radials equal to the two inner arcs it carries, so a halving ring's depth is
the one it gets. Every level's stations then coincide with its neighbour's by construction, with
each ring offset half a unit from the one below — nothing is snapped and no tolerance appears.

Two documents, both on the shipped circle geometries, both `MB_SMOOTH_ITERS` 20:

| | blocks | quads | inverted | nonortho max / mean | body → far | N(r) |
|---|---|---|---|---|---|---|
| shipped 4-block O-grid | 4 | 4608 | 0 | 2.02 / 1.88 | 96 → 96 | 4 flat |
| ONE ring (`reducing_ogrid`) | 36 | 7872 | 0 | 53.6 / 4.70 | 192 → 96 | 16, 20, 12, 8 |
| `reducing_stack`, 2 stages | 92 | 6960 | 0 | 56.8 / 5.38 | 192 → 48 | 32, 24, 16, 12, 8 |
| `reducing_stack_deep`, 3 stages | 204 | 6516 | 0 | 74.8 / 4.41 | 192 → 24 | 64, 48, 32, 24, 16, 12, 8 |

**The stack is CHEAPER IN CELLS than the single ring it replaces** — 6516 against 7872 for the
same body resolution — because the count keeps coming down instead of being carried to the far
field at half strength. It costs blocks (204 against 36) and, at three stages, its worst cell.
Figure: `reduction_termination.png`, where one ring is a step and a stack is a staircase.

**K AT THE OUTERMOST RING IS THE BINDING CONSTRAINT, and it was found by it failing.** A stack of
K = 8/4/2 leaves the last ring two folds, so each corner block eats a quarter of the circle, and
that mesh has 6 inverted cells at the outermost fold at every notch tried. Starting at K = 16 so
the last ring has FOUR gives 0 inverted. **A corner block's angular span is its quality**, which
16b measured as the ring's thickness and this measures as the fold count; they are the same
statement about the taper.

### 16f. What this supersedes, and what it does not

- **SUPERSEDES the rest of §15d.** "The model cannot express a count-reducing termination" is now
  false in both halves: #190 took the chain, and this section builds the reduction the chain
  cannot deliver. The arity rule was not touched for either.
- **Does NOT supersede §14.** Local nesting stays declined on §14's own grounds. This is the
  general capability #188 asked for; a declined method is not its consumer, and nothing here
  nests anything into anything.
- **Does NOT make the capability available.** One reducing mesh passes gate 2 and one does not,
  no topology family emits a corner block, no shipped case carries one, and the best worst cell
  measured anywhere here is 53.6 degrees off orthogonal against a plain O-grid's 2.02.

### 16g. Named limits of this section

- **ONE operating point, and the claim is "the solver runs on this mesh".** Not convergence, not
  accuracy; no force is compared with anything, for the reason #157 recorded — no shipped case in
  this repo reaches a settled force here.
- **The C-grid construction is mine and it is not a good one**, which 16e's control is what
  establishes. A better station correspondence — derived from the four-block mesh's own grid lines
  the way #191's one seam station was, rather than placed by arc length — was not tried, and the
  wall-spacing defect behind `wall_first_cell_worst_rel` 0.924 was not diagnosed.
- **The notch depth was swept, not solved for.** 16b's claim that a fold needs the boundary to
  turn is a measurement over four values of one knob on two documents; no analysis says what the
  turn should be, and the three-cells-at-120-degrees ideal is argued from the valence, not
  measured.
- **N(r)'s two spikes are named in 16c and not FIXED.** `measure_block_partition.py` is #15a's
  instrument and this work did not change it; a reader who samples it at a ring interface gets 109
  and no warning. The plot excludes those radii; the tool does not.
- **The 52.8 that stood in this section for one review round** was the best worst cell at
  `MB_SMOOTH_ITERS` 0, left behind when 16d's table was re-measured at the shipped 20. It is
  recorded rather than silently corrected because it is the shape every figure in this repo decays
  into: a number that was true of a measurement nobody re-ran after the measurement moved.
- **16h's two stacks are gate-1 only.** Neither has been through `getPGrid` and `unicones`, so
  nothing here says a staircase solves; only 16d's single ring has a gate-2 run behind it.
- **Nothing here is gated.** These are research documents under `docs/research/`; no C++ check and
  no surface gate reads them, and they will rot exactly as §11's two figures did unless something
  does. That is the same state #192 step 1 closed for the three-block corner itself, and it is
  deliberate for this half: the ticket's step 4 is what decides whether a reduction becomes a
  shipped case, and it said no on the C-grid.

## Sources

Primary, read by me:

- **YouTube oEmbed**, `https://www.youtube.com/oembed?url=…&format=json`, for both video ids —
  returned the titles and the channel (`GridPro`, `https://www.youtube.com/@GridProHexa`).
- **The two watch pages**, fetched with `curl` (WebFetch returned only YouTube's footer for both,
  twice) — `itemprop` / `og:` meta tags for title, description, `uploadDate`, `duration`,
  `keywords` and interaction counts; the `shortDescription` JSON field for the full descriptions;
  the `captionTracks` array for the caption situation.
- **The videos' own published frames**, `https://i.ytimg.com/vi/<id>/maxresdefault.jpg` and
  `/maxres1.jpg`, `/maxres2.jpg`, `/maxres3.jpg` (1280 x 720), plus the 640 x 480 `sd1..3.jpg`
  that led me to them. Every quoted caption, status-bar count and dialog field above was read off
  these at full resolution; crops were enlarged with PIL/Lanczos, which is why §2a's skew figures
  read `0.052 / 0.410` here and not the `0.062 / 0.450` I first read at 640 x 480.
- **GridPro, *Airfoil with Icing* application article**, `gridpro.com/application/article/
  airfoil-with-icing/` — **404 live**, read via the Internet Archive raw capture
  `https://web.archive.org/web/20240813124309id_/…` with `curl`. Source of the 96,768 / 421 /
  ~1.5 hours table and of the eight verbatim figure captions.
- **Its eight figures**, `https://res.cloudinary.com/hrqxgjfxx/image/upload/v15039931*/*.png`,
  downloaded live. I read four: *Entire computational domain*, *Nested grid around the leading
  edge*, *Blocks used to generate the grid*, *Nested blocks at the leading edge*, plus *Surface
  mesh near leading edge with color by blocks* and *Smooth grids around the complex crevices…*.
- **CFD-Online forum thread 142231**, *How to create C-grid in GridPro*, read via the Wayback
  capture `20251015075538` with `curl` (live host: HTTP 403). Posts by `TedBrogan`
  (25 Sep 2014), Chitra (29 Sep 2014) and Vimal (24 Jan 2018), with their two dead tutorial links.
- **HTTP resolution of the two short links**, by `curl -I -L`: `bit.ly/3tWNKWt` →
  `sp.gridpro.com/Youtube_cases/airfoil_icing` → `gridpro.com/…` → **404**; `db.tt/f4xSP9fw` →
  `dl.dropboxusercontent.com/u/7271780/Tutorials/Draft/2D%20TUTORIALS/Airfoil%20Tutorial/
  Sharp_Edge/Airfoil_Sharp_edge.zip` → **404**.
- **Wayback CDX API** for `sp.gridpro.com/docs*`, `sp.gridpro.com/docs/WeeklyTutorials*`,
  `gridpro.com/application*` and `gridpro.com/Youtube_cases*`.

Secondary, in this repo, quoted rather than re-derived (each is marked **[V]** where it lives):

- `docs/research/gridpro-blocking-method.md` §2a (the blog's O-vs-C paragraph), §3 and §3b
  (GridPro's own sharp-TE airfoil tutorial, 14 blocks / 4,608 cells, the C-shaped wireframe and
  the 200% wrap), §18d/§23a/§24c (the retractions and the failed image counts).
- `docs/research/cell-size-range-within-a-block.md` §L4 (the FAQ's `nest` / `reverse_nest` /
  `Enrich` wording, and Eiseman's "clamps"/"collar").
- `.claude/rules/mesher-multiblock.md` (the count equivalence class) and
  `.claude/rules/mesher-smoothing.md` (what the smoother freezes), for §4's repo side only.

Tried and could not get:

- Either video's transcript — ASR-only track, `timedtext` empty in four formats; the player-API
  route was refused by policy and abandoned.
- `yt-dlp` / `youtube-transcript-api` — neither installed in this environment.
- `https://www.gridpro.com/application/article/airfoil-with-icing/` live — 404.
- `https://www.cfd-online.com/Forums/gridpro/…` live, via WebFetch — 403 on both threads tried.
- `web.archive.org` via WebFetch — blocked in this environment; `curl` worked.
- GridPro's *Sharp_Edge* airfoil tutorial package — 404 at its one known URL, not in the CDX index.
- Any Eiseman document using the phrase "automatic nested refinement".
