# OCR260314 Engineering Task List v3
## De-ComfyUI Migration + Model-Capability Preservation

Version: v3.1
Date: 2026-03-16 (updated from v3.0 / 2026-03-15)
Target repo: `qq10086-jones/ocr260314`

> **Supersedes:** `Local_Image_Translation_Task_List_v1_1.md` milestone definitions (M1–M4) are no longer active.
> This document is the sole authoritative task list. When in conflict, v3 always wins.

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

## M0. Baseline capture + smoke test safety net

### Goal
Two things must be done before any structural refactor: freeze the current output baseline, and establish a minimum automated test so regressions can be detected.

### Tasks

#### M0-A. Benchmark baseline (already partially done — runs/benchmark_baseline_v3/)
- [ ] Verify `runs/benchmark_baseline_v3/` artifacts are complete and reproducible.
- [ ] Confirm sample coverage across types:
  - [ ] flat background
  - [ ] gradient background
  - [ ] product surface
  - [ ] portrait/body overlap
  - [ ] button/tag text
  - [ ] outline/shadow/glow text
- [ ] Target: 30+ samples minimum (current 4 samples are insufficient for benchmark).
- [ ] Each sample must have: original, OCR overlay, current mask, cleaned background, final render, manifest.json.

#### M0-B. Smoke test baseline (new — hard prerequisite for M1)
- [ ] Write `tests/test_smoke.py` with at least one end-to-end test:
  - Calls `/process` (or engine directly) on a known sample image.
  - Asserts: no exception, output file exists, result.json contains expected keys.
  - Must run in OpenCV fast mode only (no ComfyUI required).
- [ ] Confirm test passes before any M1 refactor work begins.
- [ ] Test must be committed and green in CI/local before M1 starts.

#### M0-C. Legacy script inventory
- [ ] Document root-level legacy scripts in `docs/reports/legacy_code_mapping.md` (update existing file).
- [ ] Confirm each script's functional equivalent exists in `app/`.
- [ ] Do not delete yet — move happens during M1.

### Exit criteria

- [ ] `runs/benchmark_baseline_v3/` contains 30+ categorized samples.
- [ ] `tests/test_smoke.py` exists and passes without ComfyUI.
- [ ] Legacy script mapping is documented.
- [ ] **M1 cannot start until all M0-B criteria are met.**

---

## M1. Remove ComfyUI from production dependency path

### Goal
Make the engine runnable without ComfyUI server/workflow health requirements.

**Prerequisite: M0-B smoke test must be passing before this milestone starts.**

### Tasks

#### ComfyUI removal
- [ ] Audit all ComfyUI references in code/config/docs.
- [ ] Identify runtime-critical vs legacy-only references.
- [ ] Move `app/providers/inpaint/comfyui_provider.py` and related runtime state to `app/providers/inpaint/legacy/`.
- [ ] Remove `app/core/runtime_state.py` ComfyUI state from default boot path (or gate behind explicit opt-in config).
- [ ] Remove ComfyUI requirements from default `/health` checks.
- [ ] Update `config/config.yaml` to use provider-based runtime settings (no ComfyUI defaults).
- [ ] Add `providers.yaml` or equivalent config separation.
- [ ] Update README and docs to state new runtime path.

#### Legacy script cleanup
- [ ] Move all root-level legacy scripts to `scripts/legacy/`:
  - `step1_test.py`, `step2_erase.py`, `step3_universal_v1.1.py`
  - `test_v3.py`, `test_v4.py`
  - `capture_baseline.py`, `run_test.py`, `convert_test.py`
- [ ] Add a `scripts/legacy/README.md` explaining these are pre-migration references.
- [ ] Do not delete these files.

#### Test continuity
- [ ] Confirm smoke test still passes after ComfyUI removal.
- [ ] Smoke test failure during M1 is a blocker — fix before proceeding.

### Deliverables

- [ ] No mandatory `COMFY_SERVER`, `COMFY_ROOT_DIR`, workflow json for default execution.
- [ ] Clean boot path without ComfyUI.
- [ ] Root directory is free of legacy scripts.

### Exit criteria

