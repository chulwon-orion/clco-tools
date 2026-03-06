"""
clco-notify Setup Script
=========================
Run this once in any project to install clco-notify (Claude Code Slack notification hooks).

Usage:
    python3 setup_clco_notify.py
    python3 setup_clco_notify.py --user-id U0123456789
    python3 setup_clco_notify.py --email your.name@company.com
    python3 setup_clco_notify.py --user-id U0123456789 --python python

Options:
    --user-id ID     Slack User ID to DM (e.g. U0123456789)
                     Find: Slack -> click username -> ... -> Copy member ID
    --email EMAIL    Slack user email (alternative to --user-id, requires users:read.email scope)
    --python CMD     Python command to use in hooks (default: auto-detect python3 or python)

What this does:
    1. Detects python command (or uses --python)
    2. Merges hook config into .claude/settings.json (preserves existing hooks)
    3. Copies .env.clconotify-example -> .env.clconotify (skips if already exists)
    4. Writes --user-id / --email into .env.clconotify
    5. Adds .env.clconotify to .gitignore (if git repo detected)

After running:
    Edit .env.clconotify and set SLACK_BOT_TOKEN.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


HOOK_SCRIPT = ".claude/hooks/clco_notify.py"
GITIGNORE_MARKER = ".env.clconotify"
GITIGNORE_BLOCK = "\n# clco-notify\n.env.clconotify\n"

# ---------------------------------------------------------------------------
# Hook injection map — edit here to add, remove, or change events
# Format: { event_name: command_suffix }
# The python command is prepended automatically by step_inject_settings.
# ---------------------------------------------------------------------------
HOOK_INJECTIONS = {
    "SessionStart":     HOOK_SCRIPT + " --cancel-stale",
    "UserPromptSubmit": HOOK_SCRIPT,
    "Notification":     HOOK_SCRIPT,
    "Stop":             HOOK_SCRIPT,
}


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Install Claude Code Slack notification hooks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--user-id",
        metavar="SLACK_ID",
        help="Slack User ID to DM (e.g. U0123456789)",
    )
    parser.add_argument(
        "--email",
        metavar="EMAIL",
        help="Slack user email (alternative to --user-id)",
    )
    parser.add_argument(
        "--python",
        metavar="CMD",
        help="Python command to use in hooks (default: auto-detect)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Python detection
# ---------------------------------------------------------------------------

def detect_python():
    """Return the first working python command found."""
    for cmd in ["python3", "python"]:
        if shutil.which(cmd):
            try:
                r = subprocess.run([cmd, "--version"], capture_output=True, timeout=5)
                if r.returncode == 0:
                    return cmd
            except Exception:
                pass
    return None


def resolve_python(forced):
    if forced:
        if not shutil.which(forced):
            print("[WARN] --python=" + forced + " not found in PATH, using anyway")
        else:
            print("[INFO] Using python command (forced): " + forced)
        return forced

    cmd = detect_python()
    if cmd:
        print("[INFO] Detected python command: " + cmd)
    else:
        cmd = Path(sys.executable).name
        print("[WARN] Could not detect python in PATH - using: " + cmd)
    return cmd


# ---------------------------------------------------------------------------
# .claude/settings.json inject
# ---------------------------------------------------------------------------

def _merge_hook_event(hooks_section, event, command):
    """Inject a hook entry into an event section, updating python cmd if already present."""
    event_entries = hooks_section.setdefault(event, [])
    already_present = any(
        HOOK_SCRIPT in hook.get("command", "")
        for entry in event_entries
        for hook in entry.get("hooks", [])
    )
    changed = False
    if already_present:
        for entry in event_entries:
            for hook in entry.get("hooks", []):
                if HOOK_SCRIPT in hook.get("command", ""):
                    if hook["command"] != command:
                        hook["command"] = command
                        changed = True
    else:
        event_entries.append({"matcher": "", "hooks": [{"type": "command", "command": command}]})
        changed = True
    return changed


def step_inject_settings(project_root, python_cmd):
    """Inject clco-notify hooks into .claude/settings.json.
    Creates the file if it doesn't exist; preserves all existing hooks if it does."""
    settings_path = project_root / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    if settings_path.exists():
        try:
            with open(settings_path, encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print("[ERROR] Could not read .claude/settings.json: " + str(e))
            print("[INFO]  Fix the file manually and re-run, or delete it to start fresh.")
            return False
    else:
        existing = {}

    hooks_section = existing.setdefault("hooks", {})
    changed = False

    for event, cmd_suffix in HOOK_INJECTIONS.items():
        command = python_cmd + " " + cmd_suffix
        changed |= _merge_hook_event(hooks_section, event, command)

    if changed:
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print("[OK]   .claude/settings.json updated (python cmd: " + python_cmd + ")")
    else:
        print("[SKIP] .claude/settings.json already up to date")

    return True


# ---------------------------------------------------------------------------
# .env.clconotify management
# ---------------------------------------------------------------------------

def step_copy_env(project_root):
    """Copy .env.clconotify-example -> .env.clconotify if not already present."""
    example = project_root / ".env.clconotify-example"
    target = project_root / ".env.clconotify"

    if target.exists():
        print("[SKIP] .env.clconotify already exists - not overwriting")
        return

    if not example.exists():
        print("[WARN] .env.clconotify-example not found - skipping env copy")
        print("[INFO]  Create .env.clconotify manually with SLACK_BOT_TOKEN set.")
        return

    shutil.copy(example, target)
    print("[OK]   .env.clconotify created from example")
    print("[INFO]  Edit .env.clconotify and set SLACK_BOT_TOKEN.")


def set_env_value(env_path, key, value):
    """Write or update key=value in an env file. Returns True if changed."""
    if not env_path.exists():
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(key + "=" + value + "\n")
        return True

    lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True)

    for i, line in enumerate(lines):
        stripped = line.strip()
        # Match uncommented key (with or without value)
        if stripped.startswith(key + "=") and not stripped.startswith("#"):
            existing_val = stripped[len(key) + 1:]
            if existing_val == value:
                return False  # Already correct
            lines[i] = key + "=" + value + "\n"
            env_path.write_text("".join(lines), encoding="utf-8")
            return True

    # Key not found - append
    with open(env_path, "a", encoding="utf-8") as f:
        f.write(key + "=" + value + "\n")
    return True


