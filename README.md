# Dishmook — دیشموک

An open-source research lab for testing whether structured multi-agent workflows improve scientific answers under a fixed compute budget.

**Current implementation: Phase 0 only.** The Fake Backend is a deterministic infrastructure fixture, not an LLM or scientific solver. No model weights, API keys, paid services, GPU, web UI, scheduler or generated-code executor are used.

## شروع سریع

با Python `3.12.14`، در Windows یا Linux:

```sh
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Linux:

```sh
source .venv/bin/activate
```

سپس:

```sh
python -m pip install -e ".[dev]"
python -m pytest
python -m dishmook smoke --seed 42
python -m dishmook schema claim
```

The installed `dishmook` command provides the same CLI. Installation downloads dependencies; tests and smoke execution work offline after installation. The GitHub runner itself still requires network access for checkout and installation.

## حدود فاز صفر

- قراردادهای `Problem`, `Agent`, `Task`, `Claim`, `Evidence`, `Run` با Pydantic.
- مدل آزمایشی تکرارپذیر با خروجی `unverified` و هزینهٔ صفر.
- CLI برای تست اولیه و خروجی JSON Schema.
- تست CPU روی Windows و Linux؛ تست‌ها اتصال شبکهٔ Python را مسدود می‌کنند.
- ثبت وضعیت علمی در Schema، به‌تنهایی اثبات درستی ادعا نیست.

هدف ۵۰ ایجنت منطقی و اجرای مدل مشترک، مربوط به مراحل بعد است. پایان فاز صفر نیازمند موفقیت CI است و به معنی آماده‌بودن MVP نیست.

See [the complete Persian specification](Dishmook_Project_Spec_FA.md), [Phase 0 scope](docs/PHASE_0.md), [architecture](docs/ARCHITECTURE.md), [security](docs/SECURITY.md), [reproducibility](docs/REPRODUCIBILITY.md), [scientific validation](docs/SCIENTIFIC_VALIDATION.md), and [free compute](docs/FREE_COMPUTE.md).
