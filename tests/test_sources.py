from pathlib import Path

from agentype import collector
from agentype import paths
from agentype.collector import SkillInfo, SkillRoot, collect_project_documents
from agentype.sources.base import SessionEvent
from agentype.sources.claude import iter_events as iter_claude_events
from agentype.sources.codex import iter_events as iter_codex_events
from agentype.sources import claude, codex, gemini, nanobot, opencode, openclaw, pi
from agentype.sources.nanobot_compat import iter_events as iter_nanobot_compat_events
from agentype.sources.gemini import iter_events as iter_gemini_events
from agentype.sources.nanobot import iter_events as iter_nanobot_events
from agentype.sources.opencode import iter_events as iter_opencode_events
from agentype.sources.openclaw import iter_events as iter_openclaw_events
from agentype.sources.pi import iter_events as iter_pi_events


def test_default_collection_roots_use_agentype_home_override(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTYPE_TEST_HOME", str(tmp_path))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    assert paths.home_dir() == tmp_path
    assert claude.default_root() == tmp_path / ".claude" / "projects"
    assert codex.default_root() == tmp_path / ".codex"
    assert opencode.default_root() == tmp_path / ".local" / "share" / "opencode"
    assert pi.default_root() == tmp_path / ".pi" / "agent" / "sessions"
    assert gemini.default_root() == tmp_path / ".gemini"
    assert openclaw.default_root() == tmp_path / ".openclaw" / "agents"
    assert nanobot.default_root() == tmp_path / ".nanobot" / "sessions"


def test_skill_roots_use_home_override(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTYPE_TEST_HOME", str(tmp_path))

    roots = collector._skill_roots(None)

    assert roots[:3] == [
        SkillRoot("agents", tmp_path / ".agents" / "skills"),
        SkillRoot("claude", tmp_path / ".claude" / "skills"),
        SkillRoot("codex", tmp_path / ".codex" / "skills"),
    ]


def test_opencode_root_respects_xdg_data_home(tmp_path: Path, monkeypatch) -> None:
    data_home = tmp_path / "xdg-data"
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))

    assert opencode.default_root() == data_home / "opencode"


def test_claude_reader_extracts_skill_tool_use(tmp_path: Path) -> None:
    session = tmp_path / "project-a" / "session.jsonl"
    session.parent.mkdir()
    session.write_text(
        "\n".join(
            [
                '{"sessionId":"s1","cwd":"/repo/project-a","timestamp":"2026-04-30T01:00:00Z",'
                '"message":{"role":"user","content":"hello"}}',
                '{"sessionId":"s1","cwd":"/repo/project-a","timestamp":"2026-04-30T01:01:00Z",'
                '"message":{"role":"assistant","content":[{"type":"text","text":"using skill"},'
                '{"type":"tool_use","name":"Skill","input":{"skill":"pdf"}}]}}',
            ]
        )
    )

    events = list(iter_claude_events(tmp_path))
    tool_events = [event for event in events if event.kind == "tool_use"]

    assert len(tool_events) == 1
    assert tool_events[0].provider == "claude"
    assert tool_events[0].session_id == "s1"
    assert tool_events[0].project_dir == "/repo/project-a"
    assert tool_events[0].name == "Skill"
    assert tool_events[0].input == {"skill": "pdf"}


def test_codex_reader_extracts_messages_and_tool_calls(tmp_path: Path) -> None:
    session = tmp_path / "sessions" / "2026" / "04" / "30" / "rollout.jsonl"
    session.parent.mkdir(parents=True)
    session.write_text(
        "\n".join(
            [
                '{"timestamp":"2026-04-30T01:00:00Z","type":"session_meta",'
                '"payload":{"id":"c1","cwd":"/repo/agentype"}}',
                '{"timestamp":"2026-04-30T01:01:00Z","type":"response_item",'
                '"payload":{"type":"message","role":"user","content":"fix parser"}}',
                '{"timestamp":"2026-04-30T01:02:00Z","type":"response_item",'
                '"payload":{"type":"function_call","name":"exec_command","arguments":"{\\"cmd\\":\\"pytest\\"}"}}',
                '{"timestamp":"2026-04-30T01:03:00Z","type":"response_item",'
                '"payload":{"type":"function_call_output","output":"passed"}}',
            ]
        )
    )

    events = list(iter_codex_events(tmp_path))

    assert [event.kind for event in events] == ["message", "tool_use", "tool_result"]
    assert events[0].provider == "codex"
    assert events[0].session_id == "c1"
    assert events[0].project_dir == "/repo/agentype"
    assert events[0].text == "fix parser"
    assert events[1].name == "exec_command"
    assert events[2].text == "passed"


