"""
clco-notify -- Claude Code Slack Notification Hook
--------------------------------------------------
Sends delayed Slack notifications. If the user responds before the delay
expires, the notification is cancelled automatically.

Config file: .env.clco  (project root or ~/.claude/, gitignored)
Template:    .env.clco-example

Runtime files (gitignored):
  .claude/hooks/.session_state.json   -- last prompt per session
  .claude/hooks/.pending_<sid>.json   -- pending notification per session

Flow:
  UserPromptSubmit  -> cancel pending timer + save prompt + timestamp
  Stop/Notification -> build Block Kit message, save as pending, spawn delayed sender
  [N seconds later] -> sender checks if still pending -> sends or skips
                       first send saves thread_ts; subsequent sends reply in thread

Modes:
  python3 clco_notify.py                           # hook mode (called by Claude Code)
  python3 clco_notify.py --send SID STAMP DELAY    # sender mode (internal background process)
"""

import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config():
    config = {}
    # Search order: project root (.env.clco) -> global (~/.claude/.env.clco)
    # Both files are read; project-level values take precedence over global.
    candidates = [
        Path.cwd() / ".env.clco",
        Path.home() / ".claude" / ".env.clco",
    ]
    for config_path in candidates:
        if config_path.exists():
            with open(config_path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and value and key not in config:
                        config[key] = value
    return config


def _int(config, key, default):
    try:
        return int(config.get(key, str(default)))
    except ValueError:
        return default


# ---------------------------------------------------------------------------
# Session state -- last prompt + timestamp + thread_ts per session
# ---------------------------------------------------------------------------

STATE_FILE = ".claude/hooks/.session_state.json"
MAX_SESSIONS = 30


def _state_path():
    return Path.cwd() / STATE_FILE


def _load_state():
    p = _state_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_state(state):
    p = _state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


def get_session_state(session_id):
    """Return dict with keys: prompt, ts, thread_ts. Handles old plain-string format."""
    if not session_id:
        return {"prompt": "", "ts": None, "thread_ts": None}
    raw = _load_state().get(session_id, {})
    if isinstance(raw, str):
        # Migrate on read: old plain-string format
        return {"prompt": raw, "ts": None, "thread_ts": None}
    return {
        "prompt": raw.get("prompt", ""),
        "ts": raw.get("ts"),
        "thread_ts": raw.get("thread_ts"),
    }


def get_last_prompt(session_id):
    return get_session_state(session_id)["prompt"]


def save_session_prompt(session_id, prompt):
    """Save prompt + current timestamp, preserving any existing thread_ts."""
    if not session_id or not prompt:
        return
    state = _load_state()
    while len(state) >= MAX_SESSIONS:
        state.pop(next(iter(state)))
    existing = state.get(session_id, {})
    existing_thread_ts = existing.get("thread_ts") if isinstance(existing, dict) else None
    state[session_id] = {
        "prompt": prompt[:500],
        "ts": time.time(),
        "thread_ts": existing_thread_ts,
    }
    _save_state(state)


def save_thread_ts(session_id, thread_ts):
    """Save the Slack message ts so subsequent events in this session reply in-thread."""
    if not session_id or not thread_ts:
        return
    state = _load_state()
    entry = state.get(session_id, {})
    if isinstance(entry, str):
        entry = {"prompt": entry, "ts": None}
    entry["thread_ts"] = thread_ts
    state[session_id] = entry
    _save_state(state)


# ---------------------------------------------------------------------------
# Pending notification -- per-session file
# ---------------------------------------------------------------------------

def _pending_path(session_id):
    return Path.cwd() / ".claude" / "hooks" / (".pending_" + session_id[:16] + ".json")


def save_pending(session_id, stamp, channel, text, blocks, thread_ts):
    p = _pending_path(session_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(
            {"stamp": stamp, "channel": channel, "text": text,
             "blocks": blocks, "thread_ts": thread_ts},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def get_pending(session_id):
    p = _pending_path(session_id)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def cancel_pending(session_id):
    try:
        _pending_path(session_id).unlink()
    except FileNotFoundError:
        pass
    except Exception:
        pass


def cancel_all_pending():
    """Delete ALL .pending_*.json files -- use manually only.
    WARNING: also cancels timers from other active sessions."""
    hooks_dir = Path.cwd() / ".claude" / "hooks"
    files = list(hooks_dir.glob(".pending_*.json")) if hooks_dir.exists() else []
    if not files:
        print("[INFO] No pending notifications found.")
        return
    for f in files:
        try:
            f.unlink()
            print("[OK]   Cancelled: " + f.name)
        except Exception as exc:
            print("[ERROR] Could not delete " + f.name + ": " + str(exc))
    print("[DONE] Cancelled " + str(len(files)) + " pending notification(s).")


def cancel_stale_pending(config):
    """Delete only pending files older than the configured delay (+ buffer).
    Safe to run on SessionStart -- does not affect timers from active sessions."""
    delay = _int(config, "SLACK_NOTIFY_DELAY_SECONDS", 60)
    stale_threshold = delay + 30  # buffer: 30s grace period after timer would have fired
    now = time.time()

    hooks_dir = Path.cwd() / ".claude" / "hooks"
    files = list(hooks_dir.glob(".pending_*.json")) if hooks_dir.exists() else []
    removed = 0
    for f in files:
        age = now - f.stat().st_mtime
        if age > stale_threshold:
            try:
                f.unlink()
                print("[OK]   Removed stale pending: " + f.name + " (age: " + str(int(age)) + "s)")
                removed += 1
            except Exception as exc:
                print("[ERROR] " + f.name + ": " + str(exc))
    if removed == 0:
        print("[INFO] No stale notifications found.")
    else:
        print("[DONE] Removed " + str(removed) + " stale pending notification(s).")


# ---------------------------------------------------------------------------
# Emoji map -- edit here to customize status icons
# ---------------------------------------------------------------------------
# key: (hook_event_name, notification_type)  or  (hook_event_name, None) for Stop
# value: (emoji, status_text)  or  None to suppress
EVENT_LABELS = {
    ("Stop",         None):                 ("\u2705", "Claude Code finished responding."),
    ("Notification", "idle_prompt"):        ("\u23f3", "Claude Code is waiting for your input."),
    ("Notification", "elicitation_dialog"): ("\u2753", "Claude Code has a question for you."),
    ("Notification", "permission_prompt"):  ("\U0001f510", "Claude Code is requesting permission."),
    ("Notification", "auth_success"):       None,   # suppressed
    ("Notification", None):                 ("\U0001f514", "Claude Code needs your attention."),  # fallback
}


SLACK_MAX_LEN_CAP = 3000

def _trunc(text, maxlen):
    """Truncate text to maxlen chars. maxlen <= 0 means no limit. Hard cap: SLACK_MAX_LEN_CAP."""
    effective = min(maxlen, SLACK_MAX_LEN_CAP) if maxlen > 0 else SLACK_MAX_LEN_CAP
    if len(text) <= effective:
        return text
    return text[:effective] + "..."


def build_blocks(event, config):
    """Build Slack Block Kit payload. Returns (text_fallback, blocks) or (None, None) to skip."""
    event_name    = event.get("hook_event_name", "")
    notif_type    = event.get("notification_type") if event_name == "Notification" else None
    session_id    = event.get("session_id", "")
    event_message = event.get("message", "").strip()
    project       = config.get("SLACK_NOTIFY_PROJECT_NAME", "").strip()

    last_prompt_maxlen = _int(config, "SLACK_NOTIFY_LAST_PROMPT_MAXLEN", 150)
    event_msg_maxlen   = _int(config, "SLACK_NOTIFY_EVENT_MESSAGE_MAXLEN", 200)

    label = EVENT_LABELS.get((event_name, notif_type))
    if label is None and notif_type is not None:
        label = EVENT_LABELS.get((event_name, None))
    if label is None:
        return None, None

    emoji, status_text = label

    session_state = get_session_state(session_id)
    last_prompt   = session_state["prompt"]
    prompt_ts     = session_state["ts"]

    # Elapsed time since the last user prompt
    elapsed_str = None
    if prompt_ts is not None:
        elapsed_sec = int(time.time() - prompt_ts)
        m, s = divmod(elapsed_sec, 60)
        elapsed_str = (str(m) + "m " + str(s) + "s") if m else (str(s) + "s")

    # Plain text fallback (mobile push / desktop toast preview shown alongside blocks)
    text_fallback = ("[" + project + "] " if project else "") + emoji + " " + status_text

    # Channel-mode mention (in DM mode the right person already receives it)
    user_id    = config.get("SLACK_NOTIFY_USER_ID", "").strip()
    user_email = config.get("SLACK_NOTIFY_USER_EMAIL", "").strip()
    is_dm = bool(user_id or user_email)
    if not is_dm:
        if user_id:
            text_fallback = "<@" + user_id + "> " + text_fallback
        elif user_email:
            text_fallback = user_email + " " + text_fallback

    blocks = []

    # Header block
    blocks.append({
        "type": "header",
        "text": {"type": "plain_text", "text": emoji + "  " + status_text, "emoji": True},
    })

    # Context block: project | session | elapsed
    context_parts = []
    if project:
        context_parts.append("*Project:* " + project)
    if session_id:
        context_parts.append("*Session:* " + session_id[:8])
    if elapsed_str:
        context_parts.append("*Elapsed:* " + elapsed_str)
    if context_parts:
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": "  |  ".join(context_parts)}],
        })

    # Last prompt section
    if last_prompt:
        prompt_text = "*Last prompt:*\n```\n" + _trunc(last_prompt, last_prompt_maxlen) + "\n```"
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": prompt_text},
        })

    # Event message section (Notification events)
    if event_message:
        blocks.append({"type": "divider"})
        msg_text = "*Message:*\n> " + _trunc(event_message, event_msg_maxlen)
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": msg_text},
        })

    return text_fallback, blocks


