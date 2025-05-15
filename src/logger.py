import logging
from logging.handlers import RotatingFileHandler
import os
from config import Config

def setup_logger(name, log_file, level=logging.INFO):
    # Créer le dossier logs s'il n'existe pas
    os.makedirs('logs', exist_ok=True)
    
    # Configurer le logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Définir le format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Créer un handler de fichier rotatif
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=1024 * 1024,  # 1MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    
    # Créer un handler de console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Ajouter les handlers au logger si aucun handler n'existe déjà
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger

# Créer les loggers
trading_logger = setup_logger('trading', Config.LOG_FILE)
error_logger = setup_logger('error', Config.ERROR_LOG, level=logging.ERROR)