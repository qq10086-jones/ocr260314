# OCR260314 Engineering Task List v3
## De-ComfyUI Migration + Model-Capability Preservation

Version: v3.0  
Date: 2026-03-15  
Target repo: `qq10086-jones/ocr260314`

---

## 1. Objective

Replace the current ComfyUI-dependent production path with a Python-native architecture while preserving model-based restoration capability.

Primary outcome:

- no production dependency on ComfyUI;
- pluggable inpaint backends;
- refine-mask-first pipeline;
- stable layout planning and QA evidence.

---

## 2. Scope control

### In scope

- remove ComfyUI from runtime path;
- implement inpaint provider abstraction;
- implement OpenCV backend;
- integrate LaMa backend or equivalent non-Comfy model backend;
- build refine mask pipeline v1;
- update API/config/health;
- build benchmark and QA evidence.

### Out of scope for this milestone

- perfect artistic text style recreation;
- Photoshop-like free editing UI;
- advanced diffusion premium mode as default;
- large-scale frontend redesign.

---

## 3. Milestone structure

## M0. Baseline capture and benchmark set

### Goal
Freeze the current baseline before structural refactor.

### Tasks

- [ ] Select 30–50 representative samples from current use cases.
- [ ] Split sample types:
  - [ ] flat background
  - [ ] gradient background
  - [ ] product surface
  - [ ] portrait/body overlap
  - [ ] button/tag text
  - [ ] outline/shadow/glow text
- [ ] Run current baseline pipeline on all samples.
- [ ] Save outputs under `runs/benchmark_baseline_v1/`.
- [ ] Create manual label sheet for pass/fail notes.
- [ ] Save at least these artifacts:
  - [ ] original
  - [ ] OCR overlay
  - [ ] current mask
  - [ ] cleaned background
  - [ ] final render

### Exit criteria

- [ ] baseline set archived and reproducible.
- [ ] 30+ images categorized.

---

## M1. Remove ComfyUI from production dependency path

### Goal
Make the engine runnable without ComfyUI server/workflow health requirements.

### Tasks

- [ ] Audit all ComfyUI references in code/config/docs.
- [ ] Identify runtime-critical vs legacy-only references.
- [ ] Move all current ComfyUI-specific code into `legacy/` or behind feature flags.
- [ ] Remove ComfyUI requirements from default `/health` checks.
- [ ] Update `config/config.yaml` to use provider-based runtime settings.
- [ ] Add `providers.yaml` or equivalent config separation.
- [ ] Update README and docs to state new runtime path.

### Deliverables

- [ ] no mandatory `COMFY_SERVER`, `COMFY_ROOT_DIR`, workflow json for default execution.
- [ ] clean boot path without ComfyUI.

### Exit criteria

- [ ] `/process` can run in default mode with no ComfyUI installed.

---

## M2. Inpaint provider abstraction

### Goal
Replace one-off erase logic with backend interface.

### Tasks

- [ ] Create `app/providers/inpaint/base.py`.
- [ ] Define `InpaintProvider` interface.
- [ ] Define `InpaintResult` data structure.
- [ ] Add provider registry.
- [ ] Add backend router contract.
- [ ] Add config-based backend selection.
- [ ] Add per-region backend logging.

### Suggested interfaces

- `inpaint(image, mask, context) -> result`
- `healthcheck() -> status`
- `supports(mode, roi_meta) -> bool`

### Exit criteria

- [ ] system can switch backend by config.
- [ ] selected backend is recorded in manifest.

---

## M3. OpenCV backend hardening

### Goal
Keep a fast deterministic fallback backend.

### Tasks

- [ ] Move current Telea logic into `opencv_provider.py`.
- [ ] Support Telea and Navier-Stokes modes.
- [ ] Add optional pre/post smoothing.
- [ ] Add boundary blending helper.
- [ ] Add crop-local processing and paste-back utility.
- [ ] Add benchmark measurements for speed and quality.

### Exit criteria

- [ ] OpenCV backend passes all simple/flat-background benchmark cases.

---

## M4. LaMa backend integration

### Goal
Add model-based restoration without ComfyUI.

