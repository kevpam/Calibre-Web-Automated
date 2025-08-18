# cps/notifications/providers/discord.py

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
        # merge defaults with whatever is loaded
        cfg = dict(self._DEFAULT_CONFIG)
        if config:
            cfg.update(config)
        self.config = cfg

    def agent_notify(self, subject="", body="", action="", **kwargs):
        """Send a notification (stub right now)."""
        text = f"{subject}\r\n{body}" if self.config.get("incl_subject") else body
        data = {
            "content": text,
        }
        if self.config.get("username"):
            data["username"] = self.config["username"]
        if self.config.get("avatar"):
            data["avatar_url"] = self.config["avatar"]
        if self.config.get("tts"):
            data["tts"] = True

        # TODO: actually send HTTP POST to webhook URL
        return {"ok": True, "prepared": True, "data": data}

    def _return_config_options(self):
        """
        Returns field descriptors consumed by the template.
        IMPORTANT: names must be discord_<key> so JS prefill works.
        """
        return [
            {
                "label": "Discord Webhook URL",
                "value": self.config.get("webhook", ""),
                "name": "discord_webhook",
                "description": "Your Discord incoming webhook URL.",
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
                "label": "Discord Avatar",
                "value": self.config.get("avatar", ""),
                "name": "discord_avatar",
                "description": "Optional avatar image URL (leave blank for webhook default).",
                "input_type": "text",
            },
            {
                "label": "Discord Color",
                "value": self.config.get("color", "") or "#5865F2",
                "name": "discord_color",
                "description": "Hex color (e.g. #5865F2).",
                "input_type": "text",
            },
            {
                "label": "Include Subject",
                "value": 1 if self.config.get("incl_subject") else 0,
                "name": "discord_incl_subject",
                "description": "Prefix message body with the subject line.",
                "input_type": "checkbox",
            },
            {
                "label": "TTS",
                "value": 1 if self.config.get("tts") else 0,
                "name": "discord_tts",
                "description": "Send the notification using text-to-speech.",
                "input_type": "checkbox",
            },
        ]
