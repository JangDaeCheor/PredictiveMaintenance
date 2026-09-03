import logging

from back.worker import Worker, Message
from logging_config import setup_logging


def main():
  logger = logging.getLogger(__name__)

  logger.info("program start")


main()
