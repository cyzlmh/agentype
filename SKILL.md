---
name: agentype
description: >-
  Run the Agentype workflow for local AI-agent usage analysis: collect and cache deterministic JSON, infer a persona/archetype from aggregate usage signals, then render a terminal summary or PNG poster. Supports Claude Code, Codex, OpenCode, pi-agent, Gemini CLI, OpenClaw, Nanobot, and configured Nanobot-compatible roots. Use when the user asks to understand their agent usage, AI workflow, token footprint, preferred agents/models/projects, or "agentype".
version: 0.1.6
tags: [ai-agents, analytics, persona, tokens, local-first]
---

# Agentype

Agentype summarizes a user's local AI-agent history into one deterministic usage overview. In skill mode, the triggering agent must run a short workflow: collect and cache JSON, infer the persona/archetype from that JSON, then render the final text or image poster.

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

Agentype is fully local in this skill workflow. It reads agent history from disk and prints a terminal summary. Handle persona inference on the agent side rather than asking the CLI to contact external model services.

## Required Skill Workflow

When this skill is triggered by an agent, do the full loop below. The first CLI output is only the raw deterministic stats view; it is not the final user-facing Agentype result.

The PyPI distribution is `agentype-cli` because `agentype` is not available on PyPI. The installed command is still `agentype`.

1. Collect and cache the deterministic analysis:

   ```bash
   agentype --json-out
   ```

   If `agentype` is not installed and there is no source checkout, run the published CLI directly:

   ```bash
   uvx --from agentype-cli agentype --json-out
   ```

   From a source checkout, use:

   ```bash
   uv run agentype --json-out
   ```

2. Read the cached JSON at `output/agentype.json`.
3. Infer the user's persona from aggregate signals in the JSON: top projects, agents, models, skill metadata, token shape, and usage rhythm.
4. Fill these top-level JSON fields in `output/agentype.json`, preserving all other fields:
   - `archetype`: short persona label.
   - `description`: one-line explanation of the archetype.
   - `keywords`: 3-6 concise keywords.
   - `comment`: 2-3 evidence-grounded sentences starting with "You are a...".
5. Render the filled JSON:

   ```bash
   agentype --json-in output/agentype.json
   ```

   For chat, IM, or gateway environments that can display images, also create the poster image:

   ```bash
   agentype --json-in output/agentype.json --png-out
   ```

6. Final response:
   - Terminal agents: relay the rendered text summary with the persona/archetype and top stats.
   - Chat or IM gateway agents: send a compact text summary and attach `output/agentype.png` when supported.
7. Do not expose raw session files, prompts, private transcripts, or full JSON unless the user explicitly asks for debugging data.

## Run

For manual CLI use outside the agent workflow, if Agentype is installed:

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

- Default: terminal overview with AGENTYPE/persona first when persona fields exist, otherwise deterministic token usage, breakdowns, and trends. No LLM calls by default.
- `-v`: adds detailed tables for statistics, discovered themes, and data confidence.
- `--json-out`: writes `output/agentype.json` with the full analysis.
- `--json-in PATH`: renders a previously written Agentype JSON file. Use this after filling top-level persona fields.
- `--png-out`: writes `output/agentype.png`, a shareable poster-style summary for chat or IM environments.

## Debugging

If the user asks for debugging or validation, rerun collection as:

```bash
agentype -v --json-out
```

From a source checkout:

```bash
uv run agentype -v --json-out
```
