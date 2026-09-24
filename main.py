import os
import time
import logging
import threading
from logging.handlers import RotatingFileHandler

from app.core.bot import bot
from app.core.database import init_db

# This import registers all the handlers automatically
import app.handlers  # noqa: F401 (Registers the bot handlers)

_START_TIME = time.monotonic()
logger = logging.getLogger(__name__)


def _setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            RotatingFileHandler("bot.log", maxBytes=2_000_000, backupCount=3),
            logging.StreamHandler(),
        ],
    )


def _health_thread():
    while True:
        time.sleep(3600)
        try:
            rss_kb = None
            with open(f"/proc/{os.getpid()}/status") as f:
                for line in f:
                    if line.startswith("VmRSS"):
                        rss_kb = int(line.split()[1])
                        break
            uptime_s = int(time.monotonic() - _START_TIME)
            logger.info(
                f"[health] rss={rss_kb}KB "
                f"threads={threading.active_count()} "
                f"uptime={uptime_s}s"
            )
        except Exception as e:
            logger.warning(f"[health] Failed to read process stats: {e}")


def main():
    _setup_logging()
    init_db()

    threading.Thread(target=_health_thread, daemon=True).start()

    logger.info(f"Bot started. PID={os.getpid()}")

    bot.infinity_polling(timeout=20, long_polling_timeout=15)


if __name__ == "__main__":
    main()