# ---------------------------------------------------------------------------
# Slack API
# ---------------------------------------------------------------------------

def lookup_user_by_email(token, email):
    url = "https://slack.com/api/users.lookupByEmail?email=" + urllib.parse.quote(email)
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        if data.get("ok"):
            return data["user"]["id"]
        print("[ERROR] users.lookupByEmail: " + data.get("error", "unknown"), file=sys.stderr)
    except Exception as exc:
        print("[ERROR] Email lookup failed: " + str(exc), file=sys.stderr)
    return None


def resolve_channel(config, token):
    user_id = config.get("SLACK_NOTIFY_USER_ID", "").strip()
    if user_id:
        return user_id
    email = config.get("SLACK_NOTIFY_USER_EMAIL", "").strip()
    if email:
        return lookup_user_by_email(token, email)
    channel = config.get("SLACK_NOTIFY_CHANNEL", "").strip()
    if channel:
        return channel
    return None


def send_message(token, channel, text, blocks=None, thread_ts=None):
    """Send a Slack message. Returns the message ts string on success, or None."""
    payload = {"channel": channel, "text": text or ""}
    if blocks:
        payload["blocks"] = blocks
    if thread_ts:
        payload["thread_ts"] = thread_ts
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=data,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + token},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
        if result.get("ok"):
            return result.get("ts")
        print("[ERROR] chat.postMessage: " + result.get("error", "unknown"), file=sys.stderr)
    except Exception as exc:
        print("[ERROR] Failed to send Slack message: " + str(exc), file=sys.stderr)
    return None


