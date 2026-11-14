import asyncio
import signal
from app.config import settings
from app.core.logging import logger, setup_logging


class Worker:
    def __init__(self):
        self._running = True

    def stop(self):
        logger.info("worker_stopping")
        self._running = False

    async def outbox_dispatcher_loop(self):
        """Poll and dispatch queued notifications from outbox table."""
        while self._running:
            try:
                # Dispatcher logic will be filled in Milestone 6
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("outbox_dispatcher_error", error=str(e))
                await asyncio.sleep(5)

    async def day_close_sweeper_loop(self):
        """End-of-day dose closure sweeper running every 5 minutes."""
        while self._running:
            try:
                # Sweeper logic will be filled in Milestone 4
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("day_close_sweeper_error", error=str(e))
                await asyncio.sleep(60)

    async def run(self):
        setup_logging()
        logger.info("aira_worker_started", env=settings.APP_ENV)

        tasks = [
            asyncio.create_task(self.outbox_dispatcher_loop()),
            asyncio.create_task(self.day_close_sweeper_loop()),
        ]

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass
        finally:
            logger.info("aira_worker_exited")


def main():
    worker = Worker()

    def handle_signal():
        worker.stop()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(worker.run())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
