import asyncio
from loguru import logger
from scheduler.main_pipeline import run_discovery_cycle
from database.models import init_db

async def main():
    logger.info("Starting a single pilot discovery cycle...")
    init_db()
    # run pilot (Nairobi + Mombasa, top 5 categories)
    await run_discovery_cycle(use_pilot=True)
    logger.info("Pilot cycle complete!")

if __name__ == "__main__":
    asyncio.run(main())
