"""
Ping Gu - Main Application Entry Point
Gaming Readiness & Network Stability Monitor
Playfully themed around Pingu with Arctic Tuxedo styling.
"""

import sys
import customtkinter as ctk

from presets import load_app_fonts, load_user_config

load_app_fonts()

from ui_main import PingGuApp  # noqa: E402 (fonts must register first)


def main() -> None:
    theme = load_user_config().get("theme", "Dark")
    ctk.set_appearance_mode(theme if theme in ("Light", "Dark") else "Dark")
    ctk.set_default_color_theme("blue")

    app = PingGuApp()
    app.mainloop()


if __name__ == "__main__":
    main()
