"""
clco-notify — Claude Code Slack Notification Hook
--------------------------------------------------
Sends delayed Slack notifications. If the user responds before the delay
expires, the notification is cancelled automatically.

Config file: .env.clconotify  (project root, gitignored)
Template:    .env.clconotify-example

Runtime files (gitignored):
  .claude/hooks/.session_state.json   — last prompt per session
  .claude/hooks/.pending_<sid>.json   — pending notification per session

Flow:
  UserPromptSubmit  → cancel pending timer + save prompt
  Stop/Notification → build message, save as pending, spawn delayed sender
  [N seconds later] → sender checks if still pending → sends or skips

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
    config_path = Path.cwd() / ".env.clconotify"
    if config_path.exists():
        with open(config_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value:
                    config[key] = value
    return config


def _int(config, key, default):
    try:
        return int(config.get(key, str(default)))
    except ValueError:
        return default


# ---------------------------------------------------------------------------
# Session state — last prompt per session
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


def save_last_prompt(session_id, prompt):
    if not session_id or not prompt:
        return
    state = _load_state()
    while len(state) >= MAX_SESSIONS:
        state.pop(next(iter(state)))
    state[session_id] = prompt[:500]
    _save_state(state)


def get_last_prompt(session_id):
    if not session_id:
        return ""
    return _load_state().get(session_id, "")


# ---------------------------------------------------------------------------
# Pending notification — per-session file
# ---------------------------------------------------------------------------

def _pending_path(session_id):
    return Path.cwd() / ".claude" / "hooks" / (".pending_" + session_id[:16] + ".json")


def save_pending(session_id, stamp, message, channel):
    p = _pending_path(session_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"stamp": stamp, "message": message, "channel": channel}, ensure_ascii=False),
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
    """Delete ALL .pending_*.json files — use manually only.
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
    Safe to run on SessionStart — does not affect timers from active sessions."""
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
# Emoji map — edit here to customize status icons
# ---------------------------------------------------------------------------
# key: (hook_event_name, notification_type)  or  (hook_event_name, None) for Stop
# value: (emoji, status_text)  or  None to suppress
EVENT_LABELS = {
    ("Stop",         None):                 ("✅", "Claude Code finished responding."),
    ("Notification", "idle_prompt"):        ("⏳", "Claude Code is waiting for your input."),
    ("Notification", "elicitation_dialog"): ("❓", "Claude Code has a question for you."),
    ("Notification", "permission_prompt"):  ("🔐", "Claude Code is requesting permission."),
    ("Notification", "auth_success"):       None,   # suppressed
    ("Notification", None):                 ("🔔", "Claude Code needs your attention."),  # fallback
}


def _trunc(text, maxlen):
    return text[:maxlen] + ("..." if len(text) > maxlen else "")


def build_message(event, config):
    """Build Slack message text. Returns None to skip."""
    event_name = event.get("hook_event_name", "")
    notif_type = event.get("notification_type") if event_name == "Notification" else None
    session_id = event.get("session_id", "")
    event_message = event.get("message", "").strip()
    project = config.get("SLACK_NOTIFY_PROJECT_NAME", "").strip()

    last_prompt_maxlen = _int(config, "SLACK_NOTIFY_LAST_PROMPT_MAXLEN", 150)
    event_msg_maxlen   = _int(config, "SLACK_NOTIFY_EVENT_MESSAGE_MAXLEN", 200)

    label = EVENT_LABELS.get((event_name, notif_type))
    if label is None and notif_type is not None:
        label = EVENT_LABELS.get((event_name, None))
    if label is None:
        return None

    emoji, status_text = label

    user_id    = config.get("SLACK_NOTIFY_USER_ID", "").strip()
    user_email = config.get("SLACK_NOTIFY_USER_EMAIL", "").strip()
    is_dm = bool(user_id or user_email)

    lines = []

    # Mention (channel mode only — DM already goes to the right person)
    if not is_dm and user_id:
        lines.append("<@" + user_id + ">")
    elif not is_dm and user_email:
        lines.append(user_email)

    # Meta: project + session
    meta_parts = []
    if project:
        meta_parts.append("Project: " + project)
    if session_id:
        meta_parts.append("Session: " + session_id[:8])
    if meta_parts:
        lines.append(" | ".join(meta_parts))

    # Emoji status
    lines.append(emoji + " " + status_text)

    # Last user prompt (context for all events)
    last_prompt = get_last_prompt(session_id)
    if last_prompt:
        lines.append("``` " + _trunc(last_prompt, last_prompt_maxlen))

    # Event message (optional)
    if event_message:
        lines.append("> " + _trunc(event_message, event_msg_maxlen))

    return "\n".join(lines)


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


def send_message(token, channel, text):
    payload = {"channel": channel, "text": text}
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
        if not result.get("ok"):
            print("[ERROR] chat.postMessage: " + result.get("error", "unknown"), file=sys.stderr)
    except Exception as exc:
        print("[ERROR] Failed to send Slack message: " + str(exc), file=sys.stderr)


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
    send_message(token, pending["channel"], pending["message"])


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
        save_last_prompt(session_id, event.get("prompt", "").strip())
        sys.exit(0)

    message = build_message(event, config)
    if message is None:
        sys.exit(0)

    channel = resolve_channel(config, token)
    if not channel:
        print("[WARN] No Slack target configured (USER_ID, EMAIL, or CHANNEL required)", file=sys.stderr)
        sys.exit(0)

    delay = _int(config, "SLACK_NOTIFY_DELAY_SECONDS", 60)
    stamp = time.time()

    save_pending(session_id, stamp, message, channel)
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