def step_set_user(project_root, user_id, email):
    """Write --user-id / --email into .env.clconotify."""
    env_path = project_root / ".env.clconotify"

    if not env_path.exists():
        print("[WARN] .env.clconotify not found - run setup first without --user-id/--email, then re-run")
        return

    if user_id:
        changed = set_env_value(env_path, "SLACK_NOTIFY_USER_ID", user_id)
        label = "[OK]  " if changed else "[SKIP]"
        print(label + " SLACK_NOTIFY_USER_ID=" + user_id)

    if email:
        changed = set_env_value(env_path, "SLACK_NOTIFY_USER_EMAIL", email)
        label = "[OK]  " if changed else "[SKIP]"
        print(label + " SLACK_NOTIFY_USER_EMAIL=" + email)


# ---------------------------------------------------------------------------
# .gitignore
# ---------------------------------------------------------------------------

def step_gitignore(project_root):
    if not (project_root / ".git").exists():
        print("[SKIP] Not a git repository - skipping .gitignore update")
        return

    gitignore_path = project_root / ".gitignore"

    if gitignore_path.exists():
        content = gitignore_path.read_text(encoding="utf-8", errors="replace")
        if GITIGNORE_MARKER in content:
            print("[SKIP] .gitignore already contains .env.clconotify")
            return
        with open(gitignore_path, "a", encoding="utf-8") as f:
            f.write(GITIGNORE_BLOCK)
        print("[OK]   Added .env.clconotify to .gitignore")
    else:
        with open(gitignore_path, "w", encoding="utf-8") as f:
            f.write(GITIGNORE_MARKER + "\n")
        print("[OK]   Created .gitignore with .env.clconotify")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()
    project_root = Path(__file__).resolve().parent

    print("clco-notify Setup")
    print("Project: " + str(project_root))
    print("-" * 40)

    python_cmd = resolve_python(args.python)

    ok = step_inject_settings(project_root, python_cmd)
    if not ok:
        sys.exit(1)

    step_copy_env(project_root)

    if args.user_id or args.email:
        step_set_user(project_root, args.user_id, args.email)

    step_gitignore(project_root)

    print("-" * 40)
    print("[DONE] Setup complete.")
    print()
    print("Next steps:")
    print("  1. Edit .env.clconotify")
    print("  2. Set SLACK_BOT_TOKEN=xoxb-...")
    if not args.user_id and not args.email:
        print("  3. Set SLACK_NOTIFY_USER_ID or SLACK_NOTIFY_USER_EMAIL")
    print()
    print("Test:")
    print('  echo \'{"hook_event_name":"Stop"}\' | ' + python_cmd + " .claude/hooks/clco_notify.py")


if __name__ == "__main__":
    main()