def test_pi_reader_extracts_messages_and_tool_calls(tmp_path: Path) -> None:
    session = tmp_path / "--repo-agentype--" / "2026-04-30T01-00-00-000Z_p1.jsonl"
    session.parent.mkdir()
    session.write_text(
        "\n".join(
            [
                '{"type":"session","version":3,"id":"p1","timestamp":"2026-04-30T01:00:00Z",'
                '"cwd":"/repo/agentype"}',
                '{"type":"message","id":"m1","parentId":null,"timestamp":"2026-04-30T01:01:00Z",'
                '"message":{"role":"user","content":[{"type":"text","text":"inspect files"}],'
                '"timestamp":1777470000000}}',
                '{"type":"message","id":"m2","parentId":"m1","timestamp":"2026-04-30T01:02:00Z",'
                '"message":{"role":"assistant","content":[{"type":"text","text":"reading"},'
                '{"type":"toolCall","id":"tc1","name":"read","arguments":{"path":"README.md"}}],'
                '"timestamp":1777470001000}}',
                '{"type":"message","id":"m3","parentId":"m2","timestamp":"2026-04-30T01:03:00Z",'
                '"message":{"role":"toolResult","toolCallId":"tc1","toolName":"read",'
                '"content":[{"type":"text","text":"contents"}],"isError":false,"timestamp":1777470002000}}',
            ]
        )
    )

    events = list(iter_pi_events(tmp_path))

    assert [event.kind for event in events] == ["message", "message", "tool_use", "tool_result"]
    assert events[0].provider == "pi"
    assert events[0].session_id == "p1"
    assert events[0].project_dir == "/repo/agentype"
    assert events[2].name == "read"
    assert events[2].input == {"path": "README.md"}
    assert events[3].name == "read"
    assert events[3].text == "contents"


