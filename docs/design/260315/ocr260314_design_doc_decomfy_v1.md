# OCR260314 Design Doc v3
## De-ComfyUI Architecture: Remove ComfyUI, Keep Model Capability

Version: v3.1
Date: 2026-03-16 (updated from v3.0 / 2026-03-15)
Target repo: `qq10086-jones/ocr260314`

> **Supersedes:** This document supersedes milestone definitions in `Local_Image_Translation_Task_List_v1_1.md`.
> The v1.1 task list M1/M2/M3/M4 definitions are no longer active. v3 milestone numbering (M0–M11) is the authoritative reference.
> ADR-007 (ComfyUI Degradation) is superseded by ADR-008 in this document — ComfyUI is no longer a fallback to maintain, it is removed from the production path entirely.

---

## 1. Executive Summary

This document updates the current image translation engine architecture from a **ComfyUI-dependent crop inpaint pipeline** to a **productizable Python-native engine** while preserving model-based restoration capability.

### Core decision

We will:

- remove **ComfyUI as the production execution shell**;
- keep **model capability** through pluggable backends;
- promote **mask refinement** into the primary technical focus;
- split restoration into **rule-based + model-based + layout-aware** stages;
- preserve existing OCR/translation/render assets where still useful.

### One-sentence architecture

`Detector/OCR -> Text Grouping -> Refine Mask -> Inpaint Backend Router -> Layout Planner -> Text Render -> QA Report`

---

## 2. Why this change

The current repo already has:

- a modular project skeleton under `app/`, `config/`, `tests/`, `runs/`;
- a retained legacy erase script using RapidOCR + polygon fill + dilation + OpenCV Telea;
- an HQ path that still depends on ComfyUI crop inpainting and related health checks/workflows;
- a stated migration target around OCR / grouping / crop / refined mask / inpaint / paste back.  

These facts are visible in the repo README and scripts. The current `step2_erase.py` fills OCR polygons, dilates the mask with a fixed kernel, and uses `cv2.inpaint(..., INPAINT_TELEA)`. The current `step3_universal_v1.1.py` still contains ComfyUI server/root/workflow configuration and sends mask-based tasks to ComfyUI after OCR polygon fill and dilation. This means the architectural bottleneck is not translation, but **mask quality and backend decoupling**. 

### Current pain points

1. **OCR box/polygon is not equal to true erase region**
   - outline text, shadow text, glow text, low-contrast text, button text all break this assumption.
2. **ComfyUI is acting as an execution shell, not as the core capability**
   - this makes production integration harder than necessary.
3. **Mask and restoration are tightly coupled**
   - poor mask quality forces the inpaint backend to hallucinate.
4. **Layout inference is still weakly objectized**
   - current pipeline can translate and refill, but not yet consistently plan the replacement layout.
5. **Failure routing is under-designed**
   - different image types should not share the same erase/inpaint policy.

---

## 3. Goals

### 3.1 Product goals

Build a local-first image text replacement engine that can:

- erase original text naturally;
- refill translated text with stable layout;
- work without ComfyUI;
- keep future support for stronger AI restoration backends;
- support batch processing and API service mode.

### 3.2 Technical goals

- make inpaint backends pluggable;
- elevate refine-mask quality to first-class status;
- preserve crop-level model invocation without node-workflow dependency;
- produce deterministic debug artifacts and QA evidence;
- allow later addition of diffusion backend without architectural rewrite.

### 3.3 Non-goals for this phase

- perfect recreation of every artistic text style;
- full Photoshop-grade free editing;
- universal one-pass perfection on all complex images.

---

## 4. Target architecture

