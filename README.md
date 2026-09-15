# Dishmook — دیشموک

An open-source research lab for testing whether structured multi-agent workflows improve scientific answers under a fixed compute budget.

**Current implementation: campaign and evaluation infrastructure (phases 2–5).** Includes 50 logical roles, bounded scheduling, persistent model workers, resumable checkpoints, local Hugging Face/NF4 support, and Kaggle notebooks. GPU model selection and scientific acceptance remain pending. There is no generated-code executor or paid inference client. See [current status](docs/PHASES_2_TO_6.md).

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

## Campaigns and Kaggle

```sh
python -m dishmook campaign --spec configs/campaign_50.json --campaign-id fifty --max-tasks 13
python -m dishmook campaign-resume fifty
python -m dishmook evaluate --output-dir runs/comparison
```

These defaults use Fake Backend and establish no scientific accuracy. Offline validation completed 216 campaigns / 3,168 tasks with zero failures; [evidence](reports/offline_validation/summary.json).

برای اتصال Kaggle به پروژه، [Notebook انتخاب مدل](notebooks/kaggle_model_selection.ipynb) را وارد Kaggle کن و در سلول نخست `SOURCE_REVISION` را برابر SHA کامل همین نسخهٔ کد قرار بده. پس از انتخاب مبتنی بر شواهد، [Notebook مقایسهٔ ایجنت‌ها](notebooks/kaggle_campaign.ipynb) را اجرا کن. راه جایگزین، افزودن آرشیو کد با مسیر مشخص‌شده در Notebook است. این Notebookها هنوز روی Kaggle اجرا نشده‌اند؛ گزارش تصویری شما از اجرای T4 جداگانه ثبت شده است.

انتخاب مدل و اثبات بهبود علمی هنوز انجام نشده؛ فاز ۶ به نتایج واقعی فاز ۵ وابسته است.

See [Phase 1 guide](docs/PHASE_1.md), [Persian specification](Dishmook_Project_Spec_FA.md), [architecture](docs/ARCHITECTURE.md), [security](docs/SECURITY.md), [reproducibility](docs/REPRODUCIBILITY.md), [scientific validation](docs/SCIENTIFIC_VALIDATION.md), and [free compute](docs/FREE_COMPUTE.md).
