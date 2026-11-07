
import logging
import time

from app.config import settings
from app.worker import recover_stale_jobs


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger("job-reaper")


def main():
    logger.info("Stale-job reaper started.")

    while True:
        try:
            recover_stale_jobs()
        except Exception:
            logger.exception("Reaper cycle failed.")

        time.sleep(30)


if __name__ == "__main__":
    main()
