# Legacy Scripts

These scripts are the pre-migration reference implementation (pre-M1).
They are retained for historical reference only and must not be modified or extended.

All functionality has been migrated to `app/`.

| Script | Original role | Current equivalent |
|--------|--------------|-------------------|
| step1_test.py | OCR validation entry | `app/providers/ocr/rapidocr_provider.py` |
| step2_erase.py | Mask + OpenCV inpaint | `app/providers/inpaint/opencv_provider.py` |
| step3_universal_v1.1.py | Full pipeline + ComfyUI | `app/core/engine.py` |
| test_v3.py | V3 mask flow test | `tests/test_smoke.py` |
| test_v4.py | V4 GrabCut test | `tests/test_smoke.py` |
| capture_baseline.py | Benchmark capture tool | `runs/benchmark_baseline_v3/` |
| run_test.py | General test runner | `pytest tests/` |
| convert_test.py | Image format conversion test | — |
