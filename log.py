import logging
import os

def get_logger(caller):
  logger = logging.getLogger(caller)
  handler = logging.StreamHandler()
  handler.setLevel(logging.DEBUG)
  log_level_name = os.getenv('LOG_LEVEL', 'WARNING')
  log_level = getattr(logging, log_level_name.upper(), None)
  if not isinstance(log_level, int):
    raise ValueError(f'Invalid log level: {log_level_name}')
  logger.setLevel(log_level)
  return logger
