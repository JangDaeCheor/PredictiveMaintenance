import logging
from pathlib import Path


def setup_logging():
  log_dir = Path("logs")
  log_dir.mkdir(exist_ok=True)

  logger = logging.getLogger()
  logger.setLevel(logging.DEBUG)

  formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] [%(threadName)s] %(name)s:%(lineno)d - %(message)s"
  )

  stream_handler = logging.StreamHandler()
  stream_handler.setLevel(logging.INFO)
  stream_handler.setFormatter(formatter)

  file_handler = logging.FileHandler(
    log_dir / "app.log",
    encoding="utf-8",
  )
  file_handler.setLevel(logging.DEBUG)
  file_handler.setFormatter(formatter)

  logger.addHandler(stream_handler)
  logger.addHandler(file_handler)