- [ ] `/process` can run in default mode with no ComfyUI installed.
- [ ] Smoke test still passes after refactor.
- [ ] `scripts/legacy/` contains all moved scripts.

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

## M3. Deterministic inpaint backends + background classifier

### Goal
Build the full suite of deterministic (non-model) inpaint backends and the background zone classifier that drives routing. This covers ~90% of product image cases without any ML model.

### M3-A. Background zone classifier

- [ ] Create `app/providers/bg_classifier/classifier.py`.
- [ ] Implement Step 1: color variance analysis (per-channel std dev on background sample pixels).
- [ ] Implement Step 2: gradient linearity test (least-squares fit `color = a·x + b·y + c` per channel, compute R²).
- [ ] Implement Step 3: texture periodicity test (2D FFT on grayscale ROI, detect dominant non-DC frequency peaks).
- [ ] Implement Step 4: default fallback to Type D.
- [ ] Output `BgClassifierResult` with `bg_type`, `confidence`, `dominant_color`, `gradient_params`, `texture_period_px`.
- [ ] Save `debug_bg_sample.png` artifact showing sampled region and classification decision.
- [ ] Add `bg_classifier:` config block to `config/config.yaml` with tunable thresholds.

### M3-B. Shared Poisson blend utility

- [ ] Create `app/providers/inpaint/poisson_blend.py`.
- [ ] Wrap `cv2.seamlessClone` with sensible defaults and error fallback.
- [ ] All subsequent paste-backs use this utility — no direct pixel copy.

### M3-C. SolidFillProvider (Type A)

- [ ] Create `app/providers/inpaint/solid_fill_provider.py`.
- [ ] Sample background color: weighted median of pixels in expanded ROI outside text mask.
- [ ] Fill masked region with sampled color.
- [ ] Apply Gaussian feather at mask boundary before Poisson blend.
- [ ] Benchmark: compare against current OpenCV Telea on flat-background test set.

### M3-D. GradientFillProvider (Type B)

- [ ] Create `app/providers/inpaint/gradient_fill_provider.py`.
- [ ] Create `app/providers/bg_classifier/gradient_fit.py`.
- [ ] Implement linear gradient fit: solve `color(x,y) = a·x + b·y + c` via `numpy.linalg.lstsq` per channel.
- [ ] Implement quadratic extension for radial gradients: `color(x,y) = a·x² + b·y² + c·x + d·y + e`.
- [ ] Select linear vs quadratic based on linear R² score (use quadratic if linear R² < 0.80).
- [ ] Fill masked region by evaluating fitted polynomial at each masked pixel coordinate.
- [ ] Apply Poisson blend on paste-back.
- [ ] Benchmark: compare against SolidFill on gradient-background test set.

### M3-E. PatchSynthesisProvider (Type C)

- [ ] Create `app/providers/inpaint/patch_synthesis_provider.py`.
- [ ] Implement patch search using `cv2.matchTemplate` (TM_SQDIFF_NORMED) on background region.
- [ ] Fill masked region with best-matching patch (handle boundary pixels first, working inward).
- [ ] Add Poisson blend on paste-back.
- [ ] Fallback: if patch search fails (insufficient background sample), fall back to OpenCV Telea.
- [ ] Benchmark: compare against OpenCV Telea on product-surface test set.

### M3-F. OpenCV Telea/NS provider (fast fallback)

- [ ] Move current Telea logic into `opencv_provider.py` (clean up legacy code).
- [ ] Support Telea and Navier-Stokes modes via config.
- [ ] Use as fallback within PatchSynthesisProvider and as the fast-mode Type C/D backend.

### Exit criteria

- [ ] `bg_classifier` correctly classifies at least 85% of benchmark ROIs by manual verification.
- [ ] SolidFillProvider produces clean results on all Type A benchmark cases.
- [ ] GradientFillProvider produces clean results on all Type B benchmark cases.
- [ ] PatchSynthesisProvider visibly outperforms OpenCV Telea on Type C benchmark cases.
- [ ] All providers use `poisson_blend.py` for paste-back.
- [ ] Classification result is recorded in `job_manifest.json` per ROI.

---

## M4. LaMa backend integration (Type D fallback only)

