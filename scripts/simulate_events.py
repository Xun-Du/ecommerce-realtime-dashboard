"""Continuously append realistic ecommerce sessions to Supabase."""

from __future__ import annotations

import logging
import signal
import time
from datetime import UTC, datetime, timedelta
from random import SystemRandom

from sqlalchemy.exc import SQLAlchemyError

from backend.app.core.config import get_settings
from backend.app.core.database import initialize_database, write_batch
from scripts.data_generator import generate_batch

LOGGER = logging.getLogger(__name__)
RUNNING = True
# Keep the live stream visible without overwhelming the seeded historical trend.
BATCH_SIZE = 5


def stop(_: int, __: object) -> None:
    """Finish the current loop after SIGINT or SIGTERM."""
    global RUNNING
    RUNNING = False


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    initialize_database()
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    randomizer = SystemRandom()
    LOGGER.info(
        "事件模拟器已启动：每 %s 秒写入约 %s 名用户。",
        settings.simulator_interval_seconds,
        BATCH_SIZE,
    )

    while RUNNING:
        started_at = time.monotonic()
        now = datetime.now(UTC)
        batch = generate_batch(
            start_at=now - timedelta(minutes=5),
            end_at=now,
            user_count=BATCH_SIZE,
            seed=randomizer.randrange(1, 2**63),
            b_uplift=0.20,
        )
        try:
            write_batch(batch)
            LOGGER.info("写入批次：users=%s, events=%s", len(batch.users), len(batch.events))
        except SQLAlchemyError:
            LOGGER.exception("批次写入失败，事务已回滚；将在下一轮重试。")
        remaining = settings.simulator_interval_seconds - (time.monotonic() - started_at)
        if RUNNING and remaining > 0:
            time.sleep(remaining)
    LOGGER.info("事件模拟器已安全停止。")


if __name__ == "__main__":
    main()