```text
Input Image
  -> Preflight / job creation
  -> Text detection + OCR
  -> Text block grouping
  -> Style + color estimation
  -> Refine mask generation
  -> Background zone classifier  (NEW — per ROI, before inpaint)
       -> Type A: solid color
       -> Type B: gradient
       -> Type C: repeated texture / product surface
       -> Type D: complex scene
  -> Inpaint backend router  (driven by classifier output)
       -> Type A -> Solid fill + Poisson blend
       -> Type B -> Gradient reconstruction + Poisson blend
       -> Type C -> Patch synthesis + Poisson blend
       -> Type D -> LaMa / Diffusers (model fallback)
  -> Layout planning
  -> Text render
  -> QA scoring / artifacts / report
  -> Output image + evidence bundle
```

### Why background classification comes before backend selection

Product images are designed artifacts, not natural scenes. Their backgrounds follow deterministic design patterns (solid color bands, gradients, repeating product textures). Classical deterministic methods applied to the correct background type produce cleaner results than any inpainting model, because they reconstruct the exact design intent rather than approximating it with a learned prior trained on natural image statistics.

LaMa's "natural image prior" is the wrong prior for 80–90% of product image text regions. The classifier ensures LaMa is only invoked when it is actually the right tool.

---

## 5. Architectural principles

### 5.1 Remove shell, not capability

ComfyUI is removed as the orchestration shell. Model capability remains through internal Python providers.

### 5.2 Mask first

The most important quality lever is not prompt tuning. It is:

- text region accuracy;
- stroke coverage;
- shadow/outline compensation;
- correct expansion policy per ROI.

### 5.3 Classify background before selecting backend

The background zone type of each text ROI must be classified before any inpaint backend is selected. Different background types require fundamentally different reconstruction strategies. Using a model-based backend on a solid-color background is both wasteful and produces worse results than a simple deterministic fill.

Classification drives routing. Routing drives backend selection. This order is fixed.

### 5.4 Crop-local processing

High-quality restoration should happen on localized ROIs and then be pasted back with blending.

### 5.5 Poisson blending as universal post-process

Regardless of which inpaint strategy is used, the restored ROI must be pasted back using Poisson blending (`cv2.seamlessClone`). This eliminates boundary discontinuities that make the erasure visible. This applies to all backend types including the simple solid-fill case.

### 5.6 Observable pipeline

Every job must emit intermediate artifacts.

---

## 6. Updated module design

## 6.1 app/core

### Responsibilities

- pipeline orchestration;
- job config resolution;
- execution context;
- backend routing;
- error policy.

### New files proposed

- `app/core/pipeline.py`
- `app/core/router.py`
- `app/core/job_context.py`
- `app/core/policies.py`

---

## 6.2 app/providers/ocr

### Responsibilities

- OCR text recognition;
- optional detector-only support;
- standardized output schema.

### Input/Output contract

Output each region as:

```json
{
  "polygon": [[x, y], [x, y], [x, y], [x, y]],
  "bbox": [x1, y1, x2, y2],
  "text": "example",
  "score": 0.98,
  "direction": "horizontal"
}
```

### Phase plan

- keep RapidOCR for recognition compatibility;
- add detector abstraction so OCR recognition and text region proposal are no longer the same thing.

---

## 6.3 app/providers/detection

### Responsibilities

- produce better text region candidates than OCR polygon alone;
- support future DBNet/CRAFT-like detector integration;
- support detector ensembles if needed.

### Why this matters

The current scripts use OCR polygons directly as erase masks, then dilate them. This is too coarse for production.

---

## 6.4 app/providers/mask_refine

### This is the new core module.

### Responsibilities

For each text region / block:

1. crop ROI with margin;
2. estimate foreground/background separation;
3. detect likely glyph pixels;
4. compensate outline/shadow/glow;
5. compute adaptive expansion;
6. produce multiple masks.

### Output masks

```json
{
  "coarse_mask": "polygon-derived mask",
  "glyph_mask": "foreground-stroke mask",
  "effect_mask": "outline/shadow/glow extension",
  "inpaint_mask": "final mask for erase backend"
}
```

### Recommended refine stages

#### Stage A: polygon prior
- initialize coarse region from detector/OCR polygon.

