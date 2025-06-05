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
    # Quantité fixe de transaction en BTC
    TRANSACTION_QUANTITY = 0.001  # Quantité de BTC à acheter/vendre par ordre (ajusté pour ~50 USDC si BTC vaut 50k)
    
    # Limites de positions
    MAX_POSITIONS = 1        # Nombre maximum de positions simultanées
    
    # Seuils ATR pour filtrage de la volatilité
    ATR_HIGH_VOLATILITY_THRESHOLD = 350  # Seuil au-dessus duquel aucune position n'est prise

    # Paliers pour trailing stop adapté (score == 2)
    ADAPTIVE_TRAILING_STOP_LEVELS = [
        {'trigger': 0.08, 'stop': 0.04, 'immediate': True},
        {'trigger': 0.12, 'stop': 0.08, 'immediate': True},
        {'trigger': 0.17, 'stop': 0.12, 'immediate': True},
        {'trigger': 0.25, 'stop': 0.17, 'immediate': True},
        {'trigger': 0.35, 'stop': 0.25, 'immediate': True},
        {'trigger': 0.50, 'stop': 0.35, 'immediate': True},
        {'trigger': 0.60, 'stop': 0.50, 'immediate': True},
        {'trigger': 0.85, 'stop': 0.60, 'immediate': True},
        {'trigger': 1.00, 'stop': 0.85, 'immediate': True},
        {'trigger': 1.20, 'stop': 1.00, 'immediate': True},
        {'trigger': 1.40, 'stop': 1.20, 'immediate': True},
        {'trigger': 1.60, 'stop': 1.40, 'immediate': True}
    ]
    
    # Configuration du Trailing Buy basé sur RSI
    TRAILING_BUY_RSI_LEVELS_NEUTRAL = [
        {'trigger': 1, 'stop': 30, 'immediate': True}
    ]
    # Configuration par défaut (utilisée si aucune tendance n'est détectée)
    TRAILING_BUY_RSI_LEVELS = TRAILING_BUY_RSI_LEVELS_NEUTRAL
    
    # Configuration du Trailing Stop Loss mexc
    TRAILING_STOP_LEVELS = [
        {'trigger': 0.15, 'stop': 0.1, 'immediate': True}, 
        {'trigger': 0.20, 'stop': 0.15, 'immediate': True},
        {'trigger': 0.25, 'stop': 0.20, 'immediate': True},    
        {'trigger': 0.40, 'stop': 0.25, 'immediate': True},    
        {'trigger': 0.60, 'stop': 0.40, 'immediate': True},
        {'trigger': 0.80, 'stop': 0.60, 'immediate': True},    
        {'trigger': 1.00, 'stop': 0.80, 'immediate': True},    
        {'trigger': 0.60, 'stop': 0.40, 'immediate': True},
        {'trigger': 0.80, 'stop': 0.60, 'immediate': True},    
        {'trigger': 1.00, 'stop': 0.80, 'immediate': True},    
        {'trigger': 1.20, 'stop': 1.00, 'immediate': True},    
        {'trigger': 1.40, 'stop': 1.20, 'immediate': True},    
        {'trigger': 1.60, 'stop': 1.40, 'immediate': True}     
    ]
    
    # Stop loss initial
    INITIAL_STOP_LOSS = 0.1    # Stop loss initial à 10
    
    # Montant minimum de transaction en quote currency (USDC) requis par l'exchange
    MIN_TRANSACTION_QUOTE_AMOUNT = 1.0  # Doit être >= 1 USDC
    
    # Seuils de décision pour le scoring
    DECISION_THRESHOLDS = {
        'full_position': 33,    # Score ≥ 33: Allocation complète (100%)
        'partial_position': 33  # Maintenu pour compatibilité mais non utilisé
    }

    # Paramètres ATR pour Stop Loss adaptatif
    ATR_LENGTH = 6             # Nombre de bougies pour calcul ATR
    ATR_INTERVAL = "5m"       # Intervalle pour ATR (15 minutes)
    ATR_MULTIPLIER = 1.5       # Multiplicateur pour la distance du stop loss
    STOP_TIMEOUT_SEC = 5       # Délai anti-mèche en secondes

    # Paramètre de double confirmation RSI
    DOUBLE_CONFIRMATION_TICKS = 2

