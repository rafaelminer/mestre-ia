import logging
from pathlib import Path
from services.log_service import log_info, log_warning, log_error

logs_path = Path(__file__).resolve().parent
logs_path.mkdir(parents=True, exist_ok=True)
file_handler = logging.FileHandler(logs_path / 'dojo_os.log')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))

logger = logging.getLogger('dojo_os')
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(file_handler)


def info(msg: str, empresa: str = 'sistema', contexto: str = ''):
    logger.info(msg)
    log_info(empresa, msg, contexto)


def warning(msg: str, empresa: str = 'sistema', contexto: str = ''):
    logger.warning(msg)
    log_warning(empresa, msg, contexto)


def error(msg: str, empresa: str = 'sistema', contexto: str = ''):
    logger.error(msg)
    log_error(empresa, msg, contexto)