#### Stage B: ROI binarization
- Otsu / adaptive threshold / local contrast threshold.

#### Stage C: edge/stroke extraction
- Sobel / Canny / morphological gradient.

#### Stage D: connected components
- reject components clearly inconsistent with text prior.

#### Stage E: style compensation
- if text likely has outline or shadow, grow asymmetrically or union extra components.

#### Stage F: adaptive expansion
- expansion proportional to font size / stroke width / local complexity.

### Key rule

No fixed one-size-fits-all dilation kernel in production.

---

## 6.5 app/providers/bg_classifier  (NEW)

### Responsibilities

Classify the background type of each text ROI before any inpaint backend is invoked.
This is a pure classical CV module — no ML required.

### Input

- ROI crop with configurable outer margin (recommended: 1.5× bounding box)
- Mask of text pixels within the ROI (from refine mask pipeline)

### Classification method

Sampling region: pixels within the expanded ROI but outside the text mask (i.e., the visible background surrounding the text).

```
Step 1 — Color variance analysis
  Compute per-channel std dev of sampled background pixels.
  If max(std_R, std_G, std_B) < threshold_solid (e.g., 12):
      -> Type A (solid color)

Step 2 — Gradient linearity test
  Fit linear model: color = a*x + b*y + c  (least-squares, per channel)
  Compute residual R² of the fit.
  If R² > threshold_gradient (e.g., 0.85):
      -> Type B (gradient)

Step 3 — Texture periodicity test
  Apply 2D FFT to grayscale ROI (background pixels only).
  Detect dominant frequency peaks beyond DC component.
  If peak energy ratio > threshold_texture (e.g., 0.30):
      -> Type C (repeated texture / product surface)

Step 4 — Default
  -> Type D (complex scene — model required)
```

### Output schema

```json
{
  "bg_type": "A" | "B" | "C" | "D",
  "confidence": 0.0–1.0,
  "dominant_color": [R, G, B],
  "gradient_params": {"axis": "x|y|radial", "color_start": [...], "color_end": [...]},
  "texture_period_px": 12,
  "debug_sample_mask": "path/to/debug_bg_sample.png"
}
```

### Thresholds

All thresholds are configurable in `config/config.yaml` under `bg_classifier:` block.
Initial defaults are suggestions; calibrate against the benchmark set.

---

## 6.6 app/providers/inpaint

### Responsibilities

Provide pluggable erase backends behind a unified interface.
Backend selection is driven by the `bg_classifier` output — not by heuristics internal to the router.

### Standard interface

```python
class InpaintProvider:
    def inpaint(self, image, mask, context) -> InpaintResult:
        ...
```

`context` carries the `BgClassifierResult` so each provider can access classification data.

### Backends

#### Backend A: SolidFillProvider (Type A)
Use for: solid color or near-solid backgrounds (most product banners, color-block zones).

Method:
- Compute weighted median color from sampled background pixels.
- Fill masked region with this color.
- Apply Gaussian feather at mask boundary.
- Apply Poisson blend (`cv2.seamlessClone`) on paste-back.

Expected quality: near-perfect for truly flat backgrounds.

#### Backend B: GradientFillProvider (Type B)
Use for: linear or radial gradient backgrounds.

Method:
- From sampled background pixels, solve least-squares for per-channel gradient:
  `color(x, y) = a·x + b·y + c`  (3 parameters per channel, solved with `numpy.linalg.lstsq`)
- Fill masked region by evaluating the fitted polynomial at each pixel coordinate.
- Poisson blend on paste-back.

Mathematical note: this is a linear regression in 2D coordinate space. The solution is exact for linear gradients and a reasonable approximation for mild radial gradients. For radial gradients, extend to `color(x,y) = a·x² + b·y² + c·x + d·y + e` (5 parameters).

Expected quality: clean and accurate for the vast majority of designed banner gradients.