class MarketConfig:
    """Configuration des marchés"""
    CRYPTO_LIST = [
        'BTC/USDC',
    ]

class TechnicalConfig:
    """Configuration des indicateurs techniques"""
    RSI_PERIOD = 3
    FISHER_PERIOD = 9
    FISHER_INTERVAL = "1m"
    FISHER_THRESHOLD = 1.5
    
    WILLIAMS_R_PERIOD = 8
    WILLIAMS_R_INTERVAL = "15m"
    WILLIAMS_R_OVERSOLD_THRESHOLD = -80
    WILLIAMS_R_OVERBOUGHT_THRESHOLD = -40

    ADX_LENGTH = 10
    DI_LENGTH = 10
    ADX_INTERVAL = "1D"
    "--------------------------"
    ADX_LENGTH_VALID = 10
    DI_LENGTH_VALID = 10
    ADX_INTERVAL_VALID = "1m"
    DMI_NEGATIVE_THRESHOLD = 45
class ScoringConfig:
    """Configuration du système de scoring"""
    pass

class TimeConfig:
    """Configuration des intervalles de temps"""
    ANALYSIS_INTERVAL = 60     # Analyse du marché tous les 60 secondes
    CHECK_INTERVAL = 15        # Vérification des positions (vérifier les positions chaque seconde)

class LogConfig:
    """Configuration des logs"""
    LOG_FILE = 'logs/trading.log'
    ERROR_LOG = 'logs/error.log'

class TaapiConfig:
    """Configuration de l'API taapi.io pour les indicateurs techniques"""
    API_KEY = os.getenv('TAAPI_API_KEY')
    ENDPOINT = "https://api.taapi.io"
    EXCHANGE = "binance"
    INTERVAL = "5m"
    CACHE_TTL = 0.1
    VERIFY_SSL = False

class Config(TradingConfig, MarketConfig, TechnicalConfig, ScoringConfig, TimeConfig, LogConfig, TaapiConfig):
    """Configuration globale du bot"""
    DMI_NEGATIVE_THRESHOLD = TechnicalConfig.DMI_NEGATIVE_THRESHOLD
    pass

class LogConfig:
    """Configuration des logs"""
    # Chemins des fichiers de log
    LOG_FILE = 'logs/trading.log'
    ERROR_LOG = 'logs/error.log'

    class MarketConfig:
        """Configuration des marchés"""
        # Liste des paires de trading supportées
        CRYPTO_LIST = [
            'BTC/USDC',     
        ]

class TaapiConfig:
    """Configuration de l'API taapi.io pour les indicateurs techniques"""
    # Clé API taapi.io (récupérée depuis les variables d'environnement)
    API_KEY = os.getenv('TAAPI_API_KEY')
    
    # Configuration des requêtes
    ENDPOINT = "https://api.taapi.io"
    EXCHANGE = "binance"       # Utiliser binance qui est l'exchange par défaut de taapi.io
    INTERVAL = "5m"            # Intervalle par minute pour des mises à jour rapides des données
    
    # Configuration du cache
    CACHE_TTL = 0.1            # Durée de vie du cache très courte pour forcer les appels API fréquents
    
    # Configuration SSL
    VERIFY_SSL = False         # Désactiver la vérification SSL pour contourner les erreurs de certificat

