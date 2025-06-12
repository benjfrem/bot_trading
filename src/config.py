"""Configuration du bot de trading

Ce module contient toutes les configurations nécessaires au fonctionnement du bot,
organisées en classes thématiques pour une meilleure lisibilité et maintenance.
"""
import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

class TradingConfig:
    """Configuration des paramètres de trading"""
    TRANSACTION_QUANTITY = 0.001

    MAX_POSITIONS = 1

    ATR_HIGH_VOLATILITY_THRESHOLD = 350
    
    ADAPTIVE_TRAILING_STOP_LEVELS = [
        {'trigger': 0.07, 'stop': 0.05, 'immediate': True},
        {'trigger': 0.1, 'stop': 0.07, 'immediate': True},
        {'trigger': 0.15, 'stop': 0.1, 'immediate': True},
        {'trigger': 0.25, 'stop': 0.15, 'immediate': True},
        {'trigger': 0.35, 'stop': 0.25, 'immediate': True},
        {'trigger': 0.50, 'stop': 0.35, 'immediate': True},
        {'trigger': 0.60, 'stop': 0.50, 'immediate': True},
        {'trigger': 0.85, 'stop': 0.60, 'immediate': True},
        {'trigger': 1.00, 'stop': 0.85, 'immediate': True},
        {'trigger': 1.20, 'stop': 1.00, 'immediate': True},
        {'trigger': 1.40, 'stop': 1.20, 'immediate': True},
        {'trigger': 1.60, 'stop': 1.40, 'immediate': True}
    ]

    TRAILING_BUY_RSI_LEVELS_NEUTRAL = [
    {'trigger': 1, 'stop': 30, 'immediate': True}
    ]
    TRAILING_BUY_RSI_LEVELS = TRAILING_BUY_RSI_LEVELS_NEUTRAL
    TRAILING_STOP_LEVELS = [
        {'trigger': 0.17, 'stop': 0.12, 'immediate': True},
        {'trigger': 0.20, 'stop': 0.15, 'immediate': True},
        {'trigger': 0.25, 'stop': 0.20, 'immediate': True},
        {'trigger': 0.40, 'stop': 0.25, 'immediate': True},
        {'trigger': 0.60, 'stop': 0.40, 'immediate': True},
        {'trigger': 0.80, 'stop': 0.60, 'immediate': True},
        {'trigger': 1.00, 'stop': 0.80, 'immediate': True},
        {'trigger': 1.20, 'stop': 1.00, 'immediate': True},
        {'trigger': 1.40, 'stop': 1.20, 'immediate': True},
        {'trigger': 1.60, 'stop': 1.40, 'immediate': True}
    ]
    INITIAL_STOP_LOSS = 0.1
    MIN_TRANSACTION_QUOTE_AMOUNT = 1.0
    ATR_LENGTH = 14
    ATR_INTERVAL = "5m"
    ATR_MULTIPLIER = 1.9
    STOP_TIMEOUT_SEC = 5
    DOUBLE_CONFIRMATION_TICKS = 2

class MarketConfig:
    """Configuration des marchés"""
    CRYPTO_LIST = ['BTC/USDC']

class TimeConfig:
    ANALYSIS_INTERVAL = 60

    CHECK_INTERVAL = 10

class LogConfig:
    LOG_FILE = 'logs/trading.log'
    ERROR_LOG = 'logs/error.log'

class TaapiConfig:
    API_KEY = os.getenv('TAAPI_API_KEY')
    ENDPOINT = "https://api.taapi.io"
    EXCHANGE = "binance"
    INTERVAL = "5m"
    CACHE_TTL = 0.1
    VERIFY_SSL = False
class TechnicalConfig:
    """Configuration des indicateurs techniques"""
    RSI_PERIOD = 3
    RSI_SMA_LENGTH = 7
    RSI_SMA_THRESHOLD = 66

    FISHER_PERIOD = 9
    FISHER_INTERVAL = "1m"
    FISHER_THRESHOLD = 1.5
    
    WILLIAMS_R_PERIOD = 3
    WILLIAMS_R_INTERVAL = "15m"
    WILLIAMS_R_OVERSOLD_THRESHOLD = -80
    WILLIAMS_R_OVERBOUGHT_THRESHOLD = -30

    ADX_LENGTH = 10
    DI_LENGTH = 10
    ADX_INTERVAL = "1D"
    ADX_LENGTH_VALID = 10
    DI_LENGTH_VALID = 10
    ADX_INTERVAL_VALID = "5m"
    DMI_NEGATIVE_THRESHOLD = 30
    DMI_MODERATE_THRESHOLD = 25

