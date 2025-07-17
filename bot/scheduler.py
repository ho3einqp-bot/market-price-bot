from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta
from .bot_handler import PriceBot
from config.settings import CONFIG
from config.logging_config import logger
import asyncio

class SchedulerManager:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.bot = PriceBot()
        self.interval = CONFIG['UPDATE_INTERVAL']
        self.prep_job = None
        self.send_job = None

    def _next_interval(self) -> datetime:
        """Calculate next aligned interval time"""
        now = datetime.now()
        interval = self.interval
        return now + timedelta(seconds=interval - (now.second % interval))

    async def start(self):
        """Start scheduler with aligned intervals"""
        next_run = self._next_interval()

        # Schedule price preparation 5 seconds before intervals
        self.prep_job = self.scheduler.add_job(
            self.bot.prepare_update,
            trigger=IntervalTrigger(
                seconds=self.interval,
                start_date=next_run - timedelta(seconds=5)
            ),
            max_instances=1
        )

        # Schedule exact-time message sending
        self.send_job = self.scheduler.add_job(
            self.bot.send_scheduled_update,
            trigger=IntervalTrigger(
                seconds=self.interval,
                start_date=next_run,
                jitter=0
            ),
            max_instances=1
        )

        self.scheduler.start()
        logger.info(f"💰 Scheduler started with {self.interval}s intervals. Next update at {next_run}")

        try:
            while True:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            self.scheduler.shutdown()
            logger.info("🛑 Scheduler stopped")

    def update_interval(self, new_interval: int):
        """Update both preparation and sending intervals"""
        self.interval = new_interval
        next_run = self._next_interval()

        # Reschedule preparation job
        self.prep_job.reschedule(
            trigger=IntervalTrigger(
                seconds=new_interval,
                start_date=next_run - timedelta(seconds=5)
            )
        )

        # Reschedule sending job
        self.send_job.reschedule(
            trigger=IntervalTrigger(
                seconds=new_interval,
                start_date=next_run,
                jitter=0
            )
        )

        logger.info(f"⏱ Update interval changed to {new_interval}s. Next update at {next_run}")

scheduler_manager = SchedulerManager()

async def start_scheduler():
    try:
        await scheduler_manager.start()
    except Exception as e:
        logger.critical(f"💥 Scheduler failed to start: {str(e)}")
        raise

