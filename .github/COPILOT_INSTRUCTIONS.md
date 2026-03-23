# Copilot Instructions

Repository-wide engineering standards for all AI-assisted changes.

## Scope
- Applies to Python code, tests, docs, and config in this repository.
- Audience: Developers, Copilot/ChatGPT/Cursor/agents.

## Core Principles
- Prioritize readability, maintainability, and clarity.
- Keep functions small and focused; apply SOLID where OO is used.
- Prefer explicit behavior and explicit errors over implicit magic.
- Avoid exceptions for control flow.
- Comment on non-obvious design decisions.

## Python Standards
- Use Python 3.13+ and type hints everywhere.
- Follow PEP 8 and PEP 257.
- Use Google-style docstrings on modules, classes, and functions.
- Use the `typing` module for annotations.

## Tooling and Formatting
- Use `uv` for env and dependency management.
- Format with `black` (line length 88).
- Sort imports with `isort`.
- Lint with `ruff` and `flake8`.
- Type check with `mypy`.

## Error Handling and Logging
- Use specific exception types, not broad `except Exception`.
- Provide informative error messages when raising.
- Use `logger.exception()` when logging errors.
- Avoid swallowing exceptions unless explicitly justified.

## Testing Standards
- Use `pytest` only. Do not use `unittest`.
- Unit tests live in `tests/unit`. BDD tests live in `tests/bdd`.
- Cover nominal, negative, edge, and regression cases.
- Avoid network calls in tests; mock or monkeypatch external I/O.
- For floats, use `pytest.approx()` or `math.isclose()`.
- Create a brief test plan for non-trivial changes.

## Documentation Standards
- Update docs when behavior changes.
- Keep examples minimal and accurate.

## Dependency and CI Rules
- Declare deps in `pyproject.toml`.
- Prefer pinned versions for reproducibility.
- CI must run linting, tests, and type checks; do not merge on failures.

## Security and Compliance
- Run `bandit` and `safety` when adding security-sensitive code.
- Add license headers to new files if required by repo license.

## Performance
- Profile performance-critical changes and document results.

## Accessibility and i18n
- Ensure accessibility for user-facing components.
- Prepare for i18n/l10n where relevant.

## Example Guidance (Short)
- Use `pytest` fixtures for setup.
- Keep tests deterministic and fast.
