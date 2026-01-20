"""Entry point for the Discord-Obsidian agent."""

import asyncio
import logging
import signal
import sys
from typing import Optional

from src.config.settings import get_settings
from src.bot.client import ObsidianBot


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


class GracefulExit(SystemExit):
    """Exception for graceful shutdown."""

    pass


def setup_signal_handlers(bot: ObsidianBot) -> None:
    """Set up signal handlers for graceful shutdown.

    Args:
        bot: The bot instance to close on shutdown.
    """

    def signal_handler(signum: int, frame) -> None:
        logger.info(f"Received signal {signum}, initiating shutdown...")
        raise GracefulExit()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def main() -> None:
    """Main entry point."""
    logger.info("Starting Discord-Obsidian agent...")

    try:
        settings = get_settings()
    except Exception as e:
        logger.error(f"Failed to load settings: {e}")
        logger.error("Make sure .env file exists with all required variables.")
        sys.exit(1)

    bot = ObsidianBot(settings)
    setup_signal_handlers(bot)

    try:
        logger.info("Connecting to Discord...")
        await bot.start(settings.discord_token)
    except GracefulExit:
        logger.info("Shutting down gracefully...")
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)
    finally:
        if not bot.is_closed():
            await bot.close()
        logger.info("Bot shutdown complete.")


def run() -> None:
    """Run the bot."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")


if __name__ == "__main__":
    run()