### Tasks

- [ ] Select exact LaMa integration mode:
  - [ ] local PyTorch inference
  - [ ] local service wrapper
  - [ ] ONNX/Torch alternative if needed
- [ ] Implement `lama_provider.py`.
- [ ] Normalize image/mask pre/post-processing.
- [ ] Add crop padding rules.
- [ ] Add max crop size and fallback rules.
- [ ] Add timeout and failure fallback to OpenCV.
- [ ] Add provider healthcheck.

### Exit criteria

- [ ] LaMa backend runs locally without ComfyUI.
- [ ] medium-complex benchmark set visibly improves over OpenCV baseline.

---

## M5. Refine mask pipeline v1

### Goal
Make erase masks significantly better than OCR polygon dilation.

### This is the highest-priority milestone.

### Tasks

#### M5-A. Framework
- [ ] Create `app/providers/mask_refine/base.py`.
- [ ] Create `app/providers/mask_refine/refine_pipeline.py`.
- [ ] Define per-region debug artifact schema.

#### M5-B. ROI feature extraction
- [ ] Crop ROI with configurable margin.
- [ ] Extract grayscale, LAB, HSV views.
- [ ] Compute edge density.
- [ ] Compute local contrast.
- [ ] Estimate text scale/stroke width heuristically.

#### M5-C. Candidate mask generation
- [ ] Polygon prior mask.
- [ ] Otsu threshold candidate.
- [ ] Adaptive threshold candidate.
- [ ] Edge candidate.
- [ ] Connected-components candidate.

#### M5-D. Candidate fusion
- [ ] Fuse candidates using text prior.
- [ ] Reject obvious background components.
- [ ] Produce glyph mask.
- [ ] Produce effect mask for outline/shadow.

#### M5-E. Adaptive expansion
- [ ] Replace fixed dilation kernel with per-ROI strategy.
- [ ] Expansion depends on text size and style complexity.
- [ ] Support asymmetric growth for drop-shadow cases.

#### M5-F. Debug artifacts
- [ ] Save `coarse_mask.png`.
- [ ] Save `glyph_mask.png`.
- [ ] Save `effect_mask.png`.
- [ ] Save `final_inpaint_mask.png`.
- [ ] Save ROI overlay comparison panel.

### Exit criteria

- [ ] benchmark shows clear improvement over current fixed-dilation baseline.
- [ ] at least 80% of easy/medium cases show reduced residual or reduced over-erase.

---

## M6. Detection/OCR decoupling

### Goal
Stop treating OCR output as the only text-region source.

### Tasks

- [ ] Define detector provider interface.
- [ ] Keep RapidOCR for recognition compatibility.
- [ ] Add detector stub or first detector integration.
- [ ] Merge OCR + detector outputs into common region schema.
- [ ] Add confidence-based region filtering.
- [ ] Add block grouping preprocessor.

### Exit criteria

- [ ] text region proposal no longer depends solely on OCR polygon.

---

## M7. Layout planner v1

### Goal
Turn translated text refill into an object-based render process.

### Tasks

- [ ] Define `TextBlock` schema.
- [ ] Implement block grouping.
- [ ] Implement font size estimation.
- [ ] Implement alignment estimation.
- [ ] Implement auto-wrap and shrink-to-fit.
- [ ] Implement title/button/tag heuristics.
- [ ] Support horizontal priority; gate vertical text for later if needed.
- [ ] Add overflow detection.

### Exit criteria

- [ ] translated text fits target regions without major spill/overlap in benchmark easy/medium set.

---

## M8. Router and runtime policies

### Goal
Choose backend per ROI or per job based on objective features.

### Tasks

- [ ] Implement `router.py`.
- [ ] Define ROI complexity features:
  - [ ] mask area ratio
  - [ ] edge density
  - [ ] texture variance
  - [ ] region size
  - [ ] image class
- [ ] Implement first routing rules.
- [ ] Add mode-aware routing (`fast`, `balanced`, `quality`).
- [ ] Add fallback chain:
  - [ ] Diffusers/Lama failure -> OpenCV
  - [ ] refine failure -> coarse mask fallback