def test_opencode_reader_extracts_messages_and_tool_calls(tmp_path: Path) -> None:
    import json
    import sqlite3

    db_path = tmp_path / "opencode.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE project (id text PRIMARY KEY, worktree text NOT NULL);
        CREATE TABLE session (
            id text PRIMARY KEY,
            project_id text NOT NULL,
            directory text NOT NULL,
            title text NOT NULL,
            version text NOT NULL,
            time_created integer NOT NULL,
            time_updated integer NOT NULL
        );
        CREATE TABLE message (
            id text PRIMARY KEY,
            session_id text NOT NULL,
            time_created integer NOT NULL,
            time_updated integer NOT NULL,
            data text NOT NULL
        );
        CREATE TABLE part (
            id text PRIMARY KEY,
            message_id text NOT NULL,
            session_id text NOT NULL,
            time_created integer NOT NULL,
            time_updated integer NOT NULL,
            data text NOT NULL
        );
        """
    )
    conn.execute("INSERT INTO project VALUES (?, ?)", ("proj1", "/repo/agentype"))
    conn.execute(
        "INSERT INTO session VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("o1", "proj1", "/repo/agentype", "Title", "1.0.0", 1777470000000, 1777470003000),
    )
    conn.execute(
        "INSERT INTO message VALUES (?, ?, ?, ?, ?)",
        (
            "m1",
            "o1",
            1777470001000,
            1777470001000,
            json.dumps({"role": "user", "path": {"cwd": "/repo/agentype"}}),
        ),
    )
    conn.execute(
        "INSERT INTO part VALUES (?, ?, ?, ?, ?, ?)",
        ("p1", "m1", "o1", 1777470001000, 1777470001000, json.dumps({"type": "text", "text": "hello"})),
    )
    conn.execute(
        "INSERT INTO message VALUES (?, ?, ?, ?, ?)",
        (
            "m2",
            "o1",
            1777470002000,
            1777470003000,
            json.dumps({"role": "assistant", "path": {"cwd": "/repo/agentype"}}),
        ),
    )
    conn.execute(
        "INSERT INTO part VALUES (?, ?, ?, ?, ?, ?)",
        (
            "p2",
            "m2",
            "o1",
            1777470002000,
            1777470003000,
            json.dumps(
                {
                    "type": "tool",
                    "tool": "bash",
                    "state": {
                        "status": "completed",
                        "input": {"command": "pytest"},
                        "output": "passed",
                        "time": {"start": 1777470002000, "end": 1777470003000},
                    },
                }
            ),
        ),
    )
    conn.commit()
    conn.close()

    events = list(iter_opencode_events(tmp_path))

    assert [event.kind for event in events] == ["message", "tool_use", "tool_result"]
    assert events[0].provider == "opencode"
    assert events[0].session_id == "o1"
    assert events[0].project_dir == "/repo/agentype"
    assert events[0].text == "hello"
    assert events[1].name == "bash"
    assert events[1].input == {"command": "pytest"}
    assert events[2].name == "bash"
    assert events[2].text == "passed"


def test_gemini_reader_extracts_messages_and_tool_calls(tmp_path: Path) -> None:
    session = tmp_path / "tmp" / "hash1" / "chats" / "session-2026-04-30T01-00-g1.json"
    session.parent.mkdir(parents=True)
    (session.parent.parent / ".project_root").write_text("/repo/agentype")
    session.write_text(
        """
        {
          "sessionId": "g1",
          "messages": [
            {"timestamp":"2026-04-30T01:00:00Z","type":"user","content":"hello"},
            {"timestamp":"2026-04-30T01:01:00Z","type":"gemini","content":"reading",
             "toolCalls":[{"name":"read_file","args":{"path":"README.md"},
             "resultDisplay":"contents","timestamp":"2026-04-30T01:01:05Z"}]}
          ]
        }
        """
    )

    events = list(iter_gemini_events(tmp_path))

    assert [event.kind for event in events] == ["message", "message", "tool_use", "tool_result"]
    assert events[0].provider == "gemini"
    assert events[0].session_id == "g1"
    assert events[0].project_dir == "/repo/agentype"
    assert events[2].name == "read_file"
    assert events[2].input == {"path": "README.md"}
    assert events[3].text == "contents"


def test_openclaw_reader_extracts_messages_and_tool_calls(tmp_path: Path) -> None:
    session = tmp_path / "main" / "sessions" / "o1.jsonl"
    session.parent.mkdir(parents=True)
    session.write_text(
        "\n".join(
            [
                '{"type":"session","id":"o1","timestamp":"2026-04-30T01:00:00Z","cwd":"/repo/agentype"}',
                '{"type":"message","timestamp":"2026-04-30T01:01:00Z",'
                '"message":{"role":"user","content":[{"type":"text","text":"hello"}]}}',
                '{"type":"message","timestamp":"2026-04-30T01:02:00Z",'
                '"message":{"role":"assistant","content":[{"type":"text","text":"reading"},'
                '{"type":"toolCall","name":"read","arguments":{"path":"README.md"}}]}}',
                '{"type":"message","timestamp":"2026-04-30T01:03:00Z",'
                '"message":{"role":"toolResult","toolName":"read",'
                '"content":[{"type":"text","text":"contents"}]}}',
            ]
        )
    )

    events = list(iter_openclaw_events(tmp_path))

    assert [event.kind for event in events] == ["message", "message", "tool_use", "tool_result"]
    assert events[0].provider == "openclaw"
    assert events[0].session_id == "o1"
    assert events[0].project_dir == "/repo/agentype"
    assert events[2].name == "read"
    assert events[2].input == {"path": "README.md"}
    assert events[3].text == "contents"


def test_nanobot_reader_extracts_messages_and_tools_used(tmp_path: Path) -> None:
    session = tmp_path / "cli_direct.jsonl"
    session.write_text(
        "\n".join(
            [
                '{"_type":"metadata","created_at":"2026-04-30T01:00:00","updated_at":"2026-04-30T01:02:00"}',
                '{"role":"user","content":"hello","timestamp":"2026-04-30T01:01:00"}',
                '{"role":"assistant","content":"done","timestamp":"2026-04-30T01:02:00",'
                '"tools_used":["read_file","exec"]}',
            ]
        )
    )

    events = list(iter_nanobot_events(tmp_path))

    assert [event.kind for event in events] == ["message", "message", "tool_use", "tool_use"]
    assert events[0].provider == "nanobot"
    assert events[0].session_id == "cli_direct"
    assert events[2].name == "read_file"
    assert events[3].name == "exec"


def test_nanobot_compat_reader_extracts_messages_tool_calls_and_results(tmp_path: Path) -> None:
    session = tmp_path / "sessions" / "2026" / "04" / "30" / "chat_20260430T010000_f1.jsonl"
    session.parent.mkdir(parents=True)
    session.write_text(
        "\n".join(
            [
                '{"_type":"session_state","session_id":"f1","key":"chat",'
                '"created_at":"2026-04-30T01:00:00","updated_at":"2026-04-30T01:03:00"}',
                '{"role":"user","content":"hello","timestamp":"2026-04-30T01:01:00"}',
                '{"role":"assistant","content":"","timestamp":"2026-04-30T01:02:00",'
                '"tool_calls":[{"id":"call_1","type":"function","function":{"name":"read_file",'
                '"arguments":"{\\"path\\": \\"README.md\\"}"}}]}',
                '{"role":"tool","content":"contents","timestamp":"2026-04-30T01:03:00",'
                '"tool_call_id":"call_1","name":"read_file"}',
            ]
        )
    )

    events = list(iter_nanobot_compat_events(tmp_path / "sessions"))

    assert [event.kind for event in events] == ["message", "tool_use", "tool_result"]
    assert events[0].provider == "nanobot"
    assert events[0].session_id == "f1"
    assert events[0].project_dir == str(tmp_path)
    assert events[1].name == "read_file"
    assert events[1].input == {"path": "README.md"}
    assert events[2].text == "contents"


def test_collect_usage_counts_claude_skill_events(monkeypatch) -> None:
    events = [
        SessionEvent(
            provider="claude",
            session_id="s1",
            source_path=Path("session.jsonl"),
            role="assistant",
            kind="tool_use",
            timestamp="2026-04-30T01:01:00Z",
            project_dir="project-a",
            name="Skill",
            input={"skill": "pdf"},
        ),
        SessionEvent(
            provider="claude",
            session_id="s1",
            source_path=Path("session.jsonl"),
            role="assistant",
            kind="tool_use",
            timestamp="2026-04-30T01:02:00Z",
            project_dir="project-a",
            name="Bash",
        ),
    ]
    monkeypatch.setattr(collector, "iter_claude_events", lambda _root: iter(events))

    skills = {"pdf": SkillInfo(name="pdf", description="PDF tools")}

    collector.collect_usage(skills)

    assert skills["pdf"].use_count == 1
    assert skills["pdf"].last_used == "2026-04-30T01:01:00Z"
    assert skills["pdf"].projects == ["project-a"]


def test_collect_project_documents_reads_one_doc_per_top_project(tmp_path: Path) -> None:
    project = tmp_path / "agentype"
    project.mkdir()
    (project / "README.md").write_text("# Agentype\n\nPython CLI for local AI usage analytics.")
    (project / "AGENTS.md").write_text("Use uv for commands.")
    (project / "notes.md").write_text("ignored")

    documents = collect_project_documents([str(project)])

    assert [item.filename for item in documents] == ["README.md"]
    assert documents[0].project == "agentype"
    assert documents[0].text.startswith("# Agentype")
    assert documents[0].path.endswith("README.md")


def test_collect_project_documents_falls_back_to_agents_then_claude(tmp_path: Path) -> None:
    agents_project = tmp_path / "agents-project"
    agents_project.mkdir()
    (agents_project / "AGENTS.md").write_text("Agent instructions.")
    (agents_project / "CLAUDE.md").write_text("Claude instructions.")
    claude_project = tmp_path / "claude-project"
    claude_project.mkdir()
    (claude_project / "CLAUDE.md").write_text("Claude-only instructions.")

    documents = collect_project_documents([str(agents_project), str(claude_project)])

    assert [item.filename for item in documents] == ["AGENTS.md", "CLAUDE.md"]


def test_collect_installed_skills_records_category_and_canonical_path(tmp_path: Path, monkeypatch) -> None:
    skill_dir = tmp_path / ".agents" / "skills" / "cli-creator"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: cli-creator\n"
        "description: Build Python Click CLIs.\n"
        "category: development\n"
        "---\n"
    )
    monkeypatch.setattr(
        collector,
        "_skill_roots",
        lambda _dirs: [SkillRoot("agents", tmp_path / ".agents" / "skills")],
    )

    skills = collector.collect_installed_skills()

    assert skills["cli-creator"].category == "development"
    assert skills["cli-creator"].canonical_paths == [str((skill_dir / "SKILL.md").resolve())]
