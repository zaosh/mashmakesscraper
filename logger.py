import logging
import config

# Setup standard logging configuration
logger = logging.getLogger("MashMakesTracker")
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# File handler
file_handler = logging.FileHandler(config.LOG_FILE, encoding='utf-8')
file_handler.setFormatter(formatter)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

def log_info(message):
    logger.info(message)

def log_warning(message):
    logger.warning(message)

def log_error(message):
    logger.error(message)

def get_recent_logs(lines=20):
    try:
        with open(config.LOG_FILE, 'r', encoding='utf-8', errors='replace') as f:
            log_lines = f.readlines()
            return log_lines[-lines:]
    except FileNotFoundError:
        return ["No logs available yet."]