### Exit criteria

- [ ] backend selection is deterministic and traceable.

---

## M9. QA and artifact system hardening

### Goal
Make quality visible and reviewable.

### Tasks

- [ ] Extend `job_manifest.json` with per-region records.
- [ ] Extend `qa_report.json` with backend and mask stats.
- [ ] Add residual OCR pass.
- [ ] Add outside-mask change score.
- [ ] Add boundary consistency score.
- [ ] Add render fit score.
- [ ] Add artifact gallery export for benchmark review.

### Exit criteria

- [ ] every benchmark run emits reproducible evidence package.

---

## M10. API and documentation refresh

### Goal
Align public interfaces and documentation with new architecture.

### Tasks

- [ ] Add `/detect` endpoint.
- [ ] Add `/mask_refine` endpoint.
- [ ] Update `/erase` to accept backend selection.
- [ ] Update `/process` mode options.
- [ ] Add `/providers` endpoint.
- [ ] Update README architecture diagram.
- [ ] Add ADR docs for major decisions.

### Exit criteria

- [ ] docs reflect real system architecture.

---

## M11. Optional premium backend gate

### Goal
Prepare future diffusion backend without contaminating the stable core.

### Tasks

- [ ] Define `diffusers_provider.py` interface.
- [ ] Keep behind `quality` mode and feature flag.
- [ ] Add timeout / memory guards.
- [ ] Compare against LaMa on a small hard-case benchmark set.

### Exit criteria

- [ ] premium backend is optional and isolated.

---

## 4. Priority order

### Must do first
1. M0 baseline capture
2. M1 remove Comfy dependency path
3. M2 provider abstraction
4. M5 refine mask pipeline v1
5. M4 LaMa backend

### Then do
6. M7 layout planner v1
7. M8 router
8. M9 QA hardening
9. M10 API/docs refresh

### Later / gated
10. M6 detector upgrade
11. M11 premium diffusion backend

---

## 5. Workstream split

## Workstream A: Core architecture
Owner type: senior backend / architect

- M1
- M2
- M8
- M10

## Workstream B: Mask refinement
Owner type: CV engineer

- M5
- parts of M6
- benchmark analysis support

## Workstream C: Inpaint backends
Owner type: ML engineer / image pipeline engineer

- M3
- M4
- M11

## Workstream D: Layout/render
Owner type: rendering engineer

- M7

## Workstream E: QA + benchmark
Owner type: QA / PM hybrid

- M0
- M9
- regression reporting

---

## 6. Governance rules

### Rule 1
No one is allowed to propose “just increase dilation” as milestone closure.

### Rule 2
No one is allowed to block progress on “finding a perfect model” before mask_refine v1 is done.

### Rule 3
ComfyUI cannot remain a hidden production dependency after M1 closes.

### Rule 4
Every milestone touching output quality must show benchmark artifacts, not only subjective screenshots.

### Rule 5
Layout work must not be blocked by backend perfection; it is its own workstream.

---

## 7. Definition of done

A v3 baseline release is done when:

- [ ] default runtime path requires no ComfyUI;
- [ ] OpenCV and LaMa providers are both available or stubbed with health-checked integration path;
- [ ] refine-mask v1 is implemented with saved debug artifacts;
- [ ] benchmark package compares new outputs against old baseline;
- [ ] `/process` produces final image + manifest + QA report;
- [ ] README/docs reflect actual runtime architecture.

---

## 8. Suggested first sprint

### Sprint-1 target

- [ ] M0 baseline archive
- [ ] M1 de-Comfy refactor
- [ ] M2 provider abstraction
- [ ] M3 OpenCV provider extraction
- [ ] M5-A/M5-B/M5-C first refine mask prototype

### Sprint-1 expected demo

For a fixed benchmark subset:

- current baseline output
- new refine mask overlays
- OpenCV provider output through new interface
- no ComfyUI runtime dependency

---

## 9. Final note

The project should now be framed as a **mask-first, backend-pluggable image text replacement engine**, not as a ComfyUI workflow project. That framing is the key to preventing future engineering drift.
