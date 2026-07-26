#!/usr/bin/env python3
"""Recover missing user prompts from local Codex JSONL transcripts."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

VN_TZ = timezone(timedelta(hours=7))
LEGACY_WINDOW_SECONDS = 300
TRANSCRIPT_DUPLICATE_WINDOW_SECONDS = 120
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SECRET_PATTERNS = (
    re.compile(r"(?i)\b([A-Z0-9_]*(?:API[_-]?KEY|TOKEN|PASSWORD|SECRET))(\s*[=:]\s*)([^\s,;]+)"),
    re.compile(r"(?i)\b(Bearer\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
)


def git(*args):
    try:
        return subprocess.check_output(["git", *args], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def normalize_path(value):
    try:
        return os.path.normcase(os.path.abspath(str(value))).rstrip("\\/")
    except (OSError, ValueError):
        return ""


def path_belongs_to_repo(cwd, repo_root):
    candidate, root = normalize_path(cwd), normalize_path(repo_root)
    if not candidate or not root:
        return False
    try:
        return os.path.commonpath([candidate, root]) in (candidate, root)
    except ValueError:
        return False


def parse_timestamp(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None


def redact_secrets(text):
    text = SECRET_PATTERNS[0].sub(r"\1\2[REDACTED]", text)
    text = SECRET_PATTERNS[1].sub(r"\1[REDACTED]", text)
    return SECRET_PATTERNS[2].sub("[REDACTED PRIVATE KEY]", text)


def fingerprint(prompt):
    return hashlib.sha256(" ".join(prompt.split()).encode("utf-8")).hexdigest()


def iter_transcript_prompts(transcript, repo_root):
    meta, messages, event_index = {}, [], 0
    try:
        with open(transcript, encoding="utf-8-sig") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except (json.JSONDecodeError, TypeError):
                    continue
                payload = record.get("payload") or {}
                if record.get("type") == "session_meta":
                    meta = payload
                    continue
                if record.get("type") != "event_msg" or payload.get("type") != "user_message":
                    continue
                event_index += 1
                prompt = payload.get("message", "")
                if isinstance(prompt, str) and prompt.strip():
                    messages.append(
                        {"event_index": event_index, "timestamp": record.get("timestamp", ""), "prompt": prompt.strip()}
                    )
    except OSError:
        return {}, []
    if meta.get("thread_source") != "user" or not path_belongs_to_repo(str(meta.get("cwd", "")), repo_root):
        return meta, []
    return meta, messages


def load_existing(log_file):
    ids, legacy = set(), []
    if not log_file.exists():
        return ids, legacy
    try:
        with open(log_file, encoding="utf-8-sig") as handle:
            for line in handle:
                try:
                    entry = json.loads(line)
                except (json.JSONDecodeError, TypeError):
                    continue
                if entry.get("entry_id"):
                    ids.add(str(entry["entry_id"]))
                prompt = entry.get("prompt")
                if entry.get("tool") == "codex" and isinstance(prompt, str) and prompt.strip():
                    legacy.append(
                        {
                            "fingerprint": fingerprint(prompt),
                            "timestamp": parse_timestamp(str(entry.get("ts", ""))),
                            "used": False,
                        }
                    )
    except OSError:
        pass
    return ids, legacy


def matches_legacy_entry(message, legacy):
    fp, timestamp = fingerprint(message["prompt"]), parse_timestamp(message["timestamp"])
    for item in legacy:
        if item["used"] or item["fingerprint"] != fp:
            continue
        existing = item["timestamp"]
        if timestamp and existing and abs((timestamp - existing).total_seconds()) > LEGACY_WINDOW_SECONDS:
            continue
        item["used"] = True
        return True
    return False


def repo_name(origin, fallback):
    value = origin.rstrip("/\\").replace("\\", "/").split("/")[-1]
    return value[:-4] if value.endswith(".git") else (value or fallback)


def build_entry(meta, message, transcript, repo, branch, commit, student):
    session_id = str(meta.get("id") or meta.get("session_id") or transcript.stem)
    timestamp = parse_timestamp(message["timestamp"])
    ts = (timestamp.astimezone(VN_TZ) if timestamp else datetime.now(VN_TZ)).isoformat()
    return {
        "ts": ts,
        "tool": "codex",
        "event": "UserPromptRecovered",
        "entry_id": f"codex-{session_id}-{message['event_index']:05d}",
        "session_id": session_id,
        "model": "codex",
        "repo": repo,
        "branch": branch,
        "commit": commit,
        "student": student,
        "prompt": redact_secrets(message["prompt"])[:1000],
        "transcript_path": str(transcript),
    }


def find_transcripts(sessions_dir, cutoff):
    if not sessions_dir.exists():
        return []
    files = sessions_dir.rglob("*.jsonl")
    if cutoff:
        files = (path for path in files if path.stat().st_mtime >= cutoff.timestamp())
    return sorted(files, key=lambda path: path.stat().st_mtime)


def main():
    parser = argparse.ArgumentParser(description="Recover user prompts from local Codex transcripts.")
    parser.add_argument("--auto", action="store_true")
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sessions-dir", type=Path)
    args = parser.parse_args()
    root_text = git("rev-parse", "--show-toplevel")
    root = Path(root_text) if root_text else Path.cwd()
    sessions = args.sessions_dir or Path(os.environ.get("CODEX_SESSIONS_DIR", Path.home() / ".codex" / "sessions"))
    cutoff = None if args.all else datetime.now(UTC) - timedelta(hours=args.hours)
    transcripts = find_transcripts(sessions, cutoff)
    if not transcripts:
        print(f"[codex-log] No transcripts found in {sessions}.", file=sys.stderr)
        return
    log_dir = Path(os.environ.get("AI_LOG_DIR", ".ai-log"))
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "session.jsonl"
    ids, legacy = load_existing(log_file)
    metadata = (
        repo_name(git("remote", "get-url", "origin"), root.name),
        git("rev-parse", "--abbrev-ref", "HEAD"),
        git("rev-parse", "--short", "HEAD"),
        git("config", "user.email") or os.environ.get("USERNAME", os.environ.get("USER", "unknown")),
    )
    new_entries, seen_messages = [], []
    for transcript in transcripts:
        meta, messages = iter_transcript_prompts(transcript, root)
        for message in messages:
            message_time, message_fp = parse_timestamp(message["timestamp"]), fingerprint(message["prompt"])
            duplicate = any(
                old_fp == message_fp
                and message_time
                and old_time
                and abs((message_time - old_time).total_seconds()) <= TRANSCRIPT_DUPLICATE_WINDOW_SECONDS
                for old_fp, old_time in seen_messages
            )
            seen_messages.append((message_fp, message_time))
            entry = build_entry(meta, message, transcript, *metadata)
            if entry["entry_id"] in ids or duplicate or matches_legacy_entry(message, legacy):
                continue
            ids.add(entry["entry_id"])
            new_entries.append(entry)
    if not new_entries:
        print("[codex-log] No new user prompts.", file=sys.stderr)
        return
    if args.dry_run:
        print(f"[codex-log] DRY RUN - would log {len(new_entries)} prompt(s):")
        for entry in new_entries:
            print(f"  [{entry['ts'][:19]}] {entry['prompt'].replace(chr(10), ' ')[:120]}")
        return
    with open(log_file, "a", encoding="utf-8") as handle:
        for entry in new_entries:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"[codex-log] Logged {len(new_entries)} recovered prompt(s).", file=sys.stderr)


if __name__ == "__main__":
    main()
