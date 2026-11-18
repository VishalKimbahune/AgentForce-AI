"""Worker process consuming events from RabbitMQ or Redis Streams."""

import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("worker")


async def main():
    logger.info("AgentForce worker starting up...")
    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())

