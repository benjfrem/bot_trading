"""Module des indicateurs techniques

Ce module fournit des fonctions pour calculer divers indicateurs techniques utilisés par le bot.
"""
import asyncio
from config import Config
from utils.indicators.taapi_client import taapi_client

def calculate_rsi(prices, period=14):
    """
    Calcule le Relative Strength Index (RSI) à partir d'une liste de prix.
    :param prices: Liste des prix.
    :param period: Période de calcul du RSI.
    :return: Valeur du RSI.
    """
    # Implémentation du calcul du RSI (placeholder)
    return 50  # Valeur par défaut pour simulation


def get_atr(symbol: str) -> float:
    """
    Récupère l'Average True Range (ATR) pour une paire de trading donnée.
    Les paramètres utilisés proviennent de la configuration et de taapi.io.
    
    Méthodologie :
      - Envoie une requête HTTP au endpoint taapi.io pour l'indicateur ATR.
      - Les paramètres utilisés incluent la clé API, l'exchange, la paire, l'intervalle et la période (ATR_LENGTH).
      - Le résultat est retourné en dollars et sera ensuite converti en ratio au niveau du stop loss.
      
    :param symbol: La paire de trading (ex. 'BTC/USDT').
    :return: La valeur de l'ATR en dollars. Retourne 0.0 en cas d'erreur.
    """

    import time
    import requests
    from config import Config

    # Récupération des paramètres ATR depuis la configuration
    interval = Config.ATR_INTERVAL  # Utiliser TAAPI_INTERVAL (p. ex. "5m") supporté par l'API
    period_value = Config.ATR_LENGTH
    params = {
        "secret": Config.TAAPI_API_KEY,
        "exchange": Config.TAAPI_EXCHANGE.lower(),
        "symbol": symbol,
        "interval": interval,
        "period": period_value,
    }
    
    from requests.exceptions import RequestException
    # Boucle de réessai immédiat en cas de timeout ou d'erreur
    while True:
        try:
            response = requests.get(
                f"{Config.TAAPI_ENDPOINT}/atr",
                params=params,
                verify=Config.TAAPI_VERIFY_SSL,
                timeout=5
            )
            if response.status_code != 200:
                print(f"Erreur ATR API {symbol}: {response.status_code}, {response.text}. Réessai immédiat...")
                continue
            data = response.json()
            print(f"Réponse brute ATR pour {symbol}: {data}")
            return float(data.get("value", 0))
        except RequestException as e:
            print(f"Timeout ou erreur ATR API {symbol}: {e}. Réessai immédiat...")
            continue
        except Exception as e:
            print(f"Erreur inattendue ATR API {symbol}: {e}")
            return 0.0

# Ajout de la classe IndicatorCalculator pour corriger l'import manquant
class IndicatorCalculator:
    """
    Stub de la classe IndicatorCalculator pour fournir update_indicators_batch.
    """
    def __init__(self, log_callback=None):
        self.log_callback = log_callback

    async def update_indicators_batch(self, symbols, market_data, ohlcv_data, data_fetcher):
        """
        Met à jour les indicateurs pour chaque symbole.
        Retourne un dictionnaire {symbol: (current_price, rsi, trend, variation)}.
        """
        results = {}
        for symbol in symbols:
            # Récupérer le prix, fallback sur market_data.last_price en cas d'échec
            price = await data_fetcher.get_current_price(symbol)
            market_d = market_data.get(symbol)
            if price is None and market_d:
                price = market_d.last_price
            rsi = await taapi_client.get_rsi(symbol, Config.RSI_PERIOD)
        results[symbol] = (price, rsi, 0.0)
        return results
