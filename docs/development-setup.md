# BLAZZID AI Studio — Development Setup & Quality Gates

## 1. Prerequisites

- **Python:** Python 3.9+ (Tested on Python 3.9.13 and Python 3.12).
- **Virtual Environment:** Python standard library `venv`.
- **System Tooling (Optional for Media Fixtures):** `ffmpeg` and `ffprobe` (version 7.x or 8.x).

---

## 2. Quickstart Environment Setup

From the repository root:

```bash
# 1. Create a clean virtual environment
python3 -m venv .venv

# 2. Activate virtual environment
source .venv/bin/activate

# 3. Upgrade pip and install development dependencies
pip install --upgrade pip
pip install -e packages/core -e packages/algorithms
pip install -r pyproject.toml --extra dev || pip install "pytest>=8.0.0" "hypothesis>=6.98.0" "pytest-benchmark>=4.0.0" "ruff>=0.3.0" "mypy>=1.9.0"
```

---

## 3. Quality Gate Commands

All quality gate commands are designed to run deterministically from the repository root:

### Code Formatting & Linting (Ruff)
```bash
# Check lint rules
.venv/bin/ruff check .

# Format code
.venv/bin/ruff format .

# Check formatting without modifying files
.venv/bin/ruff format --check .
```

### Strict Type Checking (Mypy)
```bash
.venv/bin/mypy packages/core/src packages/algorithms/src tests benchmarks
```

### Unit & Property Test Suites (Pytest + Hypothesis)
```bash
.venv/bin/pytest -v tests
```

### Repeatable Performance Benchmarks (pytest-benchmark)
```bash
.venv/bin/pytest -v benchmarks
```

### Run All Gates Sequentially
```bash
.venv/bin/ruff format --check . && \
.venv/bin/ruff check . && \
.venv/bin/mypy packages/core/src packages/algorithms/src tests benchmarks && \
.venv/bin/pytest -v tests
```
