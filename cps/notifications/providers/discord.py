# cps/notifications/providers/discord.py
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

class DISCORD:
    """
    Discord Notifications provider
    """

    NAME = "Discord"

    # Keep keys aligned with DB + UI prefill
    _DEFAULT_CONFIG = {
        "webhook": "",
        "username": "",
        "avatar": "",
        "color": "",
        "incl_subject": 0,
        "tts": 0,
    }

    def __init__(self, config=None):
        cfg = dict(self._DEFAULT_CONFIG)
        if config:
            cfg.update(config)
        self.config = cfg

    # ---------- UI options for the modal ----------
    def _return_config_options(self):
        """
        Returns field descriptors consumed by the template.
        IMPORTANT: names must be discord_<key> so the JS prefill works.
        """
        return [
            {
                "label": "Discord Webhook URL",
                "value": self.config.get("webhook", ""),
                "name": "discord_webhook",
                "description": "Your Discord incoming webhook URL (we add ?wait=true automatically).",
                "input_type": "text",
            },
            {
                "label": "Discord Username",
                "value": self.config.get("username", ""),
                "name": "discord_username",
                "description": "Optional override username (leave blank for webhook default).",
                "input_type": "text",
            },
            {
                "label": "Discord Avatar URL",
                "value": self.config.get("avatar", ""),
                "name": "discord_avatar",
                "description": "Optional avatar image URL (leave blank for webhook default).",
                "input_type": "text",
            },
            {
                "label": "Discord Color",
                "value": self.config.get("color", "") or "#5865F2",
                "name": "discord_color",
                "description": "Hex color (e.g. #5865F2). (Not used in plain messages.)",
                "input_type": "text",
            },
            {
                "label": "TTS",
                "value": 1 if self.config.get("tts") else 0,
                "name": "discord_tts",
                "description": "Send the notification using text-to-speech.",
                "input_type": "checkbox",
            },
        ]

    # ---------- Sending ----------
    def _with_wait_true(self, webhook: str) -> str:
        """
        Ensure the webhook URL includes wait=true (to mirror your working curl).
        """
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
        """
        Send a notification to Discord via webhook using the same shape as your curl test.
        """
        webhook = (self.config.get("webhook") or "").strip()
        if not webhook:
            return {"ok": False, "error": "missing webhook"}

        webhook = self._with_wait_true(webhook)

        # Build plain text payload. (Embeds/color can be added later if you want.)
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

        # Mimic curl request that worked for you
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
            # Surface what we actually attempted for fast debugging
            err = {"ok": False, "status": e.code, "error": f"HTTPError: {e}", "sent": payload}
            return err
        except URLError as e:
            return {"ok": False, "error": f"URLError: {e}", "sent": payload}
        except Exception as e:
            return {"ok": False, "error": str(e), "sent": payload}
