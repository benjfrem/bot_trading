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
    # Montant de transaction en USDC
    TRANSACTION_AMOUNT = 50  # Augmenté pour BTC dont la valeur unitaire est plus élevée

    # Quantité fixe de transaction en BTC
    TRANSACTION_QUANTITY = 0.001  # Quantité de BTC à acheter/vendre par ordre (ajusté pour ~50 USDC si BTC vaut 50k)
    
    # Limites de positions
    MAX_POSITIONS = 1        # Nombre maximum de positions simultanées
    
    # Seuils ATR pour filtrage de la volatilité
    ATR_HIGH_VOLATILITY_THRESHOLD = 450  # Seuil au-dessus duquel aucune position n'est prise
    ATR_MEDIUM_VOLATILITY_THRESHOLD = 300  # Seuil entre volatilité normale et moyenne
    
    # Configuration du filtre Stochastique
    STOCH_TIMEFRAME = "5m"   # Timeframe pour l'indicateur stochastique
    STOCH_K_LENGTH = 14       # Période pour %K
    STOCH_K_SMOOTH = 5       # Lissage pour %K
    STOCH_D_SMOOTH = 3       # Lissage pour %D
    STOCH_OVERSOLD_THRESHOLD = 30  # Seuil de survente (%K < 20)
    
    # Configuration du Trailing Buy basé sur RSI
    TRAILING_BUY_RSI_LEVELS_NEUTRAL = [
        {'trigger': 25, 'stop': 30, 'immediate': True}, 
        {'trigger': 20, 'stop': 25, 'immediate': True},  
        {'trigger': 10, 'stop': 20, 'immediate': True},   
        {'trigger': 0, 'stop': 10, 'immediate': True}
    ]
    # Configuration par défaut (utilisée si aucune tendance n'est détectée)
    TRAILING_BUY_RSI_LEVELS = TRAILING_BUY_RSI_LEVELS_NEUTRAL
    
    # Configuration du Trailing Stop Loss mecx
		#niveau 1 du tralling loss ( distance entre les niveau )

    
    TRAILING_STOP_LEVELS = [
		#niveau 1 du tralling loss ( distance entre les niveau )
	    {'trigger': 0.20, 'stop': 0.12, 'immediate': True}, 
	    {'trigger': 0.25, 'stop': 0.20, 'immediate': True},    
        {'trigger': 0.40, 'stop': 0.25, 'immediate': True},    
        {'trigger': 0.50, 'stop': 0.40, 'immediate': True},    
        {'trigger': 0.60, 'stop': 0.50, 'immediate': True},
	    {'trigger': 0.80, 'stop': 0.60, 'immediate': True},    
        {'trigger': 1, 'stop': 0.8, 'immediate': True},    
        {'trigger': 0.85, 'stop': 0.70, 'immediate': True},    
        {'trigger': 1.00, 'stop': 0.85, 'immediate': True},    
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
    ATR_LENGTH = 4             # Nombre de bougies pour calcul ATR
    ATR_INTERVAL = "15m"       # Intervalle pour ATR (15 minutes)
    ATR_MULTIPLIER = 2         # Multiplicateur pour la distance du stop loss
    STOP_TIMEOUT_SEC = 5       # Délai anti-mèche en secondes
    # Paramètres DMI négatif
    DMI_NEGATIVE_LENGTH = 5    # Période DMI−
    DMI_NEGATIVE_SMOOTHING = 5 # Lissage DMI−
    DMI_NEGATIVE_THRESHOLD_SAFE = 50    # Seuil DMI− non dangereux
    DMI_NEGATIVE_THRESHOLD_WARNING = 66 # Seuil DMI− zone vigilance
    # Trailing stop renforcé pour zone de vigilance DMI (paliers serrés)
    DMI_VIGILANCE_TRAILING_STOP_LEVELS = [
        {'trigger': 0.06, 'stop': 0.03, 'immediate': True},
        {'trigger': 0.09, 'stop': 0.06, 'immediate': True},
        {'trigger': 0.12, 'stop': 0.09, 'immediate': True},
        {'trigger': 0.20, 'stop': 0.12, 'immediate': True},
        {'trigger': 0.40, 'stop': 0.30, 'immediate': True},
        {'trigger': 0.60, 'stop': 0.40, 'immediate': True},
        {'trigger': 0.80, 'stop': 0.60, 'immediate': True},
        {'trigger': 1.00, 'stop': 0.80, 'immediate': True},
        {'trigger': 1.20, 'stop': 1.00, 'immediate': True},
        {'trigger': 1.40, 'stop': 1.20, 'immediate': True},
        {'trigger': 1.60, 'stop': 1.40, 'immediate': True}
    ]

    # Paramètre de double confirmation RSI
    DOUBLE_CONFIRMATION_TICKS = 2

class MarketConfig:
    """Configuration des marchés"""
    # Liste des paires de trading supportées
    CRYPTO_LIST = [
        'BTC/USDC',
    ]

class TechnicalConfig:
    """Configuration des indicateurs techniques"""
    # Paramètres RSI
    RSI_PERIOD = 4          # Période pour le RSI
    
    # Autres paramètres supprimés (Bollinger Bands et Volume)

class ScoringConfig:
    """Configuration du système de scoring"""
    # Scores RSI (25-40 points selon le niveau déclenché)
    RSI_SCORES = {
        'level_1': 25,  # Niveau 1
        'level_2': 30,  # Niveau 2
        'level_3': 35,  # Niveau 3
        'level_4': 40   # Niveau 4
    }
    
    # Les configurations BB_SCORES et VOLUME_SCORES ont été supprimées

class TimeConfig:
    """Configuration des intervalles de temps"""
    # Intervalles en secondes
    ANALYSIS_INTERVAL = 60       # Analyse du marché tous les 60 secondes
    CHECK_INTERVAL = 15          # Vérification des positions (vérifier les positions chaque seconde)

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
    INTERVAL = "15m"            # Intervalle par minute pour des mises à jour rapides des données
    
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
    TRANSACTION_AMOUNT = TradingConfig.TRANSACTION_AMOUNT
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
    RSI_SCORES = ScoringConfig.RSI_SCORES
    
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

    # Paramètres ATR pour Stop Loss adaptatif
    ATR_LENGTH = TradingConfig.ATR_LENGTH
    ATR_INTERVAL = TradingConfig.ATR_INTERVAL
    ATR_MULTIPLIER = TradingConfig.ATR_MULTIPLIER
    STOP_TIMEOUT_SEC = TradingConfig.STOP_TIMEOUT_SEC
    
    # Paramètres Stochastique
    STOCH_TIMEFRAME = TradingConfig.STOCH_TIMEFRAME
    STOCH_K_LENGTH = TradingConfig.STOCH_K_LENGTH
    STOCH_K_SMOOTH = TradingConfig.STOCH_K_SMOOTH
    STOCH_D_SMOOTH = TradingConfig.STOCH_D_SMOOTH
    STOCH_OVERSOLD_THRESHOLD = TradingConfig.STOCH_OVERSOLD_THRESHOLD

    # Paramètres DMI négatif exportés globalement
    DMI_NEGATIVE_LENGTH = TradingConfig.DMI_NEGATIVE_LENGTH
    DMI_NEGATIVE_SMOOTHING = TradingConfig.DMI_NEGATIVE_SMOOTHING
    DMI_NEGATIVE_THRESHOLD_SAFE = TradingConfig.DMI_NEGATIVE_THRESHOLD_SAFE
    DMI_NEGATIVE_THRESHOLD_WARNING = TradingConfig.DMI_NEGATIVE_THRESHOLD_WARNING
    DMI_VIGILANCE_TRAILING_STOP_LEVELS = TradingConfig.DMI_VIGILANCE_TRAILING_STOP_LEVELS
    
    # Seuils ATR pour filtrage volatilité exportés globalement
    ATR_HIGH_VOLATILITY_THRESHOLD = TradingConfig.ATR_HIGH_VOLATILITY_THRESHOLD
    ATR_MEDIUM_VOLATILITY_THRESHOLD = TradingConfig.ATR_MEDIUM_VOLATILITY_THRESHOLD
    # Paramètre de double confirmation RSI exporté globalement
    DOUBLE_CONFIRMATION_TICKS = TradingConfig.DOUBLE_CONFIRMATION_TICKS
    # Telegram Bot credentials
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
