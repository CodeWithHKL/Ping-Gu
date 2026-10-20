"""
Ping Gu - Main Application Entry Point
Gaming Readiness & Network Stability Monitor
Playfully themed around Pingu with Arctic Tuxedo styling.
"""

import sys
import customtkinter as ctk

from ui_main import PingGuApp


def main() -> None:
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")

    app = PingGuApp()
    app.mainloop()


if __name__ == "__main__":
    main()