class Config(TradingConfig, MarketConfig, TechnicalConfig, TimeConfig, LogConfig, TaapiConfig):
    """Configuration globale du bot"""

class ScoringConfig:
    """Configuration du système de scoring"""
    pass

class Config:
    """Configuration globale du bot
    
    Cette classe regroupe toutes les configurations en un point d'accès unique.
    Elle hérite des paramètres de chaque classe de configuration spécifique.
    """
    CRYPTO_LIST = MarketConfig.CRYPTO_LIST
    MIN_TRANSACTION_QUOTE_AMOUNT = TradingConfig.MIN_TRANSACTION_QUOTE_AMOUNT
    TRANSACTION_QUANTITY = TradingConfig.TRANSACTION_QUANTITY
    MAX_POSITIONS = TradingConfig.MAX_POSITIONS
    TRAILING_BUY_RSI_LEVELS = TradingConfig.TRAILING_BUY_RSI_LEVELS
    TRAILING_BUY_RSI_LEVELS_NEUTRAL = TradingConfig.TRAILING_BUY_RSI_LEVELS_NEUTRAL
    TRAILING_STOP_LEVELS = TradingConfig.TRAILING_STOP_LEVELS
    INITIAL_STOP_LOSS = TradingConfig.INITIAL_STOP_LOSS
    RSI_PERIOD = TechnicalConfig.RSI_PERIOD
    ANALYSIS_INTERVAL = TimeConfig.ANALYSIS_INTERVAL
    CHECK_INTERVAL = TimeConfig.CHECK_INTERVAL
    LOG_FILE = LogConfig.LOG_FILE
    ERROR_LOG = LogConfig.ERROR_LOG
    TAAPI_API_KEY = TaapiConfig.API_KEY
    TAAPI_ENDPOINT = TaapiConfig.ENDPOINT
    TAAPI_EXCHANGE = TaapiConfig.EXCHANGE
    TAAPI_INTERVAL = TaapiConfig.INTERVAL
    TAAPI_CACHE_TTL = TaapiConfig.CACHE_TTL
    TAAPI_VERIFY_SSL = TaapiConfig.VERIFY_SSL
    FISHER_PERIOD = TechnicalConfig.FISHER_PERIOD
    FISHER_INTERVAL = TechnicalConfig.FISHER_INTERVAL
    FISHER_THRESHOLD = TechnicalConfig.FISHER_THRESHOLD
    WILLIAMS_R_PERIOD = TechnicalConfig.WILLIAMS_R_PERIOD
    WILLIAMS_R_INTERVAL = TechnicalConfig.WILLIAMS_R_INTERVAL
    WILLIAMS_R_OVERSOLD_THRESHOLD = TechnicalConfig.WILLIAMS_R_OVERSOLD_THRESHOLD
    WILLIAMS_R_OVERBOUGHT_THRESHOLD = TechnicalConfig.WILLIAMS_R_OVERBOUGHT_THRESHOLD
    RSI_SMA_LENGTH = TechnicalConfig.RSI_SMA_LENGTH
    RSI_SMA_THRESHOLD = TechnicalConfig.RSI_SMA_THRESHOLD
    ADX_LENGTH = TechnicalConfig.ADX_LENGTH
    DI_LENGTH = TechnicalConfig.DI_LENGTH
    ADX_INTERVAL = TechnicalConfig.ADX_INTERVAL
    ADX_LENGTH_VALID = TechnicalConfig.ADX_LENGTH_VALID
    DI_LENGTH_VALID = TechnicalConfig.DI_LENGTH_VALID
    ADX_INTERVAL_VALID = TechnicalConfig.ADX_INTERVAL_VALID
    ATR_LENGTH = TradingConfig.ATR_LENGTH
    ATR_INTERVAL = TradingConfig.ATR_INTERVAL
    ATR_MULTIPLIER = TradingConfig.ATR_MULTIPLIER
    STOP_TIMEOUT_SEC = TradingConfig.STOP_TIMEOUT_SEC
    ATR_HIGH_VOLATILITY_THRESHOLD = TradingConfig.ATR_HIGH_VOLATILITY_THRESHOLD
    DOUBLE_CONFIRMATION_TICKS = TradingConfig.DOUBLE_CONFIRMATION_TICKS
    ADAPTIVE_TRAILING_STOP_LEVELS = TradingConfig.ADAPTIVE_TRAILING_STOP_LEVELS
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    DMI_NEGATIVE_THRESHOLD = TechnicalConfig.DMI_NEGATIVE_THRESHOLD
    DMI_MODERATE_THRESHOLD = TechnicalConfig.DMI_MODERATE_THRESHOLD
