# Repository Guidelines

## Project Structure & Module Organization

Agentype is a Python CLI package under `src/agentype/`. The command entry point is `src/agentype/__init__.py`, wired through `pyproject.toml` as `agentype = "agentype:main"`. Data collection lives in `collector.py`; per-agent adapters live in `src/agentype/sources/` for Claude Code, Codex, OpenCode, pi-agent, Gemini CLI, OpenClaw, Nanobot, and configured Nanobot-compatible roots. Statistics, domain scoring, and archetype selection live in `analysis.py`.

Project documentation is in `README.md`, `SKILL.md`, and `RELEASE.md`. `ROADMAP.md` is a local planning file and is intentionally ignored. Tests are in `tests/`. Runtime artifacts are written to `output/` and are intentionally ignored.

## Build, Test, and Development Commands

Use `uv` for dependency management and command execution.

- `uv sync` installs dependencies from `uv.lock`.
- `uv run pytest` runs the parser and token usage test suite.
- `uv run agentype` prints the end-user usage overview and archetype.
- `uv run agentype -v` adds intermediate statistics, domain evidence, and data confidence tables.
- `uv run agentype --json-out` writes the full analysis to `output/agentype.json`.
- `uv build` builds the package using `uv_build`.

If you add developer tools such as ruff or mypy, declare them in `pyproject.toml` and run them through `uv run`.

## Coding Style & Naming Conventions

Write idiomatic Python 3.12 with 4-space indentation and type hints for public functions or non-obvious data shapes. Use `snake_case` for functions, variables, and modules; use `PascalCase` for dataclasses such as `SkillInfo`, `SessionEvent`, and `TokenUsage`.

Keep modules focused on their existing responsibilities. Prefer small functions over new abstractions unless the abstraction removes repeated logic. Match the current style: standard-library imports first, third-party imports next, then local imports.

## Testing Guidelines

Use `pytest` and place test files under `tests/` with names like `test_sources.py`, `test_token_usage.py`, or `test_analysis.py`. Prefer fixture files or small inline JSON/SQLite samples over reading real local agent history. Focus on deterministic logic: transcript parsing, token usage summarization, statistics, domain scoring, and archetype selection. Avoid tests that require live LLM calls; mock `agentype.llm.chat` instead.

Run the suite with:

```bash
uv run pytest
```

## Commit & Pull Request Guidelines

The current history uses short, imperative commit messages, for example `Initial commit` and `Add multi-agent data collection`. Continue that style: `Add analyzer feature extraction`, `Document token summary limits`.

Pull requests should include a concise description, the commands run for verification, and example shell output when CLI presentation changes. Link related issues or roadmap items when applicable.

## Security & Configuration Tips

Do not commit `.env` files, API keys, generated output, or real local agent session data. The collectors read known agent directories under the user home directory; keep fixtures synthetic and anonymized.