### Goal
Add model-based restoration as the fallback for Type D (complex scene) ROIs only.
LaMa is NOT the default medium-quality backend. It is invoked only when the bg_classifier returns Type D.

Expected invocation rate: ~5–10% of product image ROIs.

### Prerequisite gate: ADR-006 re-evaluation (mandatory before this milestone starts)

LaMa requires `torch`. Before starting M4:

- [ ] Measure actual Type D ROI rate on the benchmark set from M3.
  - If Type D rate < 10%: ADR-006 likely remains deferred. Document this.
  - If Type D rate > 25%: re-evaluate whether VRAM mutex is needed.
- [ ] Answer: Is single-process torch inference on RX 7900 XTX stable without a VRAM mutex?
- [ ] Answer: LaMa cold-start latency on target hardware — is 300s timeout still sufficient?
- [ ] Answer: Does LaMa + concurrent GPU workload (local LLM) cause OOM?

**Write answers as addendum in `docs/adr/ADR-006-async-and-vram-reserve.md` before M4 begins.**

### Tasks

- [ ] Complete ADR-006 re-evaluation gate above.
- [ ] Select LaMa integration mode: local PyTorch inference preferred; ONNX as alternative.
- [ ] Implement `lama_provider.py` with `InpaintProvider` interface.
- [ ] Crop-local processing: pad ROI to LaMa minimum input size, inpaint, crop result back.
- [ ] Normalize image/mask pre/post-processing (uint8, 0-255, RGB channel order).
- [ ] Add max crop size guard with fallback to PatchSynthesisProvider if ROI exceeds limit.
- [ ] Add timeout guard with fallback to PatchSynthesisProvider.
- [ ] Add provider healthcheck (model file present, torch available, test inference passes).
- [ ] Apply Poisson blend on paste-back (same as all other providers).
- [ ] Add LaMa to `requirements.txt` with explicit torch version pinning.
- [ ] Document model weight download in README (weights are not bundled in repo).

### Exit criteria

- [ ] ADR-006 re-evaluation documented.
- [ ] LaMa runs locally without ComfyUI.
- [ ] Type D benchmark cases show visible improvement over PatchSynthesis fallback.
- [ ] Fallback chain works: LaMa timeout → PatchSynthesis → SolidFill.
- [ ] Smoke test passes with LaMa provider active.

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
Wire the `bg_classifier` output into the inpaint backend selection. The router is a pure dispatch layer — it reads the classification result and calls the corresponding provider. No heuristics inside the router itself.

### Tasks

- [ ] Implement `app/core/router.py`.
- [ ] Router input: `BgClassifierResult` per ROI + runtime mode (`fast` / `balanced` / `quality`).
- [ ] Implement routing table:
  ```
  fast mode:
    Type A/B/C/D  ->  OpenCV Telea (no classifier needed, skip M3-A in fast mode)

  balanced mode:
    Type A        ->  SolidFillProvider
    Type B        ->  GradientFillProvider
    Type C        ->  PatchSynthesisProvider
    Type D        ->  LamaInpaintProvider

  quality mode:
    Type A/B/C    ->  same as balanced
    Type D        ->  LamaInpaintProvider -> DiffusersInpaintProvider (if LaMa score < threshold)
  ```
- [ ] Implement fallback chain in router:
  ```
  Any provider failure  ->  PatchSynthesisProvider  ->  SolidFillProvider
  Refine mask failure   ->  coarse polygon mask fallback
  ```
- [ ] Log selected backend and fallback reason per ROI in `job_manifest.json`.
- [ ] Add mode-aware routing configuration to `config.yaml`.

### Exit criteria

- [ ] Backend selection is deterministic, driven by classifier output, and fully traceable in manifest.
- [ ] Fallback chain is exercised in tests.
- [ ] No routing decisions are based on hardcoded heuristics outside the classifier.

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

### Sprint-0 (safety net before anything)
1. M0-B smoke test baseline
2. M0-A benchmark set (30+ samples)
3. M0-C legacy script inventory

### Sprint-1 (De-Comfy + deterministic backends)
4. M1 remove ComfyUI from production path + legacy script cleanup
5. M2 provider abstraction
6. M3 background classifier + deterministic inpaint backends (SolidFill, GradientFill, PatchSynthesis, Poisson blend)
7. M5 refine mask pipeline v1

