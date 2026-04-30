import json
import sqlite3
from pathlib import Path

from agentype.collector import summarize_token_usage
from agentype.sources.base import TokenUsage
from agentype.sources.claude import iter_token_usage as iter_claude_token_usage
from agentype.sources.codex import iter_token_usage as iter_codex_token_usage
from agentype.sources.nanobot_compat import iter_token_usage as iter_nanobot_compat_token_usage
from agentype.sources.gemini import iter_token_usage as iter_gemini_token_usage
from agentype.sources.nanobot import iter_token_usage as iter_nanobot_token_usage
from agentype.sources.opencode import iter_token_usage as iter_opencode_token_usage
from agentype.sources.openclaw import iter_token_usage as iter_openclaw_token_usage
from agentype.sources.pi import iter_token_usage as iter_pi_token_usage


def test_claude_token_usage_reads_native_usage(tmp_path: Path) -> None:
    session = tmp_path / "project-a" / "session.jsonl"
    session.parent.mkdir()
    session.write_text(
        '{"sessionId":"s1","cwd":"/repo/project-a","timestamp":"2026-04-30T01:00:00Z",'
        '"message":{"role":"assistant","model":"claude-sonnet","usage":{'
        '"input_tokens":100,"output_tokens":20,"cache_read_input_tokens":300,'
        '"cache_creation_input_tokens":40}}}'
    )

    usage = list(iter_claude_token_usage(tmp_path))

    assert len(usage) == 1
    assert usage[0].provider == "claude"
    assert usage[0].session_id == "s1"
    assert usage[0].project_dir == "/repo/project-a"
    assert usage[0].model == "claude-sonnet"
    assert usage[0].non_cache_tokens == 120
    assert usage[0].cache_tokens == 340
    assert usage[0].tokens_with_cache == 460


def test_codex_token_usage_uses_last_token_usage(tmp_path: Path) -> None:
    session = tmp_path / "sessions" / "2026" / "04" / "30" / "rollout.jsonl"
    session.parent.mkdir(parents=True)
    session.write_text(
        "\n".join(
            [
                '{"timestamp":"2026-04-30T01:00:00Z","type":"session_meta",'
                '"payload":{"id":"c1","cwd":"/repo/agentype"}}',
                '{"timestamp":"2026-04-30T01:01:00Z","type":"event_msg","payload":{"type":"token_count",'
                '"info":{"total_token_usage":{"input_tokens":999999,"total_tokens":999999},'
                '"last_token_usage":{"input_tokens":1000,"cached_input_tokens":2000,'
                '"output_tokens":300,"reasoning_output_tokens":50,"total_tokens":1300}}}}',
            ]
        )
    )

    usage = list(iter_codex_token_usage(tmp_path))

    assert len(usage) == 1
    assert usage[0].provider == "codex"
    assert usage[0].session_id == "c1"
    assert usage[0].project_dir == "/repo/agentype"
    assert usage[0].input_tokens == 1000
    assert usage[0].reasoning_tokens == 50
    assert usage[0].cache_read_tokens == 2000
    assert usage[0].non_cache_tokens == 1300


def test_pi_token_usage_reads_total_and_cost(tmp_path: Path) -> None:
    session = tmp_path / "--repo-agentype--" / "2026-04-30T01-00-00-000Z_p1.jsonl"
    session.parent.mkdir()
    session.write_text(
        "\n".join(
            [
                '{"type":"session","version":3,"id":"p1","timestamp":"2026-04-30T01:00:00Z",'
                '"cwd":"/repo/agentype"}',
                '{"type":"message","id":"m1","timestamp":"2026-04-30T01:01:00Z",'
                '"message":{"role":"assistant","model":"deepseek","usage":{"input":10,"output":5,'
                '"cacheRead":20,"cacheWrite":2,"totalTokens":15,"cost":{"total":0.25}}}}',
            ]
        )
    )

    usage = list(iter_pi_token_usage(tmp_path))

    assert len(usage) == 1
    assert usage[0].provider == "pi"
    assert usage[0].session_id == "p1"
    assert usage[0].model == "deepseek"
    assert usage[0].non_cache_tokens == 15
    assert usage[0].tokens_with_cache == 37
    assert usage[0].cost == 0.25


