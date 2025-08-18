class DISCORD:
    """
    Minimal provider class.
    Exposes:
      - NAME
      - _DEFAULT_CONFIG
      - _return_config_options()
    """
    NAME = "Discord"
    _DEFAULT_CONFIG = {
        "hook": "",
        "username": "",
        "avatar_url": "",
        "color": "#5865F2",
        "tts": 0,
        "incl_subject": 0,
    }

    def __init__(self, config=None):
        self.config = {**self._DEFAULT_CONFIG, **(config or {})}

    def _return_config_options(self):
        return [
            {
                "label": "Discord Webhook URL",
                "value": self.config.get("hook", ""),
                "name": "discord_hook",
                "description": "Your Discord incoming webhook URL.",
                "input_type": "text",
            },
            {
                "label": "Discord Username",
                "value": self.config.get("username", ""),
                "name": "discord_username",
                "description": "Optional username override.",
                "input_type": "text",
            },
            {
                "label": "Discord Avatar URL",
                "value": self.config.get("avatar_url", ""),
                "name": "discord_avatar_url",
                "description": "Optional avatar image URL.",
                "input_type": "text",
            },
            {
                "label": "Discord Color",
                "value": self.config.get("color", ""),
                "name": "discord_color",
                "description": "Hex color starting with '#'.",
                "input_type": "text",
            },
            {
                "label": "Include Subject",
                "value": self.config.get("incl_subject", 0),
                "name": "discord_incl_subject",
                "description": "Prefix message body with subject.",
                "input_type": "checkbox",
            },
            {
                "label": "TTS",
                "value": self.config.get("tts", 0),
                "name": "discord_tts",
                "description": "Send notification using text-to-speech.",
                "input_type": "checkbox",
            },
        ]
