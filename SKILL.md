---
name: agentype
description: Analyze local AI-agent usage across Claude Code, Codex, OpenCode, pi-agent, Gemini CLI, OpenClaw, Nanobot, and configured Nanobot-compatible roots to produce a token overview, trends, preferences, and skill signals. The triggering agent should infer a persona from the deterministic output. Use when the user asks to understand their agent usage, AI workflow, token footprint, preferred agents/models/projects, or "agentype".
version: 0.1.0
tags: [ai-agents, analytics, persona, tokens, local-first]
---

# Agentype

Agentype summarizes a user's local AI-agent history into one deterministic usage overview. Persona discovery is performed by the triggering agent using its own LLM — Agentype itself makes no LLM calls by default.

## When to Use

Use this skill when the user asks:

- "what is my agentype?"
- "analyze my agent usage"
- "show my AI usage stats"
- "which agents or models do I use most?"
- "what persona am I based on my AI workflow?"
- `/agentype`

Do not use it for billing estimates. Agentype reports tokens and local usage signals, not provider invoices.

## What It Reads

Agentype collects local session and token metadata from supported agents where available:

- Claude Code
- Codex
- OpenCode
- pi-agent
- Gemini CLI
- OpenClaw
- Nanobot
- Nanobot-compatible JSONL roots configured through `AGENTYPE_NANOBOT_ROOTS`

Agentype is fully local and makes no network requests by default. It reads agent history from disk and prints a terminal summary. The BYOK `--llm-*` options are available for users who want Agentype to call an LLM directly, but the skill should prefer the default deterministic path and handle persona inference on the agent side.

## Run

If Agentype is installed:

```bash
agentype
```

If working from a source checkout:

```bash
uv run agentype
```

For users without `uv`, prefer installing the published CLI:

```bash
pipx install agentype-cli
agentype
```

## Custom Local Paths

If a user's agent history lives outside the default locations, ask for the relevant root and configure it before running Agentype. Nanobot-compatible JSONL roots can be added with `AGENTYPE_NANOBOT_ROOTS`:

```bash
AGENTYPE_NANOBOT_ROOTS="/path/to/workspace:/path/to/another/root" agentype --json-out
```

For unsupported agent layouts, tell the user the collector paths live in `src/agentype/paths.py` and source adapters live in `src/agentype/sources/`, so they can add their own local path or adapter before publishing private stats.

## Output Modes

- Default: poster-style terminal overview with AGENTYPE/persona first, then token usage, breakdowns, and trends. No LLM calls by default.
- `-v`: adds detailed tables for statistics, discovered themes, and data confidence.
- `--json-out`: writes `output/agentype.json` with the full analysis.
- `--json-in PATH`: renders a previously written Agentype JSON file. Use this after filling top-level persona fields.
- `--png-out`: writes `output/agentype.png`, a shareable poster-style summary for chat or IM environments.
- `--llm-base-url URL --llm-api-key KEY --llm-model MODEL`: opt into LLM persona discovery (BYOK, OpenAI-compatible API). Flags or env vars (`AGENTYPE_LLM_BASE_URL`, `AGENTYPE_LLM_API_KEY`, `AGENTYPE_LLM_MODEL`).

## Agent Instructions

When the user invokes this skill:

1. Run `agentype --json-out` (or `uv run agentype --json-out` from a source checkout) to collect deterministic local usage into `output/agentype.json`.
2. Read `output/agentype.json`.
3. Using your own LLM when needed, infer a persona from the aggregate signals: top projects, agents, models, skill metadata, and usage patterns. Fill these top-level JSON fields: `archetype`, `description`, `keywords`, and `comment`. Keep the comment to 2-3 concise evidence-grounded sentences starting with "You are a...".
4. Run `agentype --json-in output/agentype.json --png-out` (or `uv run agentype --json-in output/agentype.json --png-out`) to render the final terminal result and shareable PNG from the filled JSON.
5. Relay the persona and top usage stats to the user in a compact summary. Attach `output/agentype.png` when the environment supports files or images.
6. If the user asks for debugging or validation, rerun as `agentype -v --json-out` or `uv run agentype -v --json-out`.
7. Do not expose raw session files, prompts, or private transcripts.
8. In chat or IM environments, summarize the terminal result compactly and prefer the PNG for share-oriented requests.
