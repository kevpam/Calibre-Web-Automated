# cps/notifications/views.py
from flask import request, jsonify, g, abort
from flask_babel import gettext as _, lazy_gettext as _l

from cps.notifications import notifications_bp
from cps.notifications.registry import get_notifier, NOTIFIER_REGISTRY
from cps.notifications.providers import *  # ensures built-ins register

from cps.render_template import render_title_template
from cps import csrf

# CWA_DB import (works if scripts/ is present)
try:
    from cwa_db import CWA_DB
except Exception:
    from scripts.cwa_db import CWA_DB  # fallback


# ---------- Triggers ----------
NOTIFICATION_TRIGGERS = [
    {"key": "book_added",      "label": _l("Book Added")},
    {"key": "book_downloaded", "label": _l("Book Downloaded")},
    {"key": "book_deleted",    "label": _l("Book Deleted")},
]
TRIGGER_KEYS = {t["key"] for t in NOTIFICATION_TRIGGERS}


# ---------- DB lifecycle ----------
def get_db() -> CWA_DB:
    if "cwa_db" not in g:
        g.cwa_db = CWA_DB(verbose=False)
    return g.cwa_db


@notifications_bp.teardown_app_request
def _close_db(error=None):
    db = g.pop("cwa_db", None)
    if db and getattr(db, "con", None):
        try:
            db.con.close()
        except Exception:
            pass


# ---------- Fallback storage (SQLite via db.con) ----------
def _ensure_table(db: CWA_DB):
    sql = """
    CREATE TABLE IF NOT EXISTS notification_agents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        name TEXT,
        webhook TEXT,
        username TEXT,
        avatar TEXT,
        color TEXT,
        incl_subject INTEGER DEFAULT 0,
        tts INTEGER DEFAULT 0,
        enabled_triggers TEXT DEFAULT ''
    );
    """
    db.con.execute(sql)
    db.con.commit()