**Sprint-1 delivers a fully working product-image pipeline with no ML model dependency.**
**For ~90% of product image ROIs, this is the complete solution.**

### Sprint-2 (model fallback + routing + layout)
8. M8 router (wire bg_classifier to provider selection)
9. M4 LaMa integration (Type D fallback, after ADR-006 gate)
10. M7 layout planner v1
11. M9 QA hardening

### Later / gated
12. M6 detector upgrade
13. M10 API/docs refresh
14. M11 Diffusers premium backend

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

### Rule 6
No M1 code work begins until M0-B smoke test is passing. This is not optional.

### Rule 7
ADR-006 re-evaluation must be documented before M4 (LaMa) begins. Introducing `torch` as a dependency without this evaluation is a scope violation.

### Rule 8
The v1.1 task list (`Local_Image_Translation_Task_List_v1_1.md`) milestone names M1–M4 are retired. Do not use them in status updates, PRs, or commit messages. Use v3 milestone numbers (M0–M11) exclusively.

---

## 7. Sprint plan

### Sprint-0 target (prerequisite — must complete before Sprint-1)

- [ ] M0-B: write and pass smoke test (`tests/test_smoke.py`)
- [ ] M0-C: document legacy script inventory
- [ ] M0-A: verify/expand benchmark set to 30+ samples

Expected duration: 1–2 days. No new features. No refactoring.
Sprint-0 exits only when smoke test is committed and green.

---

### Sprint-1 target (starts only after Sprint-0 exits)

- [ ] M1: de-Comfy refactor + legacy script cleanup
- [ ] M2: provider abstraction
- [ ] M3-A: background zone classifier
- [ ] M3-B: Poisson blend utility
- [ ] M3-C: SolidFillProvider (Type A)
- [ ] M3-D: GradientFillProvider (Type B)
- [ ] M3-E: PatchSynthesisProvider (Type C)
- [ ] M3-F: OpenCV Telea cleanup (fast fallback)
- [ ] M5-A/M5-B/M5-C: refine mask prototype

### Sprint-1 expected demo

For a fixed product image benchmark subset:

- current baseline output (from Sprint-0 archive)
- bg_classifier output per ROI (type label + debug sample)
- new refine mask overlays
- SolidFill / GradientFill / PatchSynthesis outputs per ROI type
- no ComfyUI runtime dependency, no LaMa/torch
- smoke test passing throughout

**Sprint-1 demo should show that Type A and B cases look better than the ComfyUI baseline.**

---

### Sprint-2 target (after Sprint-1 exits)

- [ ] M5-D/M5-E/M5-F: refine mask pipeline completion
- [ ] M8: router (wire bg_classifier → provider)
- [ ] M4 gate: ADR-006 re-evaluation + Type D rate measurement on benchmark
- [ ] M4: LaMa integration (only if gate passes)
- [ ] M7: layout planner v1

---

## 8. Definition of Done (v3 baseline release)

A v3 baseline release is done when:

- [ ] Default runtime path requires no ComfyUI.
- [ ] OpenCV and LaMa providers are both available and health-checked.
- [ ] Refine-mask v1 is implemented with saved debug artifacts.
- [ ] Benchmark package compares new outputs against old baseline (Sprint-0 archive).
- [ ] `/process` produces final image + manifest + QA report.
- [ ] README/docs reflect actual runtime architecture (v3, not v1.1).
- [ ] At least one automated smoke test is passing in `tests/`.
- [ ] Legacy root-level scripts are moved to `scripts/legacy/`.
- [ ] ADR-006 re-evaluation is documented.
- [ ] All milestone ADR candidates (ADR-008 to ADR-014) have corresponding files in `docs/adr/`.

---

## 9. Final note

The project should now be framed as a **mask-first, backend-pluggable image text replacement engine**, not as a ComfyUI workflow project. That framing is the key to preventing future engineering drift.

The single most common failure mode in similar projects is starting structural refactors without automated tests. Sprint-0 exists specifically to close that gap before anything else moves.