class Config:
    """Configuration globale du bot
    
    Cette classe regroupe toutes les configurations en un point d'accès unique.
    Elle hérite des paramètres de chaque classe de configuration spécifique.
    """
    # Import des configurations spécifiques
    CRYPTO_LIST = MarketConfig.CRYPTO_LIST
    
    # Montant minimum de transaction en quote currency (USDC)
    MIN_TRANSACTION_QUOTE_AMOUNT = TradingConfig.MIN_TRANSACTION_QUOTE_AMOUNT
    
    # Paramètres de trading
    TRANSACTION_QUANTITY = TradingConfig.TRANSACTION_QUANTITY
    MAX_POSITIONS = TradingConfig.MAX_POSITIONS
    TRAILING_BUY_RSI_LEVELS = TradingConfig.TRAILING_BUY_RSI_LEVELS
    TRAILING_BUY_RSI_LEVELS_NEUTRAL = TradingConfig.TRAILING_BUY_RSI_LEVELS_NEUTRAL
    
    # Trailing stop et autres paramètres
    TRAILING_STOP_LEVELS = TradingConfig.TRAILING_STOP_LEVELS
    INITIAL_STOP_LOSS = TradingConfig.INITIAL_STOP_LOSS
    DECISION_THRESHOLDS = TradingConfig.DECISION_THRESHOLDS
    
    # Paramètres techniques - seulement RSI
    RSI_PERIOD = TechnicalConfig.RSI_PERIOD
    
    # Paramètres de scoring - seulement RSI_SCORES
    
    # Intervalles
    ANALYSIS_INTERVAL = TimeConfig.ANALYSIS_INTERVAL
    CHECK_INTERVAL = TimeConfig.CHECK_INTERVAL
    
    # Logs
    LOG_FILE = LogConfig.LOG_FILE
    ERROR_LOG = LogConfig.ERROR_LOG
    
    # Paramètres taapi.io
    TAAPI_API_KEY = TaapiConfig.API_KEY
    TAAPI_ENDPOINT = TaapiConfig.ENDPOINT
    TAAPI_EXCHANGE = TaapiConfig.EXCHANGE
    TAAPI_INTERVAL = TaapiConfig.INTERVAL
    TAAPI_CACHE_TTL = TaapiConfig.CACHE_TTL
    TAAPI_VERIFY_SSL = TaapiConfig.VERIFY_SSL

    # Paramètres Fisher Transform
    FISHER_PERIOD = TechnicalConfig.FISHER_PERIOD
    FISHER_INTERVAL = TechnicalConfig.FISHER_INTERVAL
    FISHER_THRESHOLD = TechnicalConfig.FISHER_THRESHOLD

    # Paramètres Williams %R
    WILLIAMS_R_PERIOD = TechnicalConfig.WILLIAMS_R_PERIOD
    WILLIAMS_R_INTERVAL = TechnicalConfig.WILLIAMS_R_INTERVAL
    WILLIAMS_R_OVERSOLD_THRESHOLD = TechnicalConfig.WILLIAMS_R_OVERSOLD_THRESHOLD
    WILLIAMS_R_OVERBOUGHT_THRESHOLD = TechnicalConfig.WILLIAMS_R_OVERBOUGHT_THRESHOLD

    # Paramètres ADX et DMI exportés
    ADX_LENGTH = TechnicalConfig.ADX_LENGTH
    DI_LENGTH = TechnicalConfig.DI_LENGTH
    ADX_INTERVAL = TechnicalConfig.ADX_INTERVAL
    ADX_LENGTH_VALID = TechnicalConfig.ADX_LENGTH_VALID
    DI_LENGTH_VALID = TechnicalConfig.DI_LENGTH_VALID
    ADX_INTERVAL_VALID = TechnicalConfig.ADX_INTERVAL_VALID

    # Paramètres ATR pour Stop Loss adaptatif
    ATR_LENGTH = TradingConfig.ATR_LENGTH
    ATR_INTERVAL = TradingConfig.ATR_INTERVAL
    ATR_MULTIPLIER = TradingConfig.ATR_MULTIPLIER
    STOP_TIMEOUT_SEC = TradingConfig.STOP_TIMEOUT_SEC
    

    
    # Seuils ATR pour filtrage volatilité exportés globalement
    ATR_HIGH_VOLATILITY_THRESHOLD = TradingConfig.ATR_HIGH_VOLATILITY_THRESHOLD
    # Paramètre de double confirmation RSI exporté globalement
    DOUBLE_CONFIRMATION_TICKS = TradingConfig.DOUBLE_CONFIRMATION_TICKS
    ADAPTIVE_TRAILING_STOP_LEVELS = TradingConfig.ADAPTIVE_TRAILING_STOP_LEVELS
    # Telegram Bot credentials
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
