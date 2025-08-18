# cps/notifications/providers/discord.py
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode


class DISCORD:
    """
    Discord Notifications provider
    """
    
    KEY = "discord" 
    
    CONFIG_SCHEMA = [
        {
            "key": "webhook",
            "label": "Discord Webhook URL",
            "input_type": "url",
            "description": "Your Discord incoming webhook URL (we add ?wait=true automatically).",
            "required": True,
            "placeholder": "https://discord.com/api/webhooks/…",
        },
        {
            "key": "username",
            "label": "Discord Username",
            "input_type": "text",
            "description": "Optional override username (leave blank for webhook default).",
            "placeholder": "Optional",
        },
        {
            "key": "avatar",
            "label": "Discord Avatar URL",
            "input_type": "url",
            "description": "Optional avatar image URL (leave blank for webhook default).",
            "placeholder": "https://…",
        },
        {
            "key": "color",
            "label": "Discord Color (hex)",
            "input_type": "text",
            "description": "Hex color (e.g. #5865F2). (Not used in plain messages.)",
            "placeholder": "#5865F2",
        },
        {
            "key": "tts",
            "label": "Text-to-speech (if supported)",
            "input_type": "checkbox",
            "description": "Send the notification using text-to-speech.",
        },
    ]

    # ---------- Default values for the config keys above ----------
    _DEFAULT_CONFIG = {
        "webhook": "",
        "username": "",
        "avatar": "",
        "color": "",
        "tts": 0,
    }

    def __init__(self, config=None):
        cfg = dict(self._DEFAULT_CONFIG)
        if config:
            cfg.update(config)
        self.config = cfg
        

    def _field_name(self, key: str) -> str:
        """Builds provider-prefixed field names like 'discord_webhook' generically."""
        prefix = getattr(self, "KEY", None) or getattr(self, "NAME", None) or self.__class__.__name__
        return f"{prefix.lower()}_{key}"


    # ---------- UI options for the modal (derived from CONFIG_SCHEMA) ----------
    def _return_config_options(self):
        """
        Returns field descriptors consumed by the template.
        IMPORTANT: names must be <provider>_<key> so the JS prefill works.
        """
        opts = []
        for entry in self.CONFIG_SCHEMA:
            key = entry["key"]
            opts.append(
                {
                    "label": entry.get("label", key),
                    "value": self.config.get(key, self._DEFAULT_CONFIG.get(key, "")),
                    "name": self._field_name(key),  # <-- generic
                    "description": entry.get("description", ""),
                    "input_type": (entry.get("input_type") or "text"),
                    "required": bool(entry.get("required", False)),
                    "placeholder": entry.get("placeholder", ""),
                }
            )
        return opts


    def _with_wait_true(self, webhook: str) -> str:
        try:
            parts = urlsplit(webhook)
            q = dict(parse_qsl(parts.query, keep_blank_values=True))
            if "wait" not in q:
                q["wait"] = "true"
            new_query = urlencode(q)
            return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))
        except Exception:
            # If parsing fails, fall back to a simple append
            sep = "&" if "?" in webhook else "?"
            return f"{webhook}{sep}wait=true"

    def agent_notify(self, subject: str = "", body: str = "", action: str = "", **kwargs):
        webhook = (self.config.get("webhook") or "").strip()
        if not webhook:
            return {"ok": False, "error": "missing webhook"}

        webhook = self._with_wait_true(webhook)

        text = (
            f"{subject}\r\n{body}"
            if self.config.get("incl_subject")
            else (body or subject or "Notification")
        )
        payload = {"content": text}

        if self.config.get("username"):
            payload["username"] = self.config["username"]
        if self.config.get("avatar"):
            payload["avatar_url"] = self.config["avatar"]
        if self.config.get("tts"):
            payload["tts"] = True

        data = json.dumps(payload).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "User-Agent": "curl/8.5.0",
        }

        req = Request(webhook, data=data, headers=headers, method="POST")
        try:
            with urlopen(req, timeout=15) as resp:
                status = getattr(resp, "status", 204)
                ok = 200 <= status < 300 or status == 204
                # Discord may return a JSON body when wait=true; read but don't require it
                try:
                    body_bytes = resp.read()
                    resp_text = body_bytes.decode("utf-8", "ignore") if body_bytes else ""
                except Exception:
                    resp_text = ""
                return {"ok": ok, "status": status, "response": resp_text}
        except HTTPError as e:
            err = {"ok": False, "status": e.code, "error": f"HTTPError: {e}", "sent": payload}
            return err
        except URLError as e:
            return {"ok": False, "error": f"URLError: {e}", "sent": payload}
        except Exception as e:
            return {"ok": False, "error": str(e), "sent": payload}
