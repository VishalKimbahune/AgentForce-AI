"""Mock business services (Calendar, ATS, HRMS, ERP, CRM) entry point."""

import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mock_services")


async def main():
    logger.info("Mock business services running on ports 8100-8103...")
    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())

