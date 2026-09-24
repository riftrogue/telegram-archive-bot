import time
import logging
import threading

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Delayed message deletion
# ---------------------------------------------------------------------------

def delete_after(bot, chat_id: int, message_id: int, delay: int) -> None:
    """
    Delete a Telegram message after `delay` seconds.

    For delay=0, deletes immediately (inline, no thread).
    For delay>0, fires a daemon thread so the caller is not blocked.
    Failures are silently ignored — these are cosmetic cleanups only.
    """
    def _delete():
        try:
            bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception:
            pass  # message may already be gone; not an error worth logging

    if delay == 0:
        _delete()
    else:
        t = threading.Timer(delay, _delete)
        t.daemon = True
        t.start()


# ---------------------------------------------------------------------------
# Database retry helper
# ---------------------------------------------------------------------------

def db_retry(fn, *args, **kwargs):
    """
    Call fn(*args, **kwargs). If it raises, wait 1 second and try once more.
    If the second attempt also raises, the exception propagates to the caller.

    Only use this for operations that are known to be idempotent
    (UPDATE, DELETE, and UPSERT). Do not use for plain INSERT.
    """
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        logger.warning(f"DB call failed ({fn.__name__}), retrying once: {e}")
        time.sleep(1)
        return fn(*args, **kwargs)
