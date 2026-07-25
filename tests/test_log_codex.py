import json

from scripts.log_codex import build_entry, iter_transcript_prompts, load_existing, matches_legacy_entry, redact_secrets


def write_transcript(path, meta, messages):
    records = [{"timestamp": meta["timestamp"], "type": "session_meta", "payload": meta}, *messages]
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) if isinstance(r, dict) else r for r in records), encoding="utf-8"
    )


def test_extracts_only_explicit_user_messages(tmp_path):
    repo, transcript = tmp_path / "repo", tmp_path / "rollout.jsonl"
    repo.mkdir()
    meta = {"id": "session-1", "timestamp": "2026-07-25T11:00:00Z", "cwd": str(repo), "thread_source": "user"}
    write_transcript(
        transcript,
        meta,
        [
            {
                "timestamp": "2026-07-25T11:01:00Z",
                "type": "event_msg",
                "payload": {"type": "user_message", "message": "Tiếng Việt 🚀"},
            },
            {
                "timestamp": "2026-07-25T11:02:00Z",
                "type": "response_item",
                "payload": {"type": "message", "role": "user", "content": "synthetic"},
            },
            "not-json",
        ],
    )
    parsed_meta, prompts = iter_transcript_prompts(transcript, repo)
    assert parsed_meta["id"] == "session-1"
    assert [item["prompt"] for item in prompts] == ["Tiếng Việt 🚀"]


def test_skips_subagent_and_other_repo(tmp_path):
    repo, other = tmp_path / "repo", tmp_path / "other"
    repo.mkdir()
    other.mkdir()
    message = {
        "timestamp": "2026-07-25T11:01:00Z",
        "type": "event_msg",
        "payload": {"type": "user_message", "message": "hidden"},
    }
    subagent, wrong = tmp_path / "subagent.jsonl", tmp_path / "wrong.jsonl"
    write_transcript(
        subagent,
        {"id": "s1", "timestamp": "2026-07-25T11:00:00Z", "cwd": str(repo), "thread_source": "subagent"},
        [message],
    )
    write_transcript(
        wrong, {"id": "s2", "timestamp": "2026-07-25T11:00:00Z", "cwd": str(other), "thread_source": "user"}, [message]
    )
    assert iter_transcript_prompts(subagent, repo)[1] == []
    assert iter_transcript_prompts(wrong, repo)[1] == []


def test_matches_legacy_hook_entry_once(tmp_path):
    log_file = tmp_path / "session.jsonl"
    log_file.write_text(
        json.dumps(
            {"tool": "codex", "ts": "2026-07-25T18:19:31+07:00", "prompt": "Kiểm tra tính năng"}, ensure_ascii=False
        )
        + "\n",
        encoding="utf-8",
    )
    _, legacy = load_existing(log_file)
    message = {"timestamp": "2026-07-25T11:20:00Z", "prompt": "Kiểm tra tính năng"}
    assert matches_legacy_entry(message, legacy) is True
    assert matches_legacy_entry(message, legacy) is False


def test_redacts_secrets_and_converts_timezone(tmp_path):
    entry = build_entry(
        {"id": "abc"},
        {"event_index": 2, "timestamp": "2026-07-25T11:00:00Z", "prompt": "OPENAI_API_KEY=sk-secret Bearer token123"},
        tmp_path / "rollout.jsonl",
        "P-069",
        "main",
        "abc123",
        "student@example.com",
    )
    assert entry["entry_id"] == "codex-abc-00002"
    assert entry["ts"].startswith("2026-07-25T18:00:00+07:00")
    assert "sk-secret" not in entry["prompt"] and "token123" not in entry["prompt"]
    assert entry["prompt"].count("[REDACTED]") == 2


def test_redacts_private_key_block():
    value = "before\n-----BEGIN PRIVATE KEY-----\nsecret\n-----END PRIVATE KEY-----\nafter"
    assert redact_secrets(value) == "before\n[REDACTED PRIVATE KEY]\nafter"
