# Agentype

Agentype analyzes your local AI-agent usage and turns it into a private terminal overview.

It is for people who work across multiple agents and want one summary of their token footprint, usage rhythm, top projects, and preferred agents/models. With an opt-in LLM, it also uses project and skill context to infer a persona comment, keywords, and an archetype.

## Supported Agents

Agentype currently reads local history from:

- Claude Code
- Codex
- OpenCode
- pi-agent
- Gemini CLI
- OpenClaw
- Nanobot
- Nanobot-compatible JSONL roots configured through `AGENTYPE_NANOBOT_ROOTS`

Availability depends on what each agent stores locally. Some agents provide richer token or tool metadata than others.

For Nanobot-compatible deployments outside the default `~/.nanobot/sessions` path, set one or more roots with your platform path separator:

```bash
AGENTYPE_NANOBOT_ROOTS="/path/to/app:/path/to/another/app" agentype
```

## Install

The PyPI distribution is `agentype-cli` because `agentype` is not available on PyPI. The installed command is still `agentype`.

The recommended CLI install is:

```bash
pipx install agentype-cli
agentype
```

If you do not use `pipx`, a regular pip install should also work:

```bash
pip install agentype-cli
agentype
```

For one-off runs without installing the command permanently:

```bash
uvx --from agentype-cli agentype
```

For source checkout development:

```bash
git clone https://github.com/cyzlmh/agentype.git
cd agentype
uv sync
uv run agentype
```

## Usage

```bash
agentype
agentype -v
agentype --json-out
agentype --json-in output/agentype.json
agentype --png-out
agentype --output output --json-out --png-out
agentype --llm-base-url https://api.openai.com/v1 --llm-api-key sk-... --llm-model gpt-4o
```

- `agentype` prints the main terminal overview.
- `agentype -v` adds detailed statistics, discovered theme tables, and data confidence.
- `agentype --json-out` writes `output/agentype.json`.
- `agentype --json-in PATH` renders a previously written Agentype JSON file. This is meant for skill workflows where the triggering agent fills top-level persona fields before asking the CLI to print or render the final result.
- `agentype --png-out` writes `output/agentype.png`, a shareable poster-style summary.
- `--output DIR` changes where JSON and PNG artifacts are written.
- `--llm-base-url URL --llm-api-key KEY --llm-model MODEL`: opt into LLM persona discovery (BYOK, OpenAI-compatible API). All three are required; any can also be set via `AGENTYPE_LLM_BASE_URL`, `AGENTYPE_LLM_API_KEY`, `AGENTYPE_LLM_MODEL`.

## What It Shows

- Persona poster: AGENTYPE and the LLM-inferred persona first, or a usage snapshot when no LLM is configured.
- Token usage: total, non-cache, cache, input, output, and reasoning tokens where available.
- Breakdowns: top projects, agents, and model IDs.
- Usage rhythm: monthly and weekly trend bars.
- Without LLM configuration, only the statistics overview is shown.
- When `--llm-*` options are provided (or the equivalent env vars), a persona comment, keywords, and an archetype inferred by the configured LLM from top project docs and skill metadata.

Agentype reports tokens, not cost. Pricing varies by provider, subscription, and plan, so cost estimates are intentionally excluded.

## Privacy

Agentype is fully local by default. It reads known agent history locations on your machine and makes no network requests. If `--llm-*` options are provided, Agentype sends a compact usage summary (last-30-day token total, used agents, and used models), skill descriptions/categories/usage counts/canonical paths, and bounded top-project `README.md`, `AGENTS.md`, or `CLAUDE.md` text to the configured LLM provider. Raw prompts, transcripts, and detailed per-project/per-agent statistics are never uploaded in any mode.

## Platform Support

Agentype targets macOS, Linux, and Windows. Release builds are checked with cross-platform CI.

Adapter coverage still depends on where each agent stores local history. Some agents may use different paths or formats across platforms.

If an agent stores its history somewhere different on your machine, Agentype may simply show less data instead of failing.

## Agent Skill Usage

Agentype can also be packaged as an agent skill for marketplaces such as skills.sh and clawhub.ai. When triggered by an agent, it should run a workflow instead of stopping at the first statistics output.

Marketplace links:

- skills.sh: https://skills.sh/cyzlmh/agentype/agentype
- ClawHub: https://clawhub.ai/cyzlmh/agentype

Install from skills.sh:

```bash
npx skills add cyzlmh/agentype --skill agentype
```

Install from ClawHub:

```bash
npx clawhub@latest install agentype
```

Required skill loop:

```bash
agentype --json-out
```

The agent then reads the cached JSON at `output/agentype.json`, infers the persona/archetype from aggregate usage signals, and fills these top-level fields:

- `archetype`
- `description`
- `keywords`
- `comment`

After the JSON is filled, render the final result:

```bash
agentype --json-in output/agentype.json
```

For chat or IM gateway environments that can display images, also render the poster:

```bash
agentype --json-in output/agentype.json --png-out
```

Shell-oriented agents should return the rendered terminal summary. Chat or IM-oriented agents should send a compact summary and attach `output/agentype.png` when supported.

For nonstandard local agent history paths, configure available environment variables first. Nanobot-compatible roots use `AGENTYPE_NANOBOT_ROOTS`; unsupported layouts can be added in `src/agentype/paths.py` or a source adapter under `src/agentype/sources/`.
