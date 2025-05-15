"""Constants utilisées dans le Market Analyzer"""

class MarketConstants:
    # Clés API
    API_KEY_ENV = 'MEXC_API_KEY'
    API_SECRET_ENV = 'MEXC_API_SECRET'
    
    # Clés de réponse API
    TICKER_LAST_PRICE = 'last'
    ORDER_STATUS = 'status'
    ORDER_CLOSED = 'closed'
    
    # Messages d'erreur
    ERROR_API_KEYS = "Les clés API MEXC ne sont pas configurées"
    ERROR_INVALID_SYMBOLS = "Symboles invalides: {}"
    ERROR_TICKER_DATA = "Données de ticker invalides pour {}"
    
    # Configuration Exchange
    EXCHANGE_CONFIG = {
        'enableRateLimit': True,
        'options': {
            'defaultType': 'spot',
            'adjustForTimeDifference': True,
            'createMarketBuyOrderRequiresPrice': False,
            'defaultTimeInForce': 'IOC',  # Immediate-Or-Cancel pour une exécution plus rapide
            'recvWindow': 5000,  # Fenêtre de réception réduite pour MEXC
            'fastOrderExecution': True  # Option pour privilégier la vitesse d'exécution
        },
        'timeout': 15000,  # Timeout réduit pour des réponses plus rapides
        'rateLimit': 50,    # Rate limit réduit pour des requêtes plus fréquentes
    }
