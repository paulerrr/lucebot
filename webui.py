"""Lucebot admin web UI.  Run: python webui.py  →  http://localhost:8080"""

import json
import os
import secrets as _secrets_mod
import sqlite3
from functools import wraps
from pathlib import Path

from dotenv import dotenv_values
from flask import Flask, flash, get_flashed_messages, redirect, request, session, url_for

ROOT        = Path(__file__).parent
ENV_PATH    = ROOT / ".env"
CONFIG_PATH = ROOT / "config.json"
SOCIAL_PATH = ROOT / "data" / "social_interactions"

# ── data helpers ──────────────────────────────────────────────────────────────
def read_env() -> dict:
    return dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}

def write_env(key: str, value: str):
    if not ENV_PATH.exists():
        ENV_PATH.touch()
    lines = ENV_PATH.read_text("utf-8").splitlines(keepends=True)
    new_line = f'{key}={value}\n'
    replaced = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}=") or line.startswith(f'export {key}='):
            lines[i] = new_line
            replaced = True
            break
    if not replaced:
        lines.append(new_line)
    ENV_PATH.write_text("".join(lines), "utf-8")

# ── app setup ─────────────────────────────────────────────────────────────────
app = Flask(__name__)

# Generate a stable session secret on first run and persist it in .env
_env0 = read_env()
_sk   = _env0.get("WEBUI_SECRET_KEY") or _secrets_mod.token_hex(32)
if not _env0.get("WEBUI_SECRET_KEY"):
    write_env("WEBUI_SECRET_KEY", _sk)
app.secret_key = _sk

def read_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text("utf-8"))
    except Exception:
        return {}

def save_config(data: dict):
    CONFIG_PATH.write_text(json.dumps(data, indent=2), "utf-8")

def read_file(path: Path) -> str:
    return path.read_text("utf-8") if path.exists() else ""

def write_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, "utf-8")

def _db_connect():
    db_path = ROOT / "data" / "messages.db"
    return sqlite3.connect(db_path) if db_path.exists() else None