def _fallback_save(db: CWA_DB, provider: str, payload: dict) -> int:
    """
    Save or update a provider agent using a generic table.
    Expected payload keys (normalized already):
      type, id?, webhook, username, avatar, color, incl_subject, tts, enabled_triggers (list)
    """
    _ensure_table(db)

    enabled_csv = ",".join(payload.get("enabled_triggers", []))
    name = payload.get("name") or (payload.get("username") or provider.title())

    if payload.get("id"):
        # update
        db.con.execute(
            """UPDATE notification_agents
               SET type=?, name=?, webhook=?, username=?, avatar=?, color=?, incl_subject=?, tts=?, enabled_triggers=?
             WHERE id=?""",
            (
                provider,
                name,
                payload.get("webhook") or "",
                payload.get("username") or "",
                payload.get("avatar") or "",
                payload.get("color") or "",
                int(payload.get("incl_subject") or 0),
                int(payload.get("tts") or 0),
                enabled_csv,
                int(payload["id"]),
            ),
        )
        db.con.commit()
        return int(payload["id"])
    else:
        cur = db.con.execute(
            """INSERT INTO notification_agents
               (type, name, webhook, username, avatar, color, incl_subject, tts, enabled_triggers)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                provider,
                name,
                payload.get("webhook") or "",
                payload.get("username") or "",
                payload.get("avatar") or "",
                payload.get("color") or "",
                int(payload.get("incl_subject") or 0),
                int(payload.get("tts") or 0),
                enabled_csv,
            ),
        )
        db.con.commit()
        return int(cur.lastrowid)


def _fallback_list(db: CWA_DB):
    _ensure_table(db)
    rows = db.con.execute(
        "SELECT id, type, name, webhook, username, avatar, color, incl_subject, tts, enabled_triggers FROM notification_agents ORDER BY id ASC"
    ).fetchall()
    agents = []
    for r in rows:
        triggers = [t for t in (r[9] or "").split(",") if t]
        agents.append(
            {
                "id": r[0],
                "type": r[1],
                "name": r[2],
                "webhook": r[3],
                "username": r[4],
                "avatar": r[5],
                "color": r[6],
                "incl_subject": r[7],
                "tts": r[8],
                "enabled_triggers": triggers,
            }
        )
    return agents


def _fallback_delete(db: CWA_DB, agent_id: int):
    _ensure_table(db)
    db.con.execute("DELETE FROM notification_agents WHERE id=?", (agent_id,))
    db.con.commit()


# ---------- Template injection ----------
def _load_notification_agents():
    db = get_db()
    if hasattr(db, "notification_list"):
        try:
            return db.notification_list()
        except Exception:
            # fall through to internal table if their impl errors
            pass
    return _fallback_list(db)


@notifications_bp.app_context_processor
def inject_notification_context():
    return {
        "notification_agents": _load_notification_agents(),
        "notification_triggers": NOTIFICATION_TRIGGERS,
        "available_providers": sorted(NOTIFIER_REGISTRY.keys()),
    }


# ---------- Helpers ----------
def _options_from_class(provider: str, provided_cfg: dict | None = None):
    klass = get_notifier(provider)
    if not klass:
        return None, None
    defaults = getattr(klass, "_DEFAULT_CONFIG", {}) or {}
    cfg = {**defaults, **(provided_cfg or {})}
    obj = klass(cfg)
    options = obj._return_config_options()
    return cfg, options


def _strip_prefix(name: str, provider: str) -> str:
    p = f"{provider}_"
    return name[len(p):] if name.startswith(p) else name


def _normalize_payload(provider: str, raw: dict) -> dict:
    """Turn form/json input into a DB-friendly payload."""
    cfg, options = _options_from_class(provider)
    if options is None:
        return {}

    payload = {"type": provider}

    # Gather provider-specific fields (based on _return_config_options names)
    for opt in options:
        name = opt.get("name")
        if not name:
            continue
        it = (opt.get("input_type") or "text").lower()
        raw_val = raw.get(name)

        if it == "checkbox":
            val = 1 if str(raw_val).lower() in ("1", "true", "on", "yes") else 0
        else:
            val = (raw_val or "").strip()

        key = _strip_prefix(name, provider)  # e.g., discord_hook -> hook
        payload[key] = val

    # Triggers
    enabled = raw.get("enabled_triggers") or []
    if isinstance(enabled, str):
        enabled = [x.strip() for x in enabled.split(",") if x.strip()]
    payload["enabled_triggers"] = sorted({t for t in enabled if t in TRIGGER_KEYS})

    # Pass through id for updates (if client provided)
    if raw.get("id"):
        payload["id"] = raw.get("id")

    # Provider-specific remaps for DB compatibility
    if provider == "discord":
        # Expecting DB keys: webhook, username, avatar, color, incl_subject, tts
        if "hook" in payload:
            payload["webhook"] = payload.pop("hook")
        if "avatar_url" in payload:
            payload["avatar"] = payload.pop("avatar_url")

    return payload


def _save_agent(provider: str, payload: dict) -> int:
    db = get_db()

    # Prefer a provider-specific method if defined
    specific = f"notification_save_{provider}"
    if hasattr(db, specific):
        return getattr(db, specific)(payload)

    # Otherwise, fall back to a generic saver if available
    if hasattr(db, "notification_save_agent"):
        return getattr(db, "notification_save_agent")(provider, payload)

    # Last resort: internal SQLite table
    return _fallback_save(db, provider, payload)


# ---------- Routes ----------
@notifications_bp.route("/", methods=["GET"])
def notifications_page():
    return render_title_template(
        "notifications/index.html",
        title=_("Notifications"),
        page="cwa-notifications",
    )


@notifications_bp.route("/<provider>/modal", methods=["GET"])
def notifications_provider_modal(provider: str):
    if not get_notifier(provider):
        abort(404, description=f"Unknown provider '{provider}'")
    cfg, options = _options_from_class(provider)  # don't shadow gettext _
    return render_title_template(
        "notifications/modal.html",
        title=_("%(p)s Settings", p=get_notifier(provider).NAME),
        provider=provider,
        options=options,
    )


@notifications_bp.route("/save", methods=["POST"])
@csrf.exempt
def notifications_save():
    raw = request.get_json(silent=True) if request.is_json else request.form.to_dict(flat=True)
    raw = raw or {}
    provider = (raw.get("type") or raw.get("provider") or "").lower()
    if not provider or not get_notifier(provider):
        return jsonify(ok=False, error="unsupported provider"), 400

    normalized = _normalize_payload(provider, raw)

    bad = [k for k in normalized.get("enabled_triggers", []) if k not in TRIGGER_KEYS]
    if bad:
        return jsonify(ok=False, error=f"invalid triggers: {bad}"), 400

    try:
        agent_id = _save_agent(provider, normalized)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500

    return jsonify(ok=True, id=agent_id)


@notifications_bp.route("/test", methods=["POST"])
@csrf.exempt
def notifications_test():
    data = request.get_json(force=True, silent=False) or {}
    provider = (data.get("type") or data.get("provider") or "").lower()
    trigger = data.get("trigger") or ""
    if not provider or not get_notifier(provider):
        return jsonify(ok=False, error="unsupported or missing provider"), 400
    if trigger and trigger not in TRIGGER_KEYS:
        return jsonify(ok=False, error=f"invalid trigger: {trigger}"), 400
    # Stub success – wire real webhook send later if desired
    return jsonify(ok=True, provider=provider, trigger=trigger or None)


@notifications_bp.route("/delete", methods=["POST"])
@csrf.exempt
def notifications_delete():
    data = request.get_json(force=True, silent=False) or {}
    try:
        agent_id = int(data["id"])
    except (KeyError, ValueError, TypeError):
        return jsonify(ok=False, error="valid id required"), 400

    db = get_db()
    if hasattr(db, "notification_delete"):
        db.notification_delete(agent_id)
    else:
        _fallback_delete(db, agent_id)

    return jsonify(ok=True, deleted=agent_id)
