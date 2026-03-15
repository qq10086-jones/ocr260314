# OCR260314 Design Doc v3
## De-ComfyUI Architecture: Remove ComfyUI, Keep Model Capability

Version: v3.0  
Date: 2026-03-15  
Target repo: `qq10086-jones/ocr260314`

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
  -> Inpaint backend router
       -> OpenCV backend
       -> LaMa backend
       -> Diffusers backend (optional / later)
  -> Layout planning
  -> Text render
  -> QA scoring / artifacts / report
  -> Output image + evidence bundle
```

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

### 5.3 Backend routing instead of one backend for all images

Different image classes require different erase strategies.

### 5.4 Crop-local processing

High-quality restoration should happen on localized ROIs and then be pasted back with blending.

### 5.5 Observable pipeline

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

## 6.5 app/providers/inpaint

### Responsibilities

Provide pluggable erase backends behind a unified interface.

### Standard interface

```python
class InpaintProvider:
    def inpaint(self, image, mask, context) -> InpaintResult:
        ...
```

### Backends

#### Backend A: OpenCVInpaintProvider
Use for:
- flat backgrounds;
- low texture;
- small text area;
- fast fallback.

Methods:
- Telea
- Navier-Stokes
- optional blending refinement

#### Backend B: LamaInpaintProvider
Use for:
- medium-complex backgrounds;
- product surfaces;
- repeated textures;
- local crop restoration.

Characteristics:
- no ComfyUI required;
- service-friendly;
- good engineering fit for local execution.

#### Backend C: DiffusersInpaintProvider
Use for:
- difficult ROIs;
- strong texture ambiguity;
- future high-quality mode.

Characteristics:
- direct Python inference;
- no node workflow;
- supports future SD/SDXL-style inpaint backends.

### Backend router

Routing should consider:

- ROI size;
- mask area ratio;
- edge density;
- texture variance;
- image class;
- requested quality mode.

Example routing:

```text
simple background -> OpenCV
medium complexity -> LaMa
high complexity / premium mode -> Diffusers
```

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
  "backend_selected": "lama",
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
- light refine mask
- OpenCV only
- simple layout

### 8.2 balanced mode

- OCR/detection
- full refine mask
- router: OpenCV or LaMa
- standard layout

### 8.3 quality mode

- OCR/detection
- full refine mask
- router may call Diffusers backend
- multi-candidate render/inpaint
- expanded QA artifacts

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

---

## 10. Directory update proposal

```text
app/
  api/
  core/
    pipeline.py
    router.py
    job_context.py
    policies.py
  providers/
    ocr/
      rapidocr_provider.py
    detection/
      base.py
      detector_stub.py
    mask_refine/
      base.py
      refine_pipeline.py
      roi_features.py
    inpaint/
      base.py
      opencv_provider.py
      lama_provider.py
      diffusers_provider.py
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
  config.yaml
  providers.yaml
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

### ADR-001
ComfyUI is removed from production path.

### ADR-002
Mask refinement becomes a first-class provider.

### ADR-003
Inpainting is provider-based and router-selected.

### ADR-004
All restoration is crop-local by default.

### ADR-005
Every job emits QA/debug evidence by design.

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

---

## 14. Success criteria for v3

A release is acceptable when:

1. production path no longer requires ComfyUI;
2. at least two inpaint providers are runnable (`opencv`, `lama`);
3. refined mask visibly outperforms OCR polygon dilation baseline on the benchmark set;
4. per-region backend routing is logged in the manifest;
5. final outputs and QA evidence are reproducible under `runs/...`.

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