def read_level_rewards() -> list[dict]:
    conn = _db_connect()
    if not conn:
        return []
    try:
        cur = conn.execute("SELECT guild_id, level, role_id FROM level_rewards ORDER BY level")
        return [{"guild_id": r[0], "level": r[1], "role_id": r[2]} for r in cur.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()

def add_level_reward(guild_id: int, level: int, role_id: int):
    conn = _db_connect()
    if not conn:
        raise RuntimeError("Database not found — has the bot started yet?")
    try:
        conn.execute(
            "INSERT INTO level_rewards (guild_id, level, role_id) VALUES (?, ?, ?)"
            " ON CONFLICT(guild_id, level) DO UPDATE SET role_id = ?",
            (guild_id, level, role_id, role_id),
        )
        conn.commit()
    finally:
        conn.close()

def remove_level_reward(guild_id: int, level: int):
    conn = _db_connect()
    if not conn:
        raise RuntimeError("Database not found")
    try:
        conn.execute(
            "DELETE FROM level_rewards WHERE guild_id = ? AND level = ?",
            (guild_id, level),
        )
        conn.commit()
    finally:
        conn.close()

def read_blocked() -> list:
    p = SOCIAL_PATH / "blocked_users.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text("utf-8")).get("blocked_users", [])
    except Exception:
        return []

def save_blocked(ids: list):
    SOCIAL_PATH.mkdir(parents=True, exist_ok=True)
    (SOCIAL_PATH / "blocked_users.json").write_text(
        json.dumps({"blocked_users": ids}, indent=2), "utf-8"
    )

def get_password() -> str:
    return read_env().get("WEBUI_PASSWORD") or "admin"

def login_required(f):
    @wraps(f)
    def _inner(*a, **kw):
        if not session.get("ok"):
            return redirect(url_for("login"))
        return f(*a, **kw)
    return _inner

# ── CSS ───────────────────────────────────────────────────────────────────────
CSS = """
:root {
  --bg:     #0d1117; --surface: #161b22; --card: #21262d;
  --border: #30363d; --text: #e6edf3;   --muted: #8b949e;
  --accent: #5865F2; --acc2:   #4752c4;
  --green:  #3fb950; --red:    #f85149; --input-bg: #0d1117;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: var(--bg); color: var(--text); min-height: 100vh;
  display: flex; flex-direction: column;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
code {
  background: var(--card); border: 1px solid var(--border);
  border-radius: 4px; padding: 1px 5px; font-size: .85em;
}
.topbar {
  background: var(--surface); border-bottom: 1px solid var(--border);
  padding: 12px 24px; display: flex; align-items: center; gap: 12px;
  position: sticky; top: 0; z-index: 10;
}
.topbar .logo { font-size: 1.1rem; font-weight: 700; }
.topbar .logo span { color: var(--accent); }
.topbar .logout { margin-left: auto; font-size: .875rem; color: var(--muted); }
.topbar .logout:hover { color: var(--text); text-decoration: none; }
.layout { display: flex; flex: 1; }
.sidebar {
  width: 210px; background: var(--surface);
  border-right: 1px solid var(--border); padding: 16px 8px; flex-shrink: 0;
}
.sidebar .sec-label {
  font-size: .7rem; font-weight: 600; letter-spacing: .08em; color: var(--muted);
  text-transform: uppercase; padding: 8px 12px 4px;
}
.sidebar a {
  display: block; padding: 8px 12px; border-radius: 6px;
  color: var(--muted); font-size: .875rem; transition: all .15s;
}
.sidebar a:hover { background: var(--card); color: var(--text); text-decoration: none; }
.sidebar a.active { background: var(--accent); color: #fff; }
.main { flex: 1; padding: 28px; max-width: 820px; }
h1 { font-size: 1.3rem; font-weight: 700; margin-bottom: 4px; }
.subtitle { color: var(--muted); font-size: .875rem; margin-bottom: 20px; }
.card {
  background: var(--card); border: 1px solid var(--border);
  border-radius: 8px; padding: 20px; margin-bottom: 16px;
}
.card h2 {
  font-size: .95rem; font-weight: 600; margin-bottom: 16px;
  padding-bottom: 10px; border-bottom: 1px solid var(--border);
}
.field { margin-bottom: 16px; }
.field:last-of-type { margin-bottom: 0; }
.field label {
  display: block; font-size: .75rem; font-weight: 600; color: var(--muted);
  margin-bottom: 6px; text-transform: uppercase; letter-spacing: .05em;
}
.field input[type=text],
.field input[type=password],
.field select,
.field textarea {
  width: 100%; background: var(--input-bg); border: 1px solid var(--border);
  border-radius: 6px; padding: 8px 12px; color: var(--text);
  font-size: .875rem; font-family: inherit; transition: border-color .15s;
}
.field select { appearance: none; cursor: pointer; }
.field input:focus, .field select:focus, .field textarea:focus { outline: none; border-color: var(--accent); }
.field .hint { font-size: .75rem; color: var(--muted); margin-top: 4px; }
.field textarea {
  resize: vertical; font-family: "SF Mono", Consolas, "Courier New", monospace;
  font-size: .8rem; line-height: 1.6;
}
.row { display: flex; gap: 12px; align-items: flex-end; }
.row .field { margin: 0; flex: 1; }
.btn {
  display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px;
  border-radius: 6px; border: none; cursor: pointer;
  font-size: .875rem; font-weight: 600; transition: all .15s; font-family: inherit;
}
.btn-primary { background: var(--accent); color: #fff; }
.btn-primary:hover { background: var(--acc2); }
.btn-danger  { background: var(--red); color: #fff; }
.btn-danger:hover { background: #c43e3c; }
.btn-sm { padding: 4px 10px; font-size: .75rem; }
.alert {
  padding: 10px 14px; border-radius: 6px; margin-bottom: 16px;
  font-size: .875rem; font-weight: 500;
}
.alert-success { background: #1c3829; border: 1px solid #3fb95040; color: var(--green); }
.alert-error   { background: #3c1c1c; border: 1px solid #f8514940; color: var(--red); }
.alert-info    { background: #1c2438; border: 1px solid #5865f240; color: var(--accent); }
.notice {
  background: #1c2438; border: 1px solid #5865f240; border-radius: 6px;
  padding: 10px 14px; font-size: .8rem; color: var(--muted); margin-bottom: 16px;
}
.badge {
  display: inline-block; padding: 1px 7px; border-radius: 10px;
  font-size: .7rem; font-weight: 600; margin-left: 6px;
}
.badge-set   { background: #1c3829; color: var(--green); }
.badge-unset { background: var(--card); color: var(--muted); border: 1px solid var(--border); }
table { width: 100%; border-collapse: collapse; font-size: .875rem; }
th {
  text-align: left; padding: 8px 12px; font-size: .75rem; font-weight: 600;
  color: var(--muted); text-transform: uppercase; letter-spacing: .04em;
  border-bottom: 1px solid var(--border);
}
td { padding: 10px 12px; border-bottom: 1px solid var(--border); vertical-align: middle; }
tr:last-child td { border-bottom: none; }
.empty { color: var(--muted); text-align: center; font-style: italic; }
.login-wrap {
  display: flex; align-items: center; justify-content: center;
  min-height: 100vh; background: var(--bg); padding: 24px;
}
.login-card {
  background: var(--card); border: 1px solid var(--border);
  border-radius: 12px; padding: 36px; width: 100%; max-width: 380px;
}
.login-title { text-align: center; font-size: 1.5rem; font-weight: 700; margin-bottom: 4px; }
.login-sub   { text-align: center; color: var(--muted); font-size: .875rem; margin-bottom: 28px; }
"""

# ── layout renderer ───────────────────────────────────────────────────────────
_NAV = [
    ("secrets",   "Secrets (.env)"),
    ("channels",  "Log Channels"),
    ("purgatory", "Purgatory"),
    ("leveling",  "Leveling"),
    ("blocked",   "Blocked Users"),
    ("messages",  "Social Messages"),
    ("reactions", "Reaction Roles"),
]

def _render(active: str, body: str) -> str:
    flashes = get_flashed_messages(with_categories=True)
    flash_html = ""
    for cat, msg in flashes:
        cls = {"success": "alert-success", "error": "alert-error"}.get(cat, "alert-info")
        flash_html += f'<div class="alert {cls}">{msg}</div>\n'

    nav_html = '<div class="sec-label">Management</div>\n'
    for key, label in _NAV:
        cls = " active" if active == key else ""
        nav_html += f'<a href="/{key}" class="{cls}">{label}</a>\n'

    return (
        f'<!DOCTYPE html><html lang="en"><head>'
        f'<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">'
        f'<title>Lucebot Admin</title><style>{CSS}</style></head><body>'
        f'<div class="topbar"><div class="logo">Luce<span>bot</span> Admin</div>'
        f'<form method="POST" action="/restart" style="margin-left:auto;margin-right:12px">'
        f'<button type="submit" class="btn btn-sm" style="background:var(--card);border:1px solid var(--border);color:var(--muted)">&#x21BA; Restart Bot</button>'
        f'</form>'
        f'<a class="logout" href="/logout">Log out</a></div>'
        f'<div class="layout"><nav class="sidebar">{nav_html}</nav>'
        f'<main class="main">{flash_html}{body}</main></div></body></html>'
    )

# ── login ─────────────────────────────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        if request.form.get("password") == get_password():
            session["ok"] = True
            return redirect(url_for("secrets"))
        error = '<div class="alert alert-error">Incorrect password.</div>'

    return (
        f'<!DOCTYPE html><html lang="en"><head>'
        f'<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">'
        f'<title>Lucebot Admin</title><style>{CSS}</style></head><body>'
        f'<div class="login-wrap"><div class="login-card">'
        f'<div class="login-title">&#x1F916; Lucebot</div>'
        f'<div class="login-sub">Admin Panel</div>'
        f'{error}'
        f'<form method="POST"><div class="field"><label>Password</label>'
        f'<input type="password" name="password" autofocus placeholder="Enter password"></div>'
        f'<br><button type="submit" class="btn btn-primary" style="width:100%">Sign in</button></form>'
        f'<div style="margin-top:16px;font-size:.75rem;color:var(--muted);text-align:center">'
        f'Default password: <code>admin</code><br>Change it under Secrets &rarr; Web UI Password'
        f'</div></div></div></body></html>'
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return redirect(url_for("secrets"))

# ── secrets ───────────────────────────────────────────────────────────────────
_ENV_FIELDS = [
    ("DISCORD_TOKEN",                "Discord Bot Token",         "password",
     "Required. From the Discord Developer Portal."),
    ("DISCORD_GUILD_ID",             "Guild ID",                  "text",
     "Optional. Speeds up slash command sync to this specific server."),
    ("DISCORD_PURGATORY_CHANNEL_ID", "Purgatory Channel ID",      "text",
     "Optional env override. Prefer <code>/purgatory-setup</code> in Discord."),
    ("DISCORD_PURGATORY_ROLE_ID",    "Purgatory Role ID",         "text",
     "Optional env override. Prefer <code>/purgatory-setup</code> in Discord."),
    ("DISCORD_LOG_CHANNEL_ID",       "Log Channel ID (fallback)", "text",
     "Optional. Used when no type-specific log channel is configured."),
    ("WEBUI_PASSWORD",               "Web UI Password",           "password",
     "Password for this admin panel. Default: <code>admin</code>"),
]

@app.route("/secrets", methods=["GET", "POST"])
@login_required
def secrets():
    if request.method == "POST":
        try:
            env = read_env()
            for key, _, ftype, _ in _ENV_FIELDS:
                val = request.form.get(key, "").strip()
                if ftype == "password" and not val:
                    continue
                if val != env.get(key, ""):
                    write_env(key, val)
            flash("Secrets saved. Restart the bot for changes to take effect.", "success")
        except Exception as exc:
            flash(f"Failed to save secrets: {exc}", "error")
        return redirect(url_for("secrets"))

    env = read_env()
    fields_html = ""
    for key, label, ftype, hint in _ENV_FIELDS:
        cur = env.get(key, "")
        badge = (
            f'<span class="badge badge-set">set</span>'
            if cur else
            f'<span class="badge badge-unset">not set</span>'
        )
        if ftype == "password":
            ph = "leave blank to keep current" if cur else "not set — enter a value"
            inp = f'<input type="password" name="{key}" autocomplete="off" placeholder="{ph}">'
        else:
            inp = f'<input type="text" name="{key}" value="{cur}">'
        fields_html += (
            f'<div class="field"><label>{label}{badge}</label>'
            f'{inp}<div class="hint">{hint}</div></div>'
        )

    body = (
        f'<h1>Secrets</h1>'
        f'<p class="subtitle">Environment variables written to <code>.env</code></p>'
        f'<div class="notice">&#x1F504; Changes require a <strong>bot restart</strong> to take effect. '
        f'Password fields are not pre-filled &mdash; leave blank to keep the current value.</div>'
        f'<form method="POST"><div class="card">'
        f'<h2>Discord &amp; Panel Configuration</h2>{fields_html}</div>'
        f'<button type="submit" class="btn btn-primary">Save secrets</button></form>'
    )
    return _render("secrets", body)

# ── log channels ──────────────────────────────────────────────────────────────
@app.route("/channels", methods=["GET", "POST"])
@login_required
def channels():
    if request.method == "POST":
        cfg = read_config()
        for key in ("log_channel_id", "message_log_channel_id", "member_log_channel_id"):
            val = request.form.get(key, "").strip()
            if val.isdigit():
                cfg[key] = int(val)
            elif not val and key in cfg:
                del cfg[key]
        save_config(cfg)
        flash("Log channels saved. Restart the bot for changes to take effect.", "success")
        return redirect(url_for("channels"))

    cfg = read_config()

    def _ch(key, label, hint):
        val = cfg.get(key, "")
        return (
            f'<div class="field"><label>{label}</label>'
            f'<input type="text" name="{key}" value="{val}" placeholder="Channel ID (blank to unset)">'
            f'<div class="hint">{hint}</div></div>'
        )

    body = (
        f'<h1>Log Channels</h1>'
        f'<p class="subtitle">Configure which channels receive each category of log events</p>'
        f'<div class="notice">Any category without a dedicated channel falls back to the Join/Leave channel.</div>'
        f'<form method="POST"><div class="card"><h2>Channel IDs</h2>'
        + _ch("log_channel_id",         "Join / Leave Channel",
              "Member joined and member left events. Also the fallback for other log types.")
        + _ch("message_log_channel_id", "Message Channel",
              "Message deleted, edited, bulk purge, and invite links posted.")
        + _ch("member_log_channel_id",  "Member Channel",
              "Role changes, nickname changes, bans, unbans, and timeouts.")
        + '</div><button type="submit" class="btn btn-primary">Save channels</button></form>'
    )
    return _render("channels", body)

# ── purgatory ─────────────────────────────────────────────────────────────────
@app.route("/purgatory", methods=["GET", "POST"])
@login_required
def purgatory():
    if request.method == "POST":
        cfg = read_config()
        for key in ("purgatory_channel_id", "purgatory_role_id"):
            val = request.form.get(key, "").strip()
            if val.isdigit():
                cfg[key] = int(val)
            elif not val and key in cfg:
                del cfg[key]
        save_config(cfg)
        flash("Purgatory config saved. Restart the bot for changes to take effect.", "success")
        return redirect(url_for("purgatory"))

    cfg = read_config()

    def _pf(key, label, hint):
        val = cfg.get(key, "")
        return (
            f'<div class="field"><label>{label}</label>'
            f'<input type="text" name="{key}" value="{val}" placeholder="ID (blank to unset)">'
            f'<div class="hint">{hint}</div></div>'
        )

    body = (
        f'<h1>Purgatory</h1>'
        f'<p class="subtitle">New member verification system configuration</p>'
        f'<div class="notice">&#x1F4A1; You can also run <code>/purgatory-setup</code> in Discord '
        f'to auto-create the channel and role.</div>'
        f'<form method="POST"><div class="card"><h2>IDs</h2>'
        + _pf("purgatory_channel_id", "Purgatory Channel ID",
              "The channel where new members answer verification questions.")
        + _pf("purgatory_role_id",    "Purgatory Role ID",
              "The role assigned to new members, restricting their server access.")
        + '</div><button type="submit" class="btn btn-primary">Save purgatory config</button></form>'
    )
    return _render("purgatory", body)

# ── blocked users ─────────────────────────────────────────────────────────────
@app.route("/blocked", methods=["GET", "POST"])
@login_required
def blocked():
    if request.method == "POST":
        action = request.form.get("action")
        uid_str = request.form.get("user_id", "").strip()
        if action == "add":
            if uid_str.isdigit():
                ids = read_blocked()
                uid_int = int(uid_str)
                if uid_int not in ids:
                    ids.append(uid_int)
                    save_blocked(ids)
                    flash(f"User {uid_str} blocked.", "success")
                else:
                    flash(f"User {uid_str} is already blocked.", "info")
            else:
                flash("Enter a valid Discord user ID (numbers only).", "error")
        elif action == "remove" and uid_str.isdigit():
            uid_int = int(uid_str)
            ids = read_blocked()
            if uid_int in ids:
                ids.remove(uid_int)
                save_blocked(ids)
                flash(f"User {uid_int} unblocked.", "success")
        return redirect(url_for("blocked"))

    ids = read_blocked()
    rows = ""
    for uid in ids:
        rows += (
            f'<tr><td><code>{uid}</code></td><td>'
            f'<form method="POST" style="display:inline">'
            f'<input type="hidden" name="action" value="remove">'
            f'<input type="hidden" name="user_id" value="{uid}">'
            f'<button type="submit" class="btn btn-danger btn-sm">Remove</button>'
            f'</form></td></tr>'
        )
    if not rows:
        rows = '<tr><td colspan="2" class="empty">No blocked users</td></tr>'

    body = (
        f'<h1>Blocked Users</h1>'
        f'<p class="subtitle">Users blocked from <code>!compliment</code> and <code>!insult</code></p>'
        f'<div class="notice">&#x1F504; Changes take effect after a bot restart (the bot loads this list at startup).</div>'
        f'<div class="card"><h2>Block a User</h2>'
        f'<form method="POST"><input type="hidden" name="action" value="add">'
        f'<div class="row"><div class="field"><label>Discord User ID</label>'
        f'<input type="text" name="user_id" placeholder="e.g. 123456789012345678"></div>'
        f'<button type="submit" class="btn btn-primary" style="flex-shrink:0">Block user</button>'
        f'</div></form></div>'
        f'<div class="card"><h2>Blocked Users ({len(ids)})</h2>'
        f'<table><thead><tr><th>User ID</th><th style="width:100px">Action</th></tr></thead>'
        f'<tbody>{rows}</tbody></table></div>'
    )
    return _render("blocked", body)

# ── social messages ───────────────────────────────────────────────────────────
@app.route("/messages", methods=["GET", "POST"])
@login_required
def messages():
    if request.method == "POST":
        tab      = request.form.get("tab", "compliments")
        content  = request.form.get("content", "")
        filename = "compliments.md" if tab == "compliments" else "insults.md"
        write_file(SOCIAL_PATH / filename, content)
        label = "Compliments" if tab == "compliments" else "Insults"
        flash(
            f"{label} saved. Run <code>!reload_messages</code> in Discord or restart the bot.",
            "success",
        )
        return redirect(url_for("messages"))

    compliments = read_file(SOCIAL_PATH / "compliments.md")
    insults     = read_file(SOCIAL_PATH / "insults.md")
    c_count     = sum(1 for l in compliments.splitlines() if l.strip())
    i_count     = sum(1 for l in insults.splitlines() if l.strip())

    def _section(tab, label, count, content):
        return (
            f'<div class="card"><h2>{label} '
            f'<span style="color:var(--muted);font-weight:400;font-size:.85rem">({count} messages)</span></h2>'
            f'<form method="POST"><input type="hidden" name="tab" value="{tab}">'
            f'<div class="field"><textarea name="content" rows="12">{content}</textarea></div>'
            f'<button type="submit" class="btn btn-primary">Save {label.lower()}</button>'
            f'</form></div>'
        )

    body = (
        f'<h1>Social Messages</h1>'
        f'<p class="subtitle">Edit the compliment and insult message pools</p>'
        f'<div class="notice">One message per line. '
        f'Use <code>!reload_messages</code> in Discord to apply changes without restarting.</div>'
        + _section("compliments", "Compliments", c_count, compliments)
        + _section("insults",     "Insults",     i_count, insults)
    )
    return _render("messages", body)

# ── reaction roles (read-only) ────────────────────────────────────────────────
@app.route("/reactions")
@login_required
def reactions():
    cfg = read_config()
    rr  = cfg.get("reaction_roles", {})

    if not rr:
        content = '<p class="empty" style="padding:16px 0">No reaction role messages configured yet.</p>'
    else:
        rows = ""
        for msg_id, mapping in rr.items():
            pairs = " &nbsp;|&nbsp; ".join(
                f"{emoji} &rarr; <code>{role_id}</code>"
                for emoji, role_id in mapping.items()
            )
            rows += f"<tr><td><code>{msg_id}</code></td><td>{pairs}</td></tr>"
        content = (
            f'<table><thead><tr><th>Message ID</th><th>Emoji &rarr; Role ID</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>'
        )

    body = (
        f'<h1>Reaction Roles</h1>'
        f'<p class="subtitle">Active reaction role configurations (read-only &mdash; manage via Discord)</p>'
        f'<div class="card"><h2>Configured Messages ({len(rr)})</h2>{content}</div>'
        f'<div class="notice">Manage via Discord: '
        f'<code>/reaction-role-setup</code> &nbsp; <code>/reaction-role-add</code> '
        f'&nbsp; <code>/reaction-role-remove</code></div>'
    )
    return _render("reactions", body)

# ── restart ───────────────────────────────────────────────────────────────────
RESTART_FLAG = ROOT / "data" / ".bot_restart"

@app.route("/restart", methods=["POST"])
@login_required
def restart():
    try:
        RESTART_FLAG.parent.mkdir(parents=True, exist_ok=True)
        RESTART_FLAG.touch()
        flash("Restart signal sent — the bot will reconnect in a few seconds.", "success")
    except Exception as exc:
        flash(f"Failed to send restart signal: {exc}", "error")
    return redirect(request.referrer or url_for("secrets"))


# ── leveling ──────────────────────────────────────────────────────────────────
@app.route("/leveling", methods=["GET", "POST"])
@login_required
def leveling():
    if request.method == "POST":
        action = request.form.get("action", "settings")
        cfg = read_config()

        if action == "settings":
            cfg["leveling_enabled"] = request.form.get("leveling_enabled") == "true"
            cfg["leveling_stack_rewards"] = request.form.get("leveling_stack_rewards") == "true"

            for key in ("leveling_xp_min", "leveling_xp_max"):
                val = request.form.get(key, "").strip()
                if val.isdigit():
                    cfg[key] = int(val)

            mode = request.form.get("leveling_notify_mode", "current")
            if mode in ("current", "dm", "channel", "off"):
                cfg["leveling_notify_mode"] = mode

            ch_val = request.form.get("leveling_notify_channel_id", "").strip()
            if ch_val.isdigit():
                cfg["leveling_notify_channel_id"] = int(ch_val)
            elif not ch_val:
                cfg.pop("leveling_notify_channel_id", None)

            save_config(cfg)
            flash("Leveling settings saved.", "success")

        elif action == "add_ignored_channel":
            val = request.form.get("channel_id", "").strip()
            if val.isdigit():
                ignored = cfg.get("leveling_ignored_channels", [])
                if int(val) not in ignored:
                    ignored.append(int(val))
                    cfg["leveling_ignored_channels"] = ignored
                    save_config(cfg)
                    flash(f"Channel {val} added to ignore list.", "success")
                else:
                    flash(f"Channel {val} is already ignored.", "info")
            else:
                flash("Enter a valid channel ID.", "error")

        elif action == "remove_ignored_channel":
            val = request.form.get("channel_id", "").strip()
            if val.isdigit():
                ignored = cfg.get("leveling_ignored_channels", [])
                if int(val) in ignored:
                    ignored.remove(int(val))
                    cfg["leveling_ignored_channels"] = ignored
                    save_config(cfg)
                    flash(f"Channel {val} removed.", "success")

        elif action == "add_ignored_role":
            val = request.form.get("role_id", "").strip()
            if val.isdigit():
                ignored = cfg.get("leveling_ignored_roles", [])
                if int(val) not in ignored:
                    ignored.append(int(val))
                    cfg["leveling_ignored_roles"] = ignored
                    save_config(cfg)
                    flash(f"Role {val} added to ignore list.", "success")
                else:
                    flash(f"Role {val} is already ignored.", "info")
            else:
                flash("Enter a valid role ID.", "error")

        elif action == "remove_ignored_role":
            val = request.form.get("role_id", "").strip()
            if val.isdigit():
                ignored = cfg.get("leveling_ignored_roles", [])
                if int(val) in ignored:
                    ignored.remove(int(val))
                    cfg["leveling_ignored_roles"] = ignored
                    save_config(cfg)
                    flash(f"Role {val} removed.", "success")

        elif action == "add_reward":
            env = read_env()
            guild_id_str = env.get("DISCORD_GUILD_ID", "").strip()
            if not guild_id_str.isdigit():
                flash("Guild ID is not set in Secrets — required to add level rewards.", "error")
            else:
                lvl = request.form.get("reward_level", "").strip()
                role = request.form.get("reward_role_id", "").strip()
                if lvl.isdigit() and role.isdigit() and int(lvl) >= 1:
                    try:
                        add_level_reward(int(guild_id_str), int(lvl), int(role))
                        flash(f"Reward added: Level {lvl} → Role {role}.", "success")
                    except Exception as e:
                        flash(f"Failed to add reward: {e}", "error")
                else:
                    flash("Enter a valid level (≥ 1) and role ID.", "error")

        elif action == "remove_reward":
            env = read_env()
            guild_id_str = env.get("DISCORD_GUILD_ID", "").strip()
            lvl = request.form.get("reward_level", "").strip()
            if guild_id_str.isdigit() and lvl.isdigit():
                try:
                    remove_level_reward(int(guild_id_str), int(lvl))
                    flash(f"Reward for Level {lvl} removed.", "success")
                except Exception as e:
                    flash(f"Failed to remove reward: {e}", "error")

        return redirect(url_for("leveling"))

    cfg = read_config()

    enabled      = cfg.get("leveling_enabled", True)
    xp_min       = cfg.get("leveling_xp_min", 15)
    xp_max       = cfg.get("leveling_xp_max", 25)
    stack        = cfg.get("leveling_stack_rewards", True)
    notify_mode  = cfg.get("leveling_notify_mode", "current")
    notify_ch_id = cfg.get("leveling_notify_channel_id", "")
    ign_channels = cfg.get("leveling_ignored_channels", [])
    ign_roles    = cfg.get("leveling_ignored_roles", [])
    rewards      = read_level_rewards()

    def _sel(name, current, options):
        opts = "".join(
            f'<option value="{v}"{"selected" if str(v) == str(current) else ""}>{label}</option>'
            for v, label in options
        )
        return f'<select name="{name}">{opts}</select>'

    # ── XP Settings card ──────────────────────────────────────────────────────
    settings_card = (
        '<div class="card"><h2>XP Settings</h2>'
        '<form method="POST"><input type="hidden" name="action" value="settings">'
        '<div class="field"><label>Leveling Enabled</label>'
        + _sel("leveling_enabled", str(enabled).lower(), [("true", "Enabled"), ("false", "Disabled")])
        + '</div>'
        '<div class="row">'
        '<div class="field"><label>XP Min (per message)</label>'
        f'<input type="text" name="leveling_xp_min" value="{xp_min}">'
        '</div>'
        '<div class="field"><label>XP Max (per message)</label>'
        f'<input type="text" name="leveling_xp_max" value="{xp_max}">'
        '</div></div>'
        '<div class="field"><label>Stack Role Rewards</label>'
        + _sel("leveling_stack_rewards", str(stack).lower(), [
            ("true",  "Stack — keep all earned rewards"),
            ("false", "Replace — only the highest reward"),
        ])
        + '<div class="hint">Stack: members keep every role they unlock. '
        'Replace: only the role for their current highest level is kept.</div></div>'
        '<div class="field"><label>Level-Up Notification</label>'
        + _sel("leveling_notify_mode", notify_mode, [
            ("current", "Current channel (where the message was sent)"),
            ("dm",      "DM the user"),
            ("channel", "Specific channel"),
            ("off",     "Off — no notifications"),
        ])
        + '</div>'
        '<div class="field"><label>Notification Channel ID</label>'
        f'<input type="text" name="leveling_notify_channel_id" value="{notify_ch_id}" placeholder="Only used when mode is \'Specific channel\'">'
        '</div>'
        '<button type="submit" class="btn btn-primary">Save settings</button>'
        '</form></div>'
    )

    # ── Level Rewards card ────────────────────────────────────────────────────
    reward_rows = ""
    for r in rewards:
        reward_rows += (
            f'<tr><td><strong>{r["level"]}</strong></td>'
            f'<td><code>{r["role_id"]}</code></td>'
            f'<td><form method="POST" style="display:inline">'
            f'<input type="hidden" name="action" value="remove_reward">'
            f'<input type="hidden" name="reward_level" value="{r["level"]}">'
            f'<button type="submit" class="btn btn-danger btn-sm">Remove</button>'
            f'</form></td></tr>'
        )
    if not reward_rows:
        reward_rows = '<tr><td colspan="3" class="empty">No level rewards configured</td></tr>'

    rewards_card = (
        '<div class="card"><h2>Level Rewards</h2>'
        '<form method="POST"><input type="hidden" name="action" value="add_reward">'
        '<div class="row">'
        '<div class="field"><label>Level</label>'
        '<input type="text" name="reward_level" placeholder="e.g. 5"></div>'
        '<div class="field"><label>Role ID</label>'
        '<input type="text" name="reward_role_id" placeholder="e.g. 123456789012345678"></div>'
        '<button type="submit" class="btn btn-primary" style="flex-shrink:0">Add reward</button>'
        '</div></form>'
        '<div class="hint" style="margin-bottom:14px">Guild ID must be set in Secrets for add/remove to work.</div>'
        '<table><thead><tr><th>Level</th><th>Role ID</th><th style="width:100px">Action</th></tr></thead>'
        f'<tbody>{reward_rows}</tbody></table></div>'
    )

    # ── Ignored Channels card ─────────────────────────────────────────────────
    ign_ch_rows = ""
    for ch_id in ign_channels:
        ign_ch_rows += (
            f'<tr><td><code>{ch_id}</code></td><td>'
            f'<form method="POST" style="display:inline">'
            f'<input type="hidden" name="action" value="remove_ignored_channel">'
            f'<input type="hidden" name="channel_id" value="{ch_id}">'
            f'<button type="submit" class="btn btn-danger btn-sm">Remove</button>'
            f'</form></td></tr>'
        )
    if not ign_ch_rows:
        ign_ch_rows = '<tr><td colspan="2" class="empty">No channels ignored</td></tr>'

    ignored_ch_card = (
        '<div class="card"><h2>Ignored Channels</h2>'
        '<p class="hint" style="margin-bottom:14px">Messages in these channels earn no XP.</p>'
        '<form method="POST"><input type="hidden" name="action" value="add_ignored_channel">'
        '<div class="row">'
        '<div class="field"><label>Channel ID</label>'
        '<input type="text" name="channel_id" placeholder="e.g. 123456789012345678"></div>'
        '<button type="submit" class="btn btn-primary" style="flex-shrink:0">Ignore channel</button>'
        '</div></form><br>'
        '<table><thead><tr><th>Channel ID</th><th style="width:100px">Action</th></tr></thead>'
        f'<tbody>{ign_ch_rows}</tbody></table></div>'
    )

    # ── Ignored Roles card ────────────────────────────────────────────────────
    ign_role_rows = ""
    for role_id in ign_roles:
        ign_role_rows += (
            f'<tr><td><code>{role_id}</code></td><td>'
            f'<form method="POST" style="display:inline">'
            f'<input type="hidden" name="action" value="remove_ignored_role">'
            f'<input type="hidden" name="role_id" value="{role_id}">'
            f'<button type="submit" class="btn btn-danger btn-sm">Remove</button>'
            f'</form></td></tr>'
        )
    if not ign_role_rows:
        ign_role_rows = '<tr><td colspan="2" class="empty">No roles ignored</td></tr>'

    ignored_role_card = (
        '<div class="card"><h2>Ignored Roles</h2>'
        '<p class="hint" style="margin-bottom:14px">Members with any of these roles earn no XP.</p>'
        '<form method="POST"><input type="hidden" name="action" value="add_ignored_role">'
        '<div class="row">'
        '<div class="field"><label>Role ID</label>'
        '<input type="text" name="role_id" placeholder="e.g. 123456789012345678"></div>'
        '<button type="submit" class="btn btn-primary" style="flex-shrink:0">Ignore role</button>'
        '</div></form><br>'
        '<table><thead><tr><th>Role ID</th><th style="width:100px">Action</th></tr></thead>'
        f'<tbody>{ign_role_rows}</tbody></table></div>'
    )

    body = (
        '<h1>Leveling</h1>'
        '<p class="subtitle">XP, level-up notifications, role rewards, and channel/role exceptions</p>'
        + settings_card + rewards_card + ignored_ch_card + ignored_role_card
    )
    return _render("leveling", body)


# ── entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("WEBUI_PORT", "8765"))
    print(f"\n  Lucebot Admin  →  http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