#### Backend C: PatchSynthesisProvider (Type C)
Use for: repeated textures, product surfaces (fabric, paper, metal, etc.).

Method:
- Extract candidate patches from background region (outside text mask).
- For each masked pixel, find the best-matching patch by SSD (sum of squared differences) on known boundary pixels.
- Fill using Criminisi exemplar-based synthesis or simplified patch copy.
- Poisson blend on paste-back.

Implementation options (in order of quality):
1. OpenCV `INPAINT_TELEA` with large radius as baseline.
2. Custom exemplar-based fill using `cv2.matchTemplate` for patch search.
3. Full Criminisi algorithm if baseline quality is insufficient.

Expected quality: good for regular textures; degrades on highly irregular surfaces.

#### Backend D: LamaInpaintProvider (Type D — model fallback only)
Use for: complex photographic backgrounds that cannot be handled by the above methods.

Characteristics:
- Invoked only for Type D ROIs.
- No ComfyUI required; pure Python torch inference.
- Crop-local: inpaint on ROI crop, paste back with Poisson blend.
- Fallback chain: LaMa failure → Backend C (patch synthesis) → Backend A (solid fill).

Expected quality: best-effort; acceptable for most complex cases, may leave artifacts on extreme cases.

#### Backend E: DiffusersInpaintProvider (future / quality mode gate)
Use for: Type D ROIs where LaMa result is insufficient; requires explicit `quality` mode.

Characteristics:
- Gated behind `quality` runtime mode and a feature flag.
- Not part of default or balanced mode pipelines.

### Routing summary

```text
bg_classifier output
        │
        ├─ Type A (solid)    → SolidFillProvider      ─┐
        ├─ Type B (gradient) → GradientFillProvider    ├─→ Poisson blend → paste back
        ├─ Type C (texture)  → PatchSynthesisProvider  ┤
        └─ Type D (complex)  → LamaInpaintProvider     ─┘
                                      └─ failure → PatchSynthesisProvider → SolidFillProvider
```

### Coverage expectation for product images

| Type | Estimated share in product images | Backend | Quality expectation |
|------|----------------------------------|---------|-------------------|
| A | 50–60% | SolidFill | Near-perfect |
| B | 15–20% | GradientFill | Clean, accurate |
| C | 15–20% | PatchSynthesis | Good for regular textures |
| D | 5–10% | LaMa | Best-effort |

LaMa is invoked for approximately 5–10% of product image ROIs.
This significantly reduces VRAM pressure compared to using LaMa as the default medium-quality backend.

---

## 6.6 app/render/layout

### Responsibilities

Turn recognized/transformed text into a renderable block model.

### Required text object schema

```json
{
  "block_id": "blk_001",
  "polygon": [...],
  "bbox": [x1, y1, x2, y2],
  "source_text": "SALE",
  "target_text": "セール",
  "font_size_est": 42,
  "font_weight_est": 700,
  "text_color": [255,255,255],
  "stroke_color": [0,0,0],
  "alignment": "center",
  "line_spacing": 1.1,
  "rotation": 0,
  "region_type": "title"
}
```

### Layout planner responsibilities

- block grouping;
- line reconstruction;
- candidate font sizing;
- auto wrap;
- shrink-to-fit;
- alignment recovery;
- vertical/horizontal mode;
- button/label/title heuristics.

### Important note

This module should be independent from erase backend selection.

---

## 6.7 app/services/qa

### Responsibilities

Emit evidence and quality scoring.

### Artifacts per job

- original image
- OCR regions overlay
- coarse masks
- refined masks
- selected backend per ROI
- cleaned background
- final render
- diff heatmap
- QA json report

### Suggested metrics

- residual OCR score;
- mask outside-change ratio;
- boundary change score;
- text fit score;
- overlap/overflow score;
- edge-consistency score.

---

## 7. Data model changes

## 7.1 Job manifest

Add per-region structured records:

