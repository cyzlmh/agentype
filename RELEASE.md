# Release Checklist

Agentype should ship through two channels: a public GitHub repository and agent skill marketplaces.

## GitHub Release

- Use `cyzlmh/agentype` as the GitHub repository.
- Keep the repository private until the flattened release history is reviewed.
- Use the MIT license.
- Publish to PyPI so users without `uv` can install with `pipx install agentype-cli` or `pip install agentype-cli`.
- Verify the package metadata in `pyproject.toml`: description, authors, Python version, dependencies, and script entrypoint.
- Run:

```bash
uv sync
uv run pytest
uv run agentype
uv build
```

- Confirm generated artifacts stay out of Git: `output/`, `.env`, caches, and local session data.
- Confirm local-only planning files stay out of Git: `ROADMAP.md`, `.claude/`, and machine-specific environment files.
- Do not make an existing repository public until Git history is sanitized. Prefer a fresh private GitHub repository or an orphan public-release branch with only the cleaned tree.
- Include README sections covering supported agents, privacy, install, usage, and platform support.
- Require CI to pass on macOS, Linux, and Windows before the first public release.

## PyPI Release

- Publish under `agentype-cli`; the `agentype` PyPI name is already used by an unrelated package.
- Add final package metadata before publishing: license, repository URL, homepage URL, and issue tracker URL.
- Configure a pending PyPI Trusted Publisher for:
  - Owner: `cyzlmh`
  - Repository: `agentype`
  - Workflow: `publish.yml`
  - Environment: `pypi`
- Build locally with:

```bash
uv build
```

- Publish after credentials are configured:

```bash
gh release create v0.1.0 --draft --title "v0.1.0" --notes "Initial alpha release"
```

- Verify a clean user install:

```bash
pipx install agentype-cli
agentype --help
```

## Skill Marketplace Release

- Use `SKILL.md` as the canonical skill entrypoint.
- Keep the skill description focused on user intent: token footprint, usage trends, preferred agents/models/projects, domains, and persona archetype.
- Package for skills.sh and clawhub.ai after their required metadata is known.
- Validate that an agent can invoke Agentype from both:

```bash
uv run agentype
agentype
```

- Validate the skill loop:

```bash
agentype --json-out
agentype --json-in output/agentype.json --png-out
```

- For shell-oriented agents, print the terminal summary.
- For chat or IM-oriented agents, summarize the terminal output and attach `output/agentype.png`.

## First Public Release Scope

Required:

- local-only data collection
- single-command terminal overview
- verbose debug mode
- JSON export
- JSON import for agent-filled persona rendering
- PNG export for share-oriented agents
- README install flow
- skill invocation guide

Planned before broader promotion:

- marketplace metadata for skills.sh and clawhub.ai
- stronger domain evidence after the analysis research track
