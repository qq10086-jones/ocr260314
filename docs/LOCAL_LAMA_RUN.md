# Local LaMa Run Notes

## What changed

- LaMa model/cache downloads now default to `./.model_cache/lama/`
- The provider no longer depends on the user's global `~/.cache`
- This makes local testing on locked-down machines much more reliable

## One-image smoke run

```powershell
python scripts/run_local_inpaint.py --image test_photo/test_1.jpg --mode smart
```

## Batch smoke run

```powershell
python scripts/run_local_inpaint.py --input-dir test_photo --mode smart
```

## Output location

By default outputs are written under:

```text
manual_runs/local_inpaint/runs/<date>/job_xxx/
```

Each job folder contains:

- `result.png`
- `clean_bg.png`
- `mask.png`
- `logs.txt`

## Dependencies

The base repo requirements do not install LaMa automatically.

At minimum, the target machine needs:

- `torch`
- `simple_lama_inpainting`

Whether LaMa uses GPU or CPU depends on the local `torch` build.
This repo version is designed to run even when GPU acceleration is unavailable.