```json
{
  "region_id": "r_001",
  "ocr_text": "SALE",
  "translated_text": "セール",
  "polygon": [[...]],
  "bbox": [...],
  "style": {...},
  "mask_stats": {
    "coarse_area": 1234,
    "glyph_area": 980,
    "final_area": 1450
  },
  "bg_classification": {
    "bg_type": "B",
    "confidence": 0.91,
    "dominant_color": [34, 87, 210],
    "gradient_params": {"axis": "x", "color_start": [20,60,190], "color_end": [50,110,230]}
  },
  "backend_selected": "gradient_fill",
  "qa": {
    "residual_score": 0.08,
    "outside_change": 0.03
  }
}
```

---

## 8. Runtime modes

### 8.1 fast mode

- OCR/detection
- light refine mask (polygon + fixed dilation)
- bg_classifier: enabled (lightweight — color variance only, skip FFT)
- routing: Type A/B → deterministic fill; Type C/D → OpenCV Telea fallback
- simple layout
- no LaMa invocation

### 8.2 balanced mode  (default for product images)

- OCR/detection
- full refine mask pipeline
- bg_classifier: full (color variance + gradient fit + FFT)
- routing: Type A → SolidFill; Type B → GradientFill; Type C → PatchSynthesis; Type D → LaMa
- Poisson blend on all paste-backs
- standard layout

### 8.3 quality mode

- OCR/detection
- full refine mask pipeline
- bg_classifier: full
- routing: same as balanced, but Type D → LaMa → Diffusers (if LaMa quality score below threshold)
- multi-candidate inpaint for Type D (select best by QA metric)
- expanded QA artifacts
- layout with overflow detection and shrink-to-fit

### Mode selection guidance for product images

Use `balanced` as the default. It covers 90–95% of product image cases without invoking LaMa.
Use `fast` for batch preview or speed-sensitive workflows.
Use `quality` only for Type D edge cases that require diffusion-model quality.

---

## 9. Migration strategy from current repo

## 9.1 Keep

- project skeleton under `app/`, `config/`, `tests/`, `runs/`;
- job artifact pattern;
- OCR + translation integration assets;
- current render/backfill learnings;
- QA reporting direction.

## 9.2 Remove from production path

- direct dependency on ComfyUI server availability;
- workflow json as execution dependency;
- `/health` checks that assume ComfyUI presence;
- crop task submission through node graph API.

## 9.3 Replace with

- Python-native inpaint provider abstraction;
- backend router;
- ROI refine mask module;
- model package management per provider.

## 9.4 Pre-refactor safety requirement

**Before any structural refactor begins, a smoke test baseline must exist.**

Minimum requirement:
- at least one end-to-end test that calls `/process` and asserts a non-error response and output file existence;
- test must be runnable without ComfyUI (OpenCV fast mode);
- test must be committed and passing before M1 refactor work starts.

Rationale: without this baseline, any regression introduced during De-Comfy migration cannot be detected automatically. Refactoring without a safety net is not acceptable given the scope of changes in M1–M5.

## 9.5 Legacy script cleanup

The following root-level scripts are retained for reference only and must not be modified or extended:

- `step1_test.py`
- `step2_erase.py`
- `step3_universal_v1.1.py`
- `test_v3.py`
- `test_v4.py`
- `capture_baseline.py`
- `run_test.py`
- `convert_test.py`

These will be moved to `scripts/legacy/` during M1, after the smoke test baseline is confirmed passing. They are **not** to be deleted; they serve as the documented pre-migration reference implementation.

---

## 10. Directory update proposal

