"""
Application configuration — loads settings from .env file.

All environment variables are validated at startup. The app will fail fast
with a clear error if required variables are missing.
"""

import os
from dotenv import load_dotenv

# Load .env from project root
load_dotenv()


class Settings:
    """Central configuration loaded from environment variables."""

    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

    def validate(self) -> None:
        """Ensure all required settings are present."""
        if not self.ANTHROPIC_API_KEY:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. "
                "Copy .env.example to .env and add your API key."
            )


settings = Settings()
