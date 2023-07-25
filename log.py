import logging
import os

log_level_name = os.getenv('LOG_LEVEL', 'WARNING')
log_level = getattr(logging, log_level_name.upper(), None)

if not isinstance(log_level, int):
  raise ValueError(f'Invalid log level: {log_level_name}')

logging.basicConfig(level=log_level)
