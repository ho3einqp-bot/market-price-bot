import asyncio
from bot.scheduler import start_scheduler
from config.logging_config import configure_logging

if __name__ == "__main__":
    configure_logging()
    asyncio.run(start_scheduler())