# ---------------------------------------------------------------------------
# Delayed sender mode  (background process)
# ---------------------------------------------------------------------------

def sender_mode(session_id, stamp, delay):
    """Sleep DELAY seconds, then send only if our pending stamp is still active."""
    time.sleep(delay)

    pending = get_pending(session_id)
    if pending is None or pending.get("stamp") != stamp:
        sys.exit(0)  # Cancelled by UserPromptSubmit or replaced by newer event

    config = load_config()
    token = config.get("SLACK_BOT_TOKEN", "").strip()
    if not token or "your-bot-token" in token:
        cancel_pending(session_id)
        sys.exit(0)

    cancel_pending(session_id)

    # Backward compat: old pending files used "message" key instead of "text"
    text = pending.get("text") or pending.get("message", "")
    thread_ts = pending.get("thread_ts")

    returned_ts = send_message(
        token,
        pending["channel"],
        text,
        blocks=pending.get("blocks"),
        thread_ts=thread_ts,
    )

    # On first message of a session, save the Slack ts so subsequent events reply in-thread
    if thread_ts is None and returned_ts:
        save_thread_ts(session_id, returned_ts)


def spawn_sender(session_id, stamp, delay):
    """Spawn a detached background process to send after delay."""
    kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    subprocess.Popen(
        [sys.executable, __file__, "--send", session_id, str(stamp), str(delay)],
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Hook mode  (called by Claude Code)
# ---------------------------------------------------------------------------

def hook_mode():
    config = load_config()
    token = config.get("SLACK_BOT_TOKEN", "").strip()
    if not token or "your-bot-token" in token:
        sys.exit(0)

    try:
        event = json.loads(sys.stdin.read() or "{}")
    except Exception:
        event = {}

    event_name = event.get("hook_event_name", "")
    session_id = event.get("session_id", "")

    if event_name == "UserPromptSubmit":
        cancel_pending(session_id)
        save_session_prompt(session_id, event.get("prompt", "").strip())
        sys.exit(0)

    text_fallback, blocks = build_blocks(event, config)
    if text_fallback is None:
        sys.exit(0)

    channel = resolve_channel(config, token)
    if not channel:
        print("[WARN] No Slack target configured (USER_ID, EMAIL, or CHANNEL required)", file=sys.stderr)
        sys.exit(0)

    delay = _int(config, "SLACK_NOTIFY_DELAY_SECONDS", 60)
    stamp = time.time()

    # Pass thread_ts so sender can reply in-thread for subsequent events
    thread_ts = get_session_state(session_id)["thread_ts"]
    save_pending(session_id, stamp, channel, text_fallback, blocks, thread_ts)
    spawn_sender(session_id, stamp, delay)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) == 5 and sys.argv[1] == "--send":
        try:
            sender_mode(sys.argv[2], float(sys.argv[3]), int(sys.argv[4]))
        except Exception as exc:
            print("[ERROR] sender_mode: " + str(exc), file=sys.stderr)
        return

    if len(sys.argv) == 2 and sys.argv[1] == "--cancel-all":
        cancel_all_pending()
        return

    if len(sys.argv) == 2 and sys.argv[1] == "--cancel-stale":
        cancel_stale_pending(load_config())
        return

    hook_mode()


if __name__ == "__main__":
    main()