def test_opencode_token_usage_reads_sqlite_message_tokens(tmp_path: Path) -> None:
    db_path = tmp_path / "opencode.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE project (id text PRIMARY KEY, worktree text NOT NULL);
        CREATE TABLE session (
            id text PRIMARY KEY,
            project_id text NOT NULL,
            directory text NOT NULL
        );
        CREATE TABLE message (
            id text PRIMARY KEY,
            session_id text NOT NULL,
            time_created integer NOT NULL,
            data text NOT NULL
        );
        """
    )
    conn.execute("INSERT INTO project VALUES (?, ?)", ("proj1", "/repo/agentype"))
    conn.execute("INSERT INTO session VALUES (?, ?, ?)", ("o1", "proj1", "/repo/agentype"))
    conn.execute(
        "INSERT INTO message VALUES (?, ?, ?, ?)",
        (
            "m1",
            "o1",
            1777470001000,
            json.dumps(
                {
                    "role": "assistant",
                    "modelID": "gpt-5",
                    "path": {"cwd": "/repo/agentype"},
                    "tokens": {
                        "input": 100,
                        "output": 20,
                        "reasoning": 5,
                        "cache": {"read": 300, "write": 40},
                    },
                    "cost": 0.5,
                }
            ),
        ),
    )
    conn.commit()
    conn.close()

    usage = list(iter_opencode_token_usage(tmp_path))

    assert len(usage) == 1
    assert usage[0].provider == "opencode"
    assert usage[0].session_id == "o1"
    assert usage[0].project_dir == "/repo/agentype"
    assert usage[0].model == "gpt-5"
    assert usage[0].non_cache_tokens == 125
    assert usage[0].tokens_with_cache == 465
    assert usage[0].cost == 0.5


def test_gemini_token_usage_reads_message_tokens(tmp_path: Path) -> None:
    session = tmp_path / "tmp" / "hash1" / "chats" / "session-2026-04-30T01-00-g1.json"
    session.parent.mkdir(parents=True)
    session.write_text(
        """
        {
          "sessionId": "g1",
          "messages": [
            {"timestamp":"2026-04-30T01:01:00Z","type":"gemini","model":"gemini-3-pro",
             "tokens":{"input":100,"output":20,"cached":300,"thoughts":5,"total":125}}
          ]
        }
        """
    )

    usage = list(iter_gemini_token_usage(tmp_path))

    assert len(usage) == 1
    assert usage[0].provider == "gemini"
    assert usage[0].session_id == "g1"
    assert usage[0].model == "gemini-3-pro"
    assert usage[0].non_cache_tokens == 125
    assert usage[0].tokens_with_cache == 425


def test_openclaw_token_usage_reads_total_and_cost(tmp_path: Path) -> None:
    session = tmp_path / "main" / "sessions" / "o1.jsonl"
    session.parent.mkdir(parents=True)
    session.write_text(
        "\n".join(
            [
                '{"type":"session","id":"o1","timestamp":"2026-04-30T01:00:00Z","cwd":"/repo/agentype"}',
                '{"type":"message","timestamp":"2026-04-30T01:01:00Z",'
                '"message":{"role":"assistant","model":"minimax","usage":{"input":10,"output":5,'
                '"cacheRead":20,"cacheWrite":2,"totalTokens":15,"cost":{"total":0.25}}}}',
            ]
        )
    )

    usage = list(iter_openclaw_token_usage(tmp_path))

    assert len(usage) == 1
    assert usage[0].provider == "openclaw"
    assert usage[0].session_id == "o1"
    assert usage[0].project_dir == "/repo/agentype"
    assert usage[0].model == "minimax"
    assert usage[0].tokens_with_cache == 37
    assert usage[0].cost == 0.25


def test_nanobot_token_usage_reads_optional_usage(tmp_path: Path) -> None:
    session = tmp_path / "cli_direct.jsonl"
    session.write_text(
        '{"role":"assistant","content":"done","timestamp":"2026-04-30T01:02:00",'
        '"model":"mini","usage":{"input":10,"output":5,"reasoning":2,'
        '"cacheRead":3,"cacheWrite":4,"totalTokens":17,"cost":{"total":0.01}}}'
    )

    usage = list(iter_nanobot_token_usage(tmp_path))

    assert len(usage) == 1
    assert usage[0].provider == "nanobot"
    assert usage[0].session_id == "cli_direct"
    assert usage[0].non_cache_tokens == 17
    assert usage[0].tokens_with_cache == 24
    assert usage[0].cost == 0.01


def test_nanobot_compat_token_usage_reads_provider_payload(tmp_path: Path) -> None:
    session = tmp_path / "sessions" / "2026" / "04" / "30" / "chat_20260430T010000_f1.jsonl"
    session.parent.mkdir(parents=True)
    session.write_text(
        "\n".join(
            [
                '{"_type":"session_state","session_id":"f1","key":"chat",'
                '"created_at":"2026-04-30T01:00:00","updated_at":"2026-04-30T01:02:00"}',
                '{"role":"assistant","content":"done","timestamp":"2026-04-30T01:02:00",'
                '"model":"glm-5","provider_payload":{"usage":{"prompt_tokens":100,'
                '"completion_tokens":20,"total_tokens":120,'
                '"completion_tokens_details":{"reasoning_tokens":5}}}}',
            ]
        )
    )

    usage = list(iter_nanobot_compat_token_usage(tmp_path / "sessions"))

    assert len(usage) == 1
    assert usage[0].provider == "nanobot"
    assert usage[0].session_id == "f1"
    assert usage[0].project_dir == str(tmp_path)
    assert usage[0].model == "glm-5"
    assert usage[0].input_tokens == 100
    assert usage[0].output_tokens == 20
    assert usage[0].reasoning_tokens == 5
    assert usage[0].non_cache_tokens == 120


def test_summarize_token_usage_by_provider() -> None:
    summary = summarize_token_usage(
        [
            TokenUsage(provider="a", source_path=Path("a"), input_tokens=10, output_tokens=5, cache_read_tokens=20),
            TokenUsage(provider="a", source_path=Path("b"), total_tokens=7, cache_write_tokens=3, cost=0.25),
        ]
    )

    assert summary["a"]["records"] == 2
    assert summary["a"]["input_tokens"] == 10
    assert summary["a"]["output_tokens"] == 5
    assert summary["a"]["non_cache_tokens"] == 22
    assert summary["a"]["tokens_with_cache"] == 45
    assert summary["a"]["cost"] == 0.25
