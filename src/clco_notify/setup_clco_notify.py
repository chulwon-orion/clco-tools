"""
clco-notify Setup Script
=========================
Installs clco-notify (Claude Code Slack notification hooks).

Default (no arguments): installs globally into ~/.claude/ so it applies to all projects.
With --project PATH:    installs into <PATH>/.claude/ for a specific project only.
With --env-only:        installs only .env.clconotify with SLACK_NOTIFY_PROJECT_NAME set.
                        Requires --project. Useful when the hook is already installed globally
                        and you only need a project-specific config override.

Usage:
    python3 setup_clco_notify.py                                         # global install
    python3 setup_clco_notify.py --user-id U0123456789                   # global + Slack user
    python3 setup_clco_notify.py --project /path/to/proj                 # project install
    python3 setup_clco_notify.py --project /path/to/proj --user-id U...  # project + Slack user
    python3 setup_clco_notify.py --project /path/to/proj --env-only      # project env only
    python3 setup_clco_notify.py --project . --env-only                  # current dir env only

Options:
    --project DIR    Project root directory. Installs into <DIR>/.claude/ instead of ~/.claude/
    --env-only       Only install .env.clconotify (skip hook script and settings.json).
                     Requires --project. Creates a minimal env file with only
                     SLACK_NOTIFY_PROJECT_NAME active; all other keys are commented out.
                     The hook merges this file with ~/.claude/.env.clconotify at runtime,
                     so SLACK_BOT_TOKEN and other global settings still apply.
    --user-id ID     Slack User ID to DM (e.g. U0123456789)
                     Find: Slack -> click username -> ... -> Copy member ID
    --email EMAIL    Slack user email (alternative to --user-id, requires users:read.email scope)
    --python CMD     Python command to use in hooks (default: auto-detect python3 or python)

What this does (full install):
    1. Detects python command (or uses --python)
    2. Copies clco_notify.py hook script to the target .claude/hooks/ directory
    3. Merges hook config into target settings.json (preserves existing hooks)
    4. Copies .env.clconotify-example -> .env.clconotify (skips if already exists)
    5. Writes --user-id / --email into .env.clconotify
    6. Adds .env.clconotify to .gitignore (project install only, if git repo detected)

What this does (--env-only, requires --project):
    1. Creates a minimal .env.clconotify in <DIR>/ with only SLACK_NOTIFY_PROJECT_NAME active
       (skips if already exists)
    2. Writes --user-id / --email into .env.clconotify if provided
    3. Adds .env.clconotify to .gitignore if git repo detected

After running:
    Edit .env.clconotify and set SLACK_NOTIFY_PROJECT_NAME (and SLACK_BOT_TOKEN for full install).

Scopes:
    global (default)  Target: ~/.claude/       Env file: ~/.claude/.env.clconotify
    --project DIR     Target: <DIR>/.claude/   Env file: <DIR>/.env.clconotify
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


# Source files (relative to this script)
SCRIPT_DIR = Path(__file__).resolve().parent
HOOK_SOURCE = SCRIPT_DIR.parent / ".claude-global" / "hooks" / "clco_notify.py"
ENV_EXAMPLE_SOURCE = SCRIPT_DIR / ".env.clconotify-example"

HOOK_FILENAME = "clco_notify.py"
HOOK_SUBPATH = "hooks/" + HOOK_FILENAME  # relative within .claude/
GITIGNORE_MARKER = ".env.clconotify"
GITIGNORE_BLOCK = "\n# clco-notify\n.env.clconotify\n"

# ---------------------------------------------------------------------------
# Hook injection map — edit here to add, remove, or change events
# Format: { event_name: args_suffix }
# The python command and hook script path are prepended automatically.
# ---------------------------------------------------------------------------
HOOK_EVENT_ARGS = {
    "SessionStart":     "--cancel-stale",
    "UserPromptSubmit": "",
    "Notification":     "",
    "Stop":             "",
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
        "--project",
        metavar="DIR",
        default=None,
        help="Project root directory. Installs into <DIR>/.claude/ instead of ~/.claude/",
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
        "--env-only",
        action="store_true",
        default=False,
        help=(
            "Only install .env.clconotify (skip hook and settings.json). "
            "Requires --project. Creates a minimal env with only SLACK_NOTIFY_PROJECT_NAME active."
        ),
    )
    parser.add_argument(
        "--python",
        metavar="CMD",
        help="Python command to use in hooks (default: auto-detect)",
    )
    return parser.parse_args()


def resolve_scope(args):
    """Return (scope_label, claude_dir, env_dir, hook_cmd_path).

    claude_dir     — the .claude/ directory to install into (Path)
    env_dir        — where .env.clconotify goes (Path)
    hook_cmd_path  — path string used in the hook command in settings.json
    """
    if args.project:
        project_root = Path(args.project).resolve()
        claude_dir = project_root / ".claude"
        env_dir = project_root
        # Relative path — works when Claude Code is run from the project root
        hook_cmd_path = ".claude/" + HOOK_SUBPATH
        return "project", claude_dir, env_dir, hook_cmd_path
    else:
        claude_dir = Path.home() / ".claude"
        env_dir = claude_dir
        # Absolute path so the command works from any project directory.
        # Use forward slashes so bash (used by Claude Code on Windows) doesn't
        # interpret backslashes as escape characters.
        hook_cmd_path = (claude_dir / HOOK_SUBPATH).as_posix()
        return "global", claude_dir, env_dir, hook_cmd_path


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
# Copy hook script
# ---------------------------------------------------------------------------

def step_copy_hook(claude_dir):
    """Copy clco_notify.py to <claude_dir>/hooks/."""
    if not HOOK_SOURCE.exists():
        print("[ERROR] Hook source not found: " + str(HOOK_SOURCE))
        return False

    target = claude_dir / "hooks" / HOOK_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists() and target.read_bytes() == HOOK_SOURCE.read_bytes():
        print("[SKIP] Hook script already up to date: " + str(target))
        return True

    shutil.copy2(HOOK_SOURCE, target)
    print("[OK]   Hook script installed: " + str(target))
    return True


# ---------------------------------------------------------------------------
# settings.json inject
# ---------------------------------------------------------------------------

def _build_command(python_cmd, hook_cmd_path, args_suffix):
    parts = [python_cmd, hook_cmd_path]
    if args_suffix:
        parts.append(args_suffix)
    return " ".join(parts)


def _merge_hook_event(hooks_section, event, command, hook_cmd_path):
    """Inject a hook entry into an event section, updating python cmd if already present."""
    event_entries = hooks_section.setdefault(event, [])
    already_present = any(
        hook_cmd_path in hook.get("command", "")
        for entry in event_entries
        for hook in entry.get("hooks", [])
    )
    changed = False
    if already_present:
        for entry in event_entries:
            for hook in entry.get("hooks", []):
                if hook_cmd_path in hook.get("command", ""):
                    if hook["command"] != command:
                        hook["command"] = command
                        changed = True
    else:
        event_entries.append({"matcher": "", "hooks": [{"type": "command", "command": command}]})
        changed = True
    return changed


def step_inject_settings(claude_dir, python_cmd, hook_cmd_path):
    """Inject clco-notify hooks into <claude_dir>/settings.json."""
    settings_path = claude_dir / "settings.json"
    claude_dir.mkdir(parents=True, exist_ok=True)

    if settings_path.exists():
        try:
            with open(settings_path, encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print("[ERROR] Could not read " + str(settings_path) + ": " + str(e))
            print("[INFO]  Fix the file manually and re-run, or delete it to start fresh.")
            return False
    else:
        existing = {}

    hooks_section = existing.setdefault("hooks", {})
    changed = False

    for event, args_suffix in HOOK_EVENT_ARGS.items():
        command = _build_command(python_cmd, hook_cmd_path, args_suffix)
        changed |= _merge_hook_event(hooks_section, event, command, hook_cmd_path)

    if changed:
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print("[OK]   " + str(settings_path) + " updated (python cmd: " + python_cmd + ")")
    else:
        print("[SKIP] " + str(settings_path) + " already up to date")

    return True


# ---------------------------------------------------------------------------
# .env.clconotify management
# ---------------------------------------------------------------------------

def step_copy_env(env_dir):
    """Copy .env.clconotify-example -> <env_dir>/.env.clconotify if not already present."""
    target = env_dir / ".env.clconotify"

    if target.exists():
        print("[SKIP] " + str(target) + " already exists - not overwriting")
        return

    if not ENV_EXAMPLE_SOURCE.exists():
        print("[WARN] .env.clconotify-example not found - skipping env copy")
        print("[INFO]  Create .env.clconotify manually with SLACK_BOT_TOKEN set.")
        return

    env_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(ENV_EXAMPLE_SOURCE, target)
    print("[OK]   " + str(target) + " created from example")
    print("[INFO]  Edit it and set SLACK_BOT_TOKEN.")


def set_env_value(env_path, key, value):
    """Write or update key=value in an env file. Returns True if changed."""
    if not env_path.exists():
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(key + "=" + value + "\n")
        return True

    lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True)

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(key + "=") and not stripped.startswith("#"):
            existing_val = stripped[len(key) + 1:]
            if existing_val == value:
                return False
            lines[i] = key + "=" + value + "\n"
            env_path.write_text("".join(lines), encoding="utf-8")
            return True

    with open(env_path, "a", encoding="utf-8") as f:
        f.write(key + "=" + value + "\n")
    return True


_PROJECT_ENV_MARKER = "# clco-notify Project Config"


def _load_project_env_template():
    """Extract the project config section from .env.clconotify-example at the marker line."""
    if not ENV_EXAMPLE_SOURCE.exists():
        return None
    text = ENV_EXAMPLE_SOURCE.read_text(encoding="utf-8")
    idx = text.find(_PROJECT_ENV_MARKER)
    if idx == -1:
        return None
    return text[idx:]


def step_copy_env_project(env_dir):
    """Create a minimal project .env.clconotify from the marked section of .env.clconotify-example."""
    target = env_dir / ".env.clconotify"

    if target.exists():
        print("[SKIP] " + str(target) + " already exists - not overwriting")
        return

    template = _load_project_env_template()
    if template is None:
        print("[WARN] .env.clconotify-example not found or marker missing - skipping env copy")
        print("[INFO]  Create .env.clconotify manually with SLACK_NOTIFY_PROJECT_NAME set.")
        return

    env_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(template, encoding="utf-8")
    print("[OK]   " + str(target) + " created (project config)")
    print("[INFO]  Edit it and set SLACK_NOTIFY_PROJECT_NAME.")


def step_set_user(env_dir, user_id, email):
    """Write --user-id / --email into .env.clconotify."""
    env_path = env_dir / ".env.clconotify"

    if not env_path.exists():
        print("[WARN] .env.clconotify not found - skipping user ID / email write")
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
# .gitignore (project install only)
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

    if args.env_only and not args.project:
        print("[ERROR] --env-only requires --project DIR")
        sys.exit(1)

    scope, claude_dir, env_dir, hook_cmd_path = resolve_scope(args)

    print("clco-notify Setup")
    print("Scope:  " + scope + (" (env only)" if args.env_only else ""))
    print("Target: " + str(env_dir))
    print("-" * 40)

    if args.env_only:
        step_copy_env_project(env_dir)

        if args.user_id or args.email:
            step_set_user(env_dir, args.user_id, args.email)

        step_gitignore(Path(args.project).resolve())

        print("-" * 40)
        print("[DONE] Project env installed.")
        print()
        print("Next step:")
        print("  Edit " + str(env_dir / ".env.clconotify") + " and set SLACK_NOTIFY_PROJECT_NAME.")
        return

    python_cmd = resolve_python(args.python)

    if not step_copy_hook(claude_dir):
        sys.exit(1)

    ok = step_inject_settings(claude_dir, python_cmd, hook_cmd_path)
    if not ok:
        sys.exit(1)

    step_copy_env(env_dir)

    if args.user_id or args.email:
        step_set_user(env_dir, args.user_id, args.email)

    if scope == "project":
        step_gitignore(Path(args.project).resolve())

    print("-" * 40)
    print("[DONE] Setup complete.")
    print()
    print("Next steps:")
    print("  1. Edit " + str(env_dir / ".env.clconotify"))
    print("  2. Set SLACK_BOT_TOKEN=xoxb-...")
    if not args.user_id and not args.email:
        print("  3. Set SLACK_NOTIFY_USER_ID or SLACK_NOTIFY_USER_EMAIL")
    print()
    print("Test:")
    print('  echo \'{"hook_event_name":"Stop"}\' | ' + python_cmd + " " + hook_cmd_path)


if __name__ == "__main__":
    main()