```text
app/
  api/
  core/
    pipeline.py
    router.py           ← driven by bg_classifier output
    job_context.py
    policies.py
  providers/
    ocr/
      rapidocr_provider.py
    detection/
      base.py
      detector_stub.py
    bg_classifier/      ← NEW: background zone classification
      base.py
      classifier.py     ← color variance + gradient fit + FFT pipeline
      gradient_fit.py   ← least-squares gradient reconstruction math
    mask_refine/
      base.py
      refine_pipeline.py
      roi_features.py
    inpaint/
      base.py
      solid_fill_provider.py      ← Type A
      gradient_fill_provider.py   ← Type B (uses gradient_fit.py)
      patch_synthesis_provider.py ← Type C (exemplar-based)
      opencv_provider.py          ← Type C/D fast fallback (Telea/NS)
      lama_provider.py            ← Type D only
      diffusers_provider.py       ← Type D quality mode (future)
      legacy/
        comfyui_provider.py       ← moved here from main path
      poisson_blend.py            ← shared paste-back utility
    translate/
  render/
    layout_planner.py
    style_estimator.py
    text_renderer.py
  services/
    artifacts.py
    qa.py
    locks.py
  utils/
config/
  config.yaml           ← includes bg_classifier thresholds block
  providers.yaml
scripts/
  legacy/               ← moved root-level legacy scripts
runs/
docs/
  adr/
tests/
```

---

## 11. API update proposal

### Existing direction
Current API already has `/health`, `/process`, `/ocr`, `/erase`, `/render` in README.

### Updated API proposal

#### POST `/process`
Main end-to-end pipeline.

#### POST `/detect`
Returns OCR/detection regions.

#### POST `/mask_refine`
Returns masks and debug overlays.

#### POST `/erase`
Runs erase only with selected backend.

#### POST `/render`
Runs layout + refill only.

#### GET `/providers`
Lists available inpaint backends and health.

### Health changes

`/health` should report:
- OCR provider availability;
- translation provider availability;
- inpaint providers availability;
- model files readiness;
- font readiness.

It should no longer depend on ComfyUI workflow/server presence.

---

## 12. Key technical decisions (ADR candidates)

> **Numbering note:** The existing repository already has ADR-005, ADR-006, ADR-007 under `docs/adr/`.
> New decisions from this design document are numbered ADR-008 onwards to avoid conflict.
> ADR-007 (ComfyUI Degradation) is superseded by ADR-008 below.

### ADR-008
ComfyUI is removed from the production path entirely.
ADR-007 (lightweight ComfyUI degradation/fallback) is superseded. There is no longer a fallback to ComfyUI — the fallback chain is LaMa → OpenCV.

### ADR-009
Mask refinement (`mask_refine`) becomes a first-class provider module.
It is no longer embedded inside the engine or treated as a preprocessing step.

### ADR-010
Inpainting is provider-based and router-selected per ROI.
A single backend-for-all policy is not acceptable in production.

### ADR-011
All model-based restoration is crop-local by default.
Full-image inference is not the default path. ROI crop → inpaint → paste-back is the standard.

### ADR-012
Every job emits QA/debug evidence by design.
Silent success is not acceptable. The artifact bundle is a first-class output.

### ADR-013
Background zone classification is a mandatory step before inpaint backend selection.
Routing based solely on mask area or heuristic complexity estimates is not acceptable in production.

### ADR-014
Poisson blending (`cv2.seamlessClone`) is the required paste-back method for all inpaint backends.
Direct pixel copy without blending is not acceptable even for solid-fill cases.

### ADR-006 re-evaluation gate (critical — scope reduced)
ADR-006 (Async queue and VRAM mutex, deferred to v1.2+) must be **explicitly re-evaluated before M4 (LaMa integration) begins**.

Note: with the bg_classifier routing, LaMa is now invoked only for Type D ROIs (~5–10% of product image ROIs). This significantly reduces the frequency and cumulative VRAM pressure compared to the earlier design where LaMa was the default medium-quality backend. The re-evaluation may conclude that ADR-006 remains deferred — but this conclusion must be written down explicitly after measuring actual LaMa invocation frequency on the benchmark set.

