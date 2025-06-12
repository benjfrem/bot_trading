"""
Module client pour l'API taapi.io

Ce module fournit un client asynchrone pour récupérer des indicateurs techniques
depuis l'API taapi.io. Il gère notamment le caching et la transformation des données.
"""
import aiohttp
import asyncio
import time
from typing import Dict, Optional, List
from config import Config
from logger import trading_logger, error_logger


class TaapiClient:
    """Client pour l'API taapi.io"""

    def __init__(self):
        self.api_key = Config.TAAPI_API_KEY
        self.endpoint = Config.TAAPI_ENDPOINT
        self.exchange = Config.TAAPI_EXCHANGE
        self.interval = Config.TAAPI_INTERVAL
        self.cache_ttl = Config.TAAPI_CACHE_TTL
        self._cache: Dict[str, Dict[str, float]] = {}
        self._session: Optional[aiohttp.ClientSession] = None

        if not self.api_key:
            error_logger.error(
                "La clé API taapi.io n'est pas configurée. Le système ne pourra pas récupérer les indicateurs."
            )
            raise ValueError("La clé API taapi.io est requise.")

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """S'assure qu'une session aiohttp est active avec timeout configuré"""
        if self._session is None or self._session.closed:
            ssl_verify = Config.TAAPI_VERIFY_SSL
            connector = aiohttp.TCPConnector(ssl=ssl_verify)
            timeout = aiohttp.ClientTimeout(total=0.8)
            self._session = aiohttp.ClientSession(connector=connector, timeout=timeout)
            self._log("Session HTTP initialisée avec timeout de 0.8 seconde", "info")
        return self._session  # type: ignore

    def _log(self, message: str, level: str = "info"):
        """Centralise la gestion des logs"""
        if level == "info":
            trading_logger.info(message)
        else:
            error_logger.error(message)
        print(message)

    def _get_from_cache(self, symbol: str) -> Optional[float]:
        """Récupère une valeur depuis le cache si elle est valide (désactivé)"""
        return None

    def _update_cache(self, symbol: str, value: float):
        """Met à jour le cache avec une nouvelle valeur (non utilisé)"""
        self._cache[symbol] = {"value": value, "timestamp": time.time()}

    async def get_rsi(self, symbol: str, period: int = 8) -> Optional[float]:
        """
        Récupère la valeur RSI pour un symbole depuis l'API taapi.io ou le cache

        Args:
            symbol: Paire de trading (ex: "BTC/USDT")
            period: Période du RSI (défaut: 14)

        Returns:
            La valeur du RSI ou None en cas d'erreur
        """
        exch = self.exchange.lower()
        # Mapping symbole selon l'exchange
        if exch == "coinbase":
            # Coinbase utilise USD, pas USDT
            formatted_symbol = symbol.replace("/USDT", "/USD")
        elif exch == "kraken":
            # Kraken utilise XBT et USD
            formatted_symbol = symbol.replace("BTC/", "XBT/").replace("/USDT", "/USD")
        else:
            # Autres exchanges, on garde le symbol
            formatted_symbol = symbol

        # Vérifier le cache
        cached = self._get_from_cache(formatted_symbol)
        if cached is not None:
            return cached

        try:
            session = await self._ensure_session()
            url = f"{self.endpoint}/rsi"
            params = {
                "secret": self.api_key,
                "exchange": exch,
                "symbol": formatted_symbol,
                "interval": self.interval,
                "period": period,
                
            }

            async with session.get(url, params=params, timeout=0.8) as response:
                if response.status != 200:
                    error_text = await response.text()
                    self._log(f"Erreur API taapi.io ({response.status}): {error_text}", "error")
                    return None

                data = await response.json()
                self._log(f"Réponse brute taapi.io pour {symbol}: {data}", "info")
                if "value" not in data:
                    self._log(f"Format de réponse inattendu: {data}", "error")
                    return None

                rsi_value = float(data["value"])
                self._update_cache(formatted_symbol, rsi_value)
                self._log(f"RSI pour {symbol}: {rsi_value}", "info")
                return rsi_value

        except asyncio.TimeoutError:
            self._log(f"Timeout de la requête API pour {symbol}", "error")
            return None
        except aiohttp.ClientError as e:
            self._log(f"Erreur réseau: {e}", "error")
            return None
        except Exception as e:
            self._log(f"Erreur récupération RSI pour {symbol}: {e}", "error")
            return None

    async def get_multi_rsi(self, symbols: list, period: int = 14) -> Dict[str, Optional[float]]:
        """
        Récupère les valeurs RSI pour plusieurs symboles en parallèle
        """
        results: Dict[str, Optional[float]] = {}
        semaphore = asyncio.Semaphore(3)

        async def worker(sym: str):
            async with semaphore:
                results[sym] = await self.get_rsi(sym, period)

        await asyncio.gather(*(worker(sym) for sym in symbols))
        return results

    async def get_fisher(self, symbol: str, period: int = None, interval: str = None) -> Optional[float]:
        """
        Récupère la valeur du Fisher Transform pour un symbole depuis l'API taapi.io.

        Args:
            symbol: Paire de trading
            period: Période de calcul (par défaut Config.FISHER_PERIOD)
            interval: Intervalle de temps (par défaut Config.FISHER_INTERVAL)

        Returns:
            La valeur du Fisher Transform (float) ou None en cas d'erreur.
        """
        period = period if period is not None else Config.FISHER_PERIOD
        interval = interval if interval is not None else Config.FISHER_INTERVAL

        exch = self.exchange.lower()
        if exch == "coinbase":
            formatted_symbol = symbol.replace("/USDT", "/USD")
        elif exch == "kraken":
            formatted_symbol = symbol.replace("BTC/", "XBT/").replace("/USDT", "/USD")
        else:
            formatted_symbol = symbol

        try:
            session = await self._ensure_session()
            url = f"{self.endpoint}/fisher"
            params = {
                "secret": self.api_key,
                "exchange": exch,
                "symbol": formatted_symbol,
                "interval": interval,
                "period": period
            }
            self._log(f"Récupération Fisher Transform pour {symbol} (période {period}, intervalle {interval})", "info")
            async with session.get(url, params=params, timeout=0.8) as response:
                if response.status != 200:
                    error_text = await response.text()
                    self._log(f"Erreur API taapi.io fisher ({response.status}): {error_text}", "error")
                    return None
                data = await response.json()
                self._log(f"Réponse brute taapi.io Fisher pour {symbol}: {data}", "info")
                if "value" in data:
                    fisher_value = float(data["value"])
                elif "fisher" in data:
                    fisher_value = float(data["fisher"])
                else:
                    self._log(f"Format de réponse inattendu Fisher: {data}", "error")
                    return None
                self._log(f"Fisher Transform pour {symbol}: {fisher_value}", "info")
                return fisher_value
        except asyncio.TimeoutError:
            self._log(f"Timeout de la requête Fisher pour {symbol}", "error")
            return None
        except aiohttp.ClientError as e:
            self._log(f"Erreur réseau Fisher: {e}", "error")
            return None
        except Exception as e:
            self._log(f"Erreur récupération Fisher pour {symbol}: {e}", "error")
            return None


    async def get_williams_r(self, symbol: str, period: int = None, interval: str = None) -> Optional[float]:
        """
        Récupère la valeur de Williams %R pour un symbole depuis l'API taapi.io.

        Args:
            symbol: Paire de trading (ex: "BTC/USDT")
            period: Période de calcul (défaut Config.WILLIAMS_R_PERIOD)
            interval: Intervalle de temps (défaut Config.WILLIAMS_R_INTERVAL)

        Returns:
            La valeur de Williams %R (float) ou None en cas d'erreur.
        """
        period = period if period is not None else Config.WILLIAMS_R_PERIOD
        interval = interval if interval is not None else Config.WILLIAMS_R_INTERVAL

        exch = self.exchange.lower()
        if exch == "coinbase":
            formatted_symbol = symbol.replace("/USDT", "/USD")
        elif exch == "kraken":
            formatted_symbol = symbol.replace("BTC/", "XBT/").replace("/USDT", "/USD")
        else:
            formatted_symbol = symbol

        try:
            session = await self._ensure_session()
            url = f"{self.endpoint}/willr"
            params = {
                "secret": self.api_key,
                "exchange": exch,
                "symbol": formatted_symbol,
                "interval": interval,
                "period": period

            }
            self._log(f"Récupération Williams %R pour {symbol} (période {period}, intervalle {interval})", "info")
            async with session.get(url, params=params, timeout=0.8) as response:
                if response.status != 200:
                    error_text = await response.text()
                    self._log(f"Erreur API taapi.io Williams %R ({response.status}): {error_text}", "error")
                    return None
                data = await response.json()
                self._log(f"Réponse brute Williams %R pour {symbol}: {data}", "info")
                if "value" in data:
                    value = float(data["value"])
                elif "willr" in data:
                    value = float(data["willr"])
                else:
                    self._log(f"Format de réponse inattendu Williams %R: {data}", "error")
                    return None
                self._log(f"Williams %R pour {symbol}: {value}", "info")
                return value
        except asyncio.TimeoutError:
            self._log(f"Timeout de la requête Williams %R pour {symbol}", "error")
            return None
        except aiohttp.ClientError as e:
            self._log(f"Erreur réseau Williams %R: {e}", "error")
            return None
        except Exception as e:
            self._log(f"Erreur récupération Williams %R pour {symbol}: {e}", "error")
            return None

    # Méthode get_obv supprimée

    async def get_adx(self, symbol: str, period: int = None, interval: str = None) -> Optional[float]:
        """Récupère l'indicateur ADX"""
        period = period if period is not None else Config.ADX_LENGTH
        interval = interval if interval is not None else Config.ADX_INTERVAL
        exch = self.exchange.lower()
        # Mapping du symbole similaire au RSI
        if exch == "coinbase":
            formatted_symbol = symbol.replace("/USDT", "/USD")
        elif exch == "kraken":
            formatted_symbol = symbol.replace("BTC/", "XBT/").replace("/USDT", "/USD")
        else:
            formatted_symbol = symbol
        try:
            session = await self._ensure_session()
            url = f"{self.endpoint}/adx"
            params = {
                "secret": self.api_key,
                "exchange": exch,
                "symbol": formatted_symbol,
                "interval": interval,
                "period": period
            }
            self._log(f"Récupération ADX pour {symbol}", "info")
            async with session.get(url, params=params, timeout=0.8) as response:
                if response.status != 200:
                    return None
                data = await response.json()
                self._log(f"Réponse brute ADX pour {symbol}: {data}", "info")
                if "value" in data:
                    adx_value = float(data["value"])
                else:
                    self._log(f"Format de réponse inattendu ADX pour {symbol}: {data}", "error")
                    return None
                self._update_cache(formatted_symbol, adx_value)
                self._log(f"ADX pour {symbol}: {adx_value}", "info")
                return adx_value
        except Exception:
            return None

    async def get_plus_di(self, symbol: str, period: int = None, interval: str = None) -> Optional[float]:
        """Récupère l'indicateur +DI"""
        period = period if period is not None else Config.DI_LENGTH
        interval = interval if interval is not None else Config.ADX_INTERVAL
        exch = self.exchange.lower()
        # Mapping du symbole similaire au RSI
        if exch == "coinbase":
            formatted_symbol = symbol.replace("/USDT", "/USD")
        elif exch == "kraken":
            formatted_symbol = symbol.replace("BTC/", "XBT/").replace("/USDT", "/USD")
        else:
            formatted_symbol = symbol
        try:
            session = await self._ensure_session()
            url = f"{self.endpoint}/plusdi"
            params = {
                "secret": self.api_key,
                "exchange": exch,
                "symbol": formatted_symbol,
                "interval": interval,
                "period": period
            }
            self._log(f"Récupération +DI pour {symbol}", "info")
            async with session.get(url, params=params, timeout=0.8) as response:
                if response.status != 200:
                    return None
                data = await response.json()
                self._log(f"Réponse brute +DI pour {symbol}: {data}", "info")
                if "value" in data:
                    plusdi_value = float(data["value"])
                elif "plusdi" in data:
                    plusdi_value = float(data["plusdi"])
                else:
                    self._log(f"Format de réponse inattendu +DI pour {symbol}: {data}", "error")
                    return None
                self._update_cache(formatted_symbol, plusdi_value)
                self._log(f"+DI pour {symbol}: {plusdi_value}", "info")
                return plusdi_value
        except Exception:
            return None

    async def get_minus_di(self, symbol: str, period: int = None, interval: str = None) -> Optional[float]:
        """Récupère l'indicateur -DI"""
        period = period if period is not None else Config.DI_LENGTH
        interval = interval if interval is not None else Config.ADX_INTERVAL
        exch = self.exchange.lower()
        # Mapping du symbole similaire au RSI
        if exch == "coinbase":
            formatted_symbol = symbol.replace("/USDT", "/USD")
        elif exch == "kraken":
            formatted_symbol = symbol.replace("BTC/", "XBT/").replace("/USDT", "/USD")
        else:
            formatted_symbol = symbol
        try:
            session = await self._ensure_session()
            url = f"{self.endpoint}/minusdi"
            params = {
                "secret": self.api_key,
                "exchange": exch,
                "symbol": formatted_symbol,
                "interval": interval,
                "period": period
            }
            self._log(f"Récupération -DI pour {symbol}", "info")
            async with session.get(url, params=params, timeout=0.8) as response:
                if response.status != 200:
                    return None
                data = await response.json()
                self._log(f"Réponse brute -DI pour {symbol}: {data}", "info")
                if "value" in data:
                    minusdi_value = float(data["value"])
                elif "minusdi" in data:
                    minusdi_value = float(data["minusdi"])
                else:
                    self._log(f"Format de réponse inattendu -DI pour {symbol}: {data}", "error")
                    return None
                self._update_cache(formatted_symbol, minusdi_value)
                self._log(f"-DI pour {symbol}: {minusdi_value}", "info")
                return minusdi_value
        except Exception:
            return None

    async def get_dmi(self, symbol: str, period: int = None, interval: str = None) -> Optional[Dict[str, float]]:
        """
        Récupère les indicateurs DMI (ADX, +DI, -DI) via l'endpoint /dmi de l'API taapi.io.
        Retourne un dict {'adx': float, 'pdi': float, 'mdi': float} ou None en cas d'erreur.
        """
        period = period if period is not None else Config.ADX_LENGTH
        interval = interval if interval is not None else Config.ADX_INTERVAL
        exch = self.exchange.lower()
        # Mapping du symbole similaire au RSI
        if exch == "coinbase":
            formatted_symbol = symbol.replace("/USDT", "/USD")
        elif exch == "kraken":
            formatted_symbol = symbol.replace("BTC/", "XBT/").replace("/USDT", "/USD")
        else:
            formatted_symbol = symbol
        try:
            session = await self._ensure_session()
            url = f"{self.endpoint}/dmi"
            params = {
                "secret": self.api_key,
                "exchange": exch,
                "symbol": formatted_symbol,
                "interval": interval,
                "period": period
            }
            self._log(f"Récupération DMI pour {symbol}", "info")
            async with session.get(url, params=params, timeout=0.8) as response:
                if response.status != 200:
                    return None
                data = await response.json()
                self._log(f"Réponse brute DMI pour {symbol}: {data}", "info")
                if "adx" in data and "pdi" in data and "mdi" in data:
                    return {
                        "adx": float(data["adx"]),
                        "pdi": float(data["pdi"]),
                        "mdi": float(data["mdi"])
                    }
                self._log(f"Format de réponse inattendu DMI pour {symbol}: {data}", "error")
                return None
        except Exception as e:
            self._log(f"Erreur récupération DMI pour {symbol}: {e}", "error")
            return None


    async def get_rsi_history(self, symbol: str, count: int = 7, period: int = None) -> Optional[List[float]]:
        """
        Récupère l'historique des valeurs RSI pour un symbole depuis l'API taapi.io
        
        Args:
            symbol: Paire de trading (ex: "BTC/USDT")
            count: Nombre de valeurs RSI historiques à récupérer (défaut: 7)
            period: Période du RSI (défaut: Config.RSI_PERIOD)
            
        Returns:
            Une liste des X dernières valeurs RSI (du plus récent au plus ancien) ou None en cas d'erreur
        """
        period = period if period is not None else Config.RSI_PERIOD
        exch = self.exchange.lower()
        
        # Mapping symbole selon l'exchange (même logique que pour get_rsi)
        if exch == "coinbase":
            formatted_symbol = symbol.replace("/USDC", "/USD").replace("/USDT", "/USD")
        elif exch == "kraken":
            formatted_symbol = symbol.replace("BTC/", "XBT/").replace("/USDC", "/USD").replace("/USDT", "/USD")
        else:
            # Pour les autres exchanges comme binance, on convertit USDC en USDT si nécessaire
            formatted_symbol = symbol.replace("/USDC", "/USDT")

        self._log(f"RSI history - Symbole original: {symbol}, symbole formaté: {formatted_symbol}", "info")
            
        try:
            session = await self._ensure_session()
            url = f"{self.endpoint}/rsi"
            params = {
                "secret": self.api_key,
                "exchange": exch,
                "symbol": formatted_symbol,
                "interval": self.interval,
                "period": period,
                "results": count  # Paramètre pour récupérer plusieurs valeurs historiques
            }
            
            self._log(f"Récupération historique RSI ({count} valeurs) pour {symbol}", "info")
            async with session.get(url, params=params, timeout=0.8) as response:
                if response.status != 200:
                    error_text = await response.text()
                    self._log(f"Erreur API taapi.io RSI historique ({response.status}): {error_text}", "error")
                    return None
                    
                data = await response.json()
                self._log(f"Réponse brute taapi.io RSI historique pour {symbol}: {data}", "info")
                
                # Traiter différents formats de réponse possible de l'API
                if isinstance(data, list) and len(data) > 0:
                    # Format 1: tableau d'objets
                    rsi_values = [float(candle.get("value", 0)) for candle in data]
                    self._log(f"Historique RSI (format liste d'objets) pour {symbol} ({len(rsi_values)} valeurs): {rsi_values}", "info")
                    return rsi_values
                elif "value" in data:
                    # Format 2: objet avec clé "value"
                    value = data["value"]
                    if isinstance(value, list):
                        # Si value est une liste de valeurs
                        rsi_values = [float(v) for v in value]
                        self._log(f"Historique RSI (format objet.value=liste) pour {symbol} ({len(rsi_values)} valeurs): {rsi_values}", "info")
                        return rsi_values
                    else:
                        # Si une seule valeur est retournée
                        self._log(f"Historique RSI (format valeur unique) pour {symbol}: [{value}]", "info")
                        return [float(value)]
                else:
                    self._log(f"Format de réponse inattendu pour l'historique RSI: {data}", "error")
                    return None
                    
        except asyncio.TimeoutError:
            self._log(f"Timeout de la requête API historique RSI pour {symbol}", "error")
            return None
        except aiohttp.ClientError as e:
            self._log(f"Erreur réseau historique RSI: {e}", "error")
            return None
        except Exception as e:
            self._log(f"Erreur récupération historique RSI pour {symbol}: {e}", "error")
            return None
    
    def calculate_sma(self, values: List[float]) -> Optional[float]:
        """
        Calcule la moyenne mobile simple (SMA) d'une liste de valeurs
        
        Args:
            values: Liste des valeurs sur lesquelles calculer la SMA
            
        Returns:
            La valeur SMA calculée ou None si la liste est vide
        """
        if not values or len(values) == 0:
            return None
            
        return sum(values) / len(values)
    
    async def get_rsi_sma(self, symbol: str, sma_length: int = 7, period: int = None) -> Optional[float]:
        """
        Récupère l'historique des valeurs RSI et calcule leur SMA
        
        Args:
            symbol: Paire de trading (ex: "BTC/USDT") 
            sma_length: Nombre de valeurs RSI pour calculer la SMA (défaut: 7)
            period: Période du RSI (défaut: Config.RSI_PERIOD)
            
        Returns:
            La valeur SMA calculée sur les X dernières valeurs RSI ou None en cas d'erreur
        """
        self._log(f"Calcul SMA RSI demandé pour {symbol} (length: {sma_length}, period: {period})", "info")
        
        # Récupérer l'historique des valeurs RSI
        rsi_history = await self.get_rsi_history(symbol, sma_length, period)
        
        if not rsi_history or len(rsi_history) == 0:
            self._log(f"Impossible de calculer la SMA RSI pour {symbol}: historique vide", "error")
            return None
            
        # Calculer la SMA
        sma = self.calculate_sma(rsi_history)
        
        if sma is not None:
            self._log(f"SMA RSI pour {symbol} (longueur {sma_length}): {sma:.2f}", "info")
            
        return sma
    
    async def get_indicators_batch(self, symbols: list, indicators: list, period_map: dict = None, interval_map: dict = None) -> dict:
        """
        Récupère en une seule requête plusieurs indicateurs pour une liste de symboles.
        Cette méthode appelle l'endpoint "/multi" de taapi.io pour récupérer les valeurs demandées.
        Args:
            symbols: Liste de symboles (ex: ["BTC/USDC"]).
            indicators: Liste d'indicateurs à récupérer (ex: ["rsi", "willr", "dmi"]).
            period_map: Dictionnaire facultatif précisant la période pour chaque indicateur.
            interval_map: Dictionnaire facultatif précisant l'intervalle pour chaque indicateur.
        Returns:
            Un dictionnaire de la forme { symbole: { indicateur: valeur, ... }, ... } ou {} en cas d'erreur.
        """
        results = {}
        try:
            session = await self._ensure_session()
            url = f"{self.endpoint}/multi"
            for symbol in symbols:
                exch = self.exchange.lower()
                if exch == "coinbase":
                    formatted_symbol = symbol.replace("/USDT", "/USD")
                elif exch == "kraken":
                    formatted_symbol = symbol.replace("BTC/", "XBT/").replace("/USDT", "/USD")
                else:
                    formatted_symbol = symbol
                params = {
                    "secret": self.api_key,
                    "exchange": exch,
                    "symbol": formatted_symbol,
                    "indicators": ",".join(indicators)
                }
                if period_map:
                    for ind, period in period_map.items():
                        params[f"{ind}_period"] = period
                if interval_map:
                    for ind, interval in interval_map.items():
                        params[f"{ind}_interval"] = interval
                async with session.get(url, params=params, timeout=0.8) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        self._log(f"Erreur API taapi.io batch ({response.status}): {error_text}", "error")
                        continue
                    data = await response.json()
                    results[symbol] = data
            return results
        except Exception as e:
            self._log(f"Erreur dans get_indicators_batch: {e}", "error")
            return {}
    
# Instance singleton pour une utilisation facile
taapi_client = TaapiClient()
