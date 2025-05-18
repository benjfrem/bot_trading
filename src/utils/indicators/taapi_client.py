"""
Module client pour l'API taapi.io

Ce module fournit un client asynchrone pour récupérer des indicateurs techniques
depuis l'API taapi.io. Il gère notamment le caching et la transformation des données.
"""
import aiohttp
import asyncio
import time
from typing import Dict, Optional
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

        # Vérifier le cache (désactivé)
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
                "backtrack": 1
            }
            # suppression du log de requête TAAPI pour épurer la sortie  
            # self._log(f"URL: {url} - Params: {params}", "info")

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

    async def get_stochastic(self, symbol: str, interval: Optional[str] = None, 
                             k_length: Optional[int] = None, k_smooth: Optional[int] = None,
                             d_smooth: Optional[int] = None) -> Optional[dict]:
        """
        Récupère les valeurs de l'oscillateur stochastique pour un symbole depuis l'API taapi.io

        Args:
            symbol: Paire de trading (ex: "BTC/USDT")
            interval: Intervalle de temps pour l'indicateur (ex: "5m")
            k_length: Période pour le calcul de %K (défaut: Config.STOCH_K_LENGTH)
            k_smooth: Lissage pour %K (défaut: Config.STOCH_K_SMOOTH)
            d_smooth: Lissage pour %D (défaut: Config.STOCH_D_SMOOTH)

        Returns:
            Un dictionnaire contenant les valeurs de %K et %D, ou None en cas d'erreur
        """
        # Utilisation des valeurs par défaut de la configuration si non spécifiées
        interval = interval if interval is not None else Config.STOCH_TIMEFRAME
        k_length = k_length if k_length is not None else Config.STOCH_K_LENGTH
        k_smooth = k_smooth if k_smooth is not None else Config.STOCH_K_SMOOTH
        d_smooth = d_smooth if d_smooth is not None else Config.STOCH_D_SMOOTH
        
        exch = self.exchange.lower()
        # Mapping du symbole selon l'exchange
        if exch == "coinbase":
            formatted_symbol = symbol.replace("/USDT", "/USD")
        elif exch == "kraken":
            formatted_symbol = symbol.replace("BTC/", "XBT/").replace("/USDT", "/USD")
        else:
            formatted_symbol = symbol
            
        try:
            session = await self._ensure_session()
            url = f"{self.endpoint}/stoch"
            params = {
                "secret": self.api_key,
                "exchange": exch,
                "symbol": formatted_symbol,
                "interval": interval,
                "kPeriod": k_length,
                "dPeriod": d_smooth,
                "kSmooth": k_smooth,
                "backtrack": 1
            }
            
            self._log(f"Récupération stochastique pour {symbol} avec intervalle {interval}", "info")
            
            async with session.get(url, params=params, timeout=0.8) as response:
                if response.status != 200:
                    error_text = await response.text()
                    self._log(f"Erreur API taapi.io stochastique ({response.status}): {error_text}", "error")
                    return None

                data = await response.json()
                self._log(f"Réponse brute taapi.io stochastique pour {symbol}: {data}", "info")
                
                # Vérification des clés attendues
                if "valueK" not in data or "valueD" not in data:
                    self._log(f"Format de réponse stochastique inattendu: {data}", "error")
                    return None

                # Extraction des valeurs K et D
                stoch_values = {
                    "valueK": float(data["valueK"]),
                    "valueD": float(data["valueD"])
                }
                
                self._log(f"Stochastique pour {symbol}: %K={stoch_values['valueK']:.2f}, %D={stoch_values['valueD']:.2f}", "info")
                return stoch_values

        except asyncio.TimeoutError:
            self._log(f"Timeout de la requête stochastique pour {symbol}", "error")
            return None
        except aiohttp.ClientError as e:
            self._log(f"Erreur réseau stochastique: {e}", "error")
            return None
        except Exception as e:
            self._log(f"Erreur récupération stochastique pour {symbol}: {e}", "error")
            return None
            
    async def get_dmi_negative(self, symbol: str, period: Optional[int] = None, smoothing: Optional[int] = None) -> Optional[float]:
        """Récupère la composante DMI− pour un symbole depuis l'API taapi.io"""
        period = period if period is not None else Config.DMI_NEGATIVE_LENGTH
        smoothing = smoothing if smoothing is not None else Config.DMI_NEGATIVE_SMOOTHING
        exch = self.exchange.lower()
        # Mapping du symbole selon l'exchange
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
                "interval": "5m",
                "period": period,
                "smoothing": smoothing,
                "backtrack": 1
            }
            async with session.get(url, params=params, timeout=0.8) as response:
                if response.status != 200:
                    error_text = await response.text()
                    self._log(f"Erreur API taapi.io DMI− ({response.status}): {error_text}", "error")
                    return None
                data = await response.json()
                self._log(f"Réponse brute taapi.io DMI− pour {symbol}: {data}", "info")
                # Extraction de la valeur négative/adx
                if "adx" in data:
                    dmi_value = float(data["adx"])
                    return dmi_value
                # Extraction de la valeur négative
                if "valueMinusDi" in data:
                    dmi_value = float(data["valueMinusDi"])
                elif "minus_dm" in data:
                    dmi_value = float(data["minus_dm"])
                elif "mdi" in data:
                    dmi_value = float(data["mdi"])
                elif "value" in data:
                    dmi_value = float(data["value"])
                else:
                    self._log(f"Format de réponse DMI− inattendu: {data}", "error")
                    return None
                return dmi_value
        except asyncio.TimeoutError:
            self._log(f"Timeout de la requête DMI− pour {symbol}", "error")
            return None
        except aiohttp.ClientError as e:
            self._log(f"Erreur réseau DMI−: {e}", "error")
            return None
        except Exception as e:
            self._log(f"Erreur récupération DMI− pour {symbol}: {e}", "error")
            return None


# Instance singleton pour une utilisation facile
taapi_client = TaapiClient()