Reason: LaMa requires `torch` as a dependency. This introduces GPU memory usage that may conflict with other local GPU workloads (e.g., local LLM inference). The original ADR-006 deferral assumed no heavy ML dependency in the production path. That assumption is no longer valid once LaMa is added.

Re-evaluation output must answer:
- Is single-process torch inference stable enough without a VRAM mutex?
- Does cold-start latency require a keep-warm strategy?
- Is a 300s timeout still sufficient for LaMa inference on target hardware?

If any answer is "no," ADR-006 implementation must be approved before M4 closes.

---

## 13. Risks and mitigations

### Risk 1: Team keeps tuning OCR boxes instead of building refine mask
**Mitigation:** declare `mask_refine` as the primary milestone gate.

### Risk 2: Team replaces ComfyUI with a single monolithic model backend
**Mitigation:** force provider interface + router.

### Risk 3: LaMa integration works but layout still fails visually
**Mitigation:** parallelize style estimation and layout planner as independent workstream.

### Risk 4: Diffusers backend introduces nondeterminism too early
**Mitigation:** keep it gated behind quality mode.

### Risk 5: QA remains subjective
**Mitigation:** standardize artifact bundle and scoring thresholds.

### Risk 6: LaMa introduces torch dependency which silently triggers ADR-006 deferred scope
**Probability:** High — torch adds GPU memory pressure, cold-start latency, and model loading complexity, all of which were explicitly deferred in ADR-006.
**Impact:** High — if VRAM contention occurs in production, the 300s timeout becomes insufficient and the single-request mutex becomes inadequate.
**Mitigation:** Treat ADR-006 re-evaluation as a mandatory gate before M4. Do not merge LaMa integration until re-evaluation is documented and signed off. See Section 12 (ADR-006 re-evaluation gate).

### Risk 7: Refactor starts without test safety net, regressions go undetected
**Probability:** High — current test coverage is near zero.
**Impact:** High — M1 touches engine core, provider abstraction, config; any silent regression in the main pipeline cannot be caught.
**Mitigation:** Section 9.4 pre-refactor smoke test is a hard prerequisite. No M1 code work until at least one passing end-to-end test exists.

---

## 14. Success criteria for v3

A release is acceptable when:

1. production path no longer requires ComfyUI;
2. at least two inpaint providers are runnable (`opencv`, `lama`);
3. refined mask visibly outperforms OCR polygon dilation baseline on the benchmark set;
4. per-region backend routing is logged in the manifest;
5. final outputs and QA evidence are reproducible under `runs/...`;
6. at least one automated smoke test is passing in `tests/`;
7. legacy root-level scripts have been moved to `scripts/legacy/`;
8. ADR-006 re-evaluation is documented before LaMa integration closes.

---

## 15. Immediate next milestone recommendation

### M1: De-Comfy foundation + Refine Mask v1

This is the highest-value milestone.

Deliverables:
- remove ComfyUI from runtime dependency path;
- add inpaint provider abstraction;
- add OpenCV provider;
- add LaMa provider stub or real integration;
- implement refine mask pipeline v1;
- add benchmark set and QA overlays.

This milestone should be completed before any style-transfer or advanced fancy layout work.

---

## 16. Guidance for implementation teams

### PM guidance
Do not frame the project as “find a better model.” The real framing is:

- better text region proposal;
- better mask refinement;
- backend decoupling;
- layout objectization;
- measurable QA.

### Engineering guidance
If an engineer proposes “just increase dilation” or “just change prompt,” that is not an acceptable architectural answer.

### QA guidance
Every sample must compare:
- baseline OCR polygon dilation result;
- refine-mask result;
- backend selected;
- final rendered result.

---

## 17. Final recommendation

The correct product direction is **not** to abandon model capability. It is to **internalize model capability behind your own provider interface** and stop making ComfyUI the main runtime dependency.

The highest leverage engineering move is to make `mask_refine` the center of the system, because poor erase masks cannot be rescued reliably by any backend.
