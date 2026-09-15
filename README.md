# Dishmook — دیشموک

An open-source research lab for testing whether structured multi-agent workflows improve scientific answers under a fixed compute budget.

**Current implementation: Phase 1, single-agent runtime.** Run one problem using a Fake Backend or an already downloaded local Hugging Face model. Results remain scientifically **unverified**. No paid API, model download, multi-agent scheduler or generated-code executor exists.

## نصب

Python `3.12.10` on Windows; `3.12.14` on Linux:

```sh
python -m venv .venv
```

Activate `.venv` using the standard command for your shell, then:

```sh
python -m pip install -e ".[dev]"
python -m pytest
```

Installation downloads dependencies; runtime and tests work offline afterwards. Windows/Linux CI tests the base runtime. A separate CPU CI job tests Transformers using tiny weights generated inside the test.

## اجرای فاز یک

```sh
python -m dishmook run --spec problems/examples/free_fall.json --run-id first-run
python -m dishmook resume first-run
```

نمونهٔ پیش‌فرض از مدل آزمایشی استفاده می‌کند؛ پاسخ علمی تولید نمی‌کند. دستور دوم، اجرای کامل‌شده را دوباره به مدل نمی‌فرستد. نتایج در `runs/first-run/` ثبت می‌شوند.

برای آماده‌سازی و اجرای بعدی:

```sh
python -m dishmook run --spec problems/examples/free_fall.json --run-id second-run --prepare-only
python -m dishmook resume second-run
```

Use a new run ID for each experiment. Existing IDs are never overwritten. Omit `--run-id` for a UUID. `--runs-dir` selects a trusted local output directory. Resume cannot change the saved model, seed or budget. The original `smoke` and `schema claim` commands remain available.

هدف ۵۰ ایجنت منطقی، انتخاب مدل 7B–8B و آزمایش Kaggle متعلق به مراحل بعد است. این نسخه به معنی تکمیل MVP نیست.

See [Phase 1 guide](docs/PHASE_1.md), [Persian specification](Dishmook_Project_Spec_FA.md), [architecture](docs/ARCHITECTURE.md), [security](docs/SECURITY.md), [reproducibility](docs/REPRODUCIBILITY.md), [scientific validation](docs/SCIENTIFIC_VALIDATION.md), and [free compute](docs/FREE_COMPUTE.md).
