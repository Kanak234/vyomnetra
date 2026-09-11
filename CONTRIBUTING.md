# Contributing to VYOMNETRA

Thank you for contributing to VYOMNETRA (Space Situational Awareness Platform)!

## Development Guidelines

### Prerequisites
- Python 3.12+
- `uv` package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- System OpenGL/Qt libraries (see `.github/workflows/ci.yml`)

### Local Verification Workflow

Before submitting a pull request, run all checks locally:

1. **Install dependencies:**
   ```bash
   uv sync --extra dev
   ```

2. **Verify data ingestion:**
   ```bash
   uv run python scripts/verify_ingest.py
   ```

3. **Run test suite & coverage (>=80% enforced):**
   ```bash
   uv run pytest --verbose --cov=vyomnetra --cov-fail-under=80
   ```

4. **Verify container build:**
   ```bash
   docker build -t vyomnetra-ssa:local .
   ```

## Pull Request Guidelines
- Create a feature or hardening branch.
- Ensure all CI gates, CodeQL checks, and coverage targets pass before review.
