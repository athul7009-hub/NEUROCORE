
from app.core.logger import logger, LOG_FILE


def test_logger():
    logger.info("NEUROCORE logging test started")
    logger.warning("This is a sample warning")
    logger.error("This is a sample error")

    assert LOG_FILE.exists()

    print("\nPASS: Log file created")
    print("Log location:", LOG_FILE)


if __name__ == "__main__":
    test_logger()
