"""Module pour la récupération des données de marché"""
import os
import asyncio
import time
from typing import Dict, Optional, List, Tuple, Any
from datetime import datetime
from dotenv import load_dotenv

# Importation directe depuis le module spécifique pour éviter l'importation circulaire
from utils.exchange.ccxt_mexc_api import CCXTMexcAPI
from logger import trading_logger, error_logger
from constants import MarketConstants as MC
from config import Config
# import de taapi_client retiré : tous les prix sont récupérés via CCXTMexcAPI
from .market_data import MarketData

class DataFetcher:
    """Classe pour la récupération des données de marché"""
    
    def __init__(self, log_callback=None):
        """Initialise le récupérateur de données"""
        self.exchange = None
        self._price_cache = {}
        self._cache_ttl = 60
        self._price_cache_ttl = 1  # Cache de prix live 1 seconde
        self._market_info_cache = {}
        self._market_info_cache_ttl = 300  # 5 minutes en secondes
        self._exchange_initialized = False
        self._log_callback = log_callback
        
    def _log(self, message: str, level: str = "info") -> None:
        """Centralise la gestion des logs"""
        if self._log_callback:
            self._log_callback(message, level)
        else:
            if level == "info":
                trading_logger.info(message)
            elif level == "error":
                error_logger.error(message)
            print(message)
    
    async def init_exchange(self) -> None:
        """Initialise la connexion à l'exchange avec gestion des erreurs"""
        if self._exchange_initialized:
            return
            
        self._log("Chargement des variables d'environnement...")
        load_dotenv()
        
        api_key = os.getenv(MC.API_KEY_ENV)
        api_secret = os.getenv(MC.API_SECRET_ENV)
        
        if not api_key or not api_secret:
            raise ValueError(MC.ERROR_API_KEYS)
        
        self._log("Tentative de connexion à MEXC via CCXT...")
        try:
            # Initialiser notre client API MEXC basé sur CCXT
            self.exchange = CCXTMexcAPI(api_key, api_secret)
            
            # Charger les marchés de manière asynchrone
            await self.exchange.load_markets()
            
            # Tester la connexion
            await self._test_api_permissions()
            self._log("✓ Connexion à MEXC réussie (utilisation exclusive de CCXT)")
            self._exchange_initialized = True
            
        except Exception as e:
            error_logger.error(f"Erreur lors de l'initialisation de l'exchange: {str(e)}")
            raise
    
    async def _test_api_permissions(self) -> None:
        """Teste les permissions de l'API avec retry"""
        self._log("Test des permissions de l'API...")
        try:
            await self.exchange.fetch_balance()
            self._log("✓ Lecture des balances OK")
            # Test réussi, pas besoin d'afficher d'autres messages
        except Exception as e:
            error_logger.error(f"Erreur lors du test des permissions: {str(e)}")
            raise
    
    async def fetch_data_for_symbol(self, symbol: str, operation: str) -> Optional[float]:
        """Récupère les données d'un symbole avec gestion des erreurs et cache"""
        try:
            # Vérifier le cache pour les opérations de prix
            if operation == "price":
                cached_data = self._price_cache.get(symbol)
                if cached_data:
                    price, timestamp = cached_data
                    # Utiliser le TTL spécifique pour le cache de prix pour rafraîchir plus souvent
                    if (datetime.now() - timestamp).total_seconds() < self._price_cache_ttl:
                        return price
            
            if operation in ["initialize", "price", "verify"]:
                ticker = await self.exchange.fetch_ticker(symbol)
                
                if not ticker or 'last' not in ticker:
                    self._log(MC.ERROR_TICKER_DATA.format(symbol), "error")
                    return None
                
                if operation == "price":
                    bid = ticker.get('bid')
                    ask = ticker.get('ask')
                    if bid is not None and ask is not None:
                        price = (float(bid) + float(ask)) / 2
                    else:
                        price = float(ticker['last'])
                else:
                    price = float(ticker['last'])
                
                if operation == "price":
                    self._price_cache[symbol] = (price, datetime.now())
                
                return price
                
        except Exception as e:
            self._log(f"Erreur pour {symbol}: {str(e)}", "error")
            return None
    
    async def verify_symbols(self) -> None:
        """Vérifie la validité des symboles configurés"""
        self._log("Vérification des symboles de trading...")
        invalid_symbols = []
        
        for symbol in Config.CRYPTO_LIST:
            is_valid = await self.fetch_data_for_symbol(symbol, "verify")
            if not is_valid:
                invalid_symbols.append(symbol)
        
        if invalid_symbols:
            raise ValueError(MC.ERROR_INVALID_SYMBOLS.format(", ".join(invalid_symbols)))
        self._log("✓ Tous les symboles sont valides")
    
    async def get_current_price(self, symbol: str) -> Optional[float]:
        """Récupère le prix actuel d'un symbole via fetch_data_for_symbol (moyenne bid/ask ou last)"""
        return await self.fetch_data_for_symbol(symbol, "price")
    
    async def get_market_info(self, symbol: str) -> Optional[dict]:
        """Récupère les informations du marché pour un symbole avec cache"""
        try:
            # Vérifier le cache
            cache_key = f"market_info_{symbol}"
            if cache_key in self._market_info_cache:
                cache_data = self._market_info_cache[cache_key]
                if (datetime.now() - cache_data['timestamp']).total_seconds() < self._market_info_cache_ttl:
                    return cache_data['info']
            
            # Si pas dans le cache ou expiré, récupérer les informations
            if not self.exchange.markets_loaded:
                await self.exchange.load_markets()
            
            market = self.exchange.markets.get(symbol)
            if not market:
                self._log(f"Marché non trouvé pour {symbol}", "error")
                return None
            
            # Extraire les informations pertinentes avec des valeurs par défaut robustes
            market_info = {
                'min_amount': market.get('limits', {}).get('amount', {}).get('min', 0.0001),  # Valeur par défaut sécurisée
                'precision': market.get('precision', {'amount': 8, 'price': 8}),  # Valeurs par défaut sécurisées
                'taker_fee': 0.001,  # Valeur par défaut
                'maker_fee': 0.001   # Valeur par défaut
            }
            
            # Mettre en cache
            self._market_info_cache[cache_key] = {
                'info': market_info,
                'timestamp': datetime.now()
            }
            
            return market_info
        except Exception as e:
            self._log(f"Erreur infos marché: {str(e)}", "error")
            return None
    
    async def fetch_ohlcv_batch(self, symbols: List[str], max_period: int) -> Dict[str, List]:
        """Récupère les données OHLCV pour plusieurs symboles en parallèle
        
        Version optimisée qui gère correctement l'annulation des tâches et utilise des valeurs par défaut robustes.
        Le RSI est maintenant géré par l'API taapi.io, donc cette méthode ne sert plus qu'à récupérer
        les données pour les bandes de Bollinger et l'analyse de volume.
        """
        results = {}
        
        # Récupérer suffisamment de données pour les indicateurs techniques (sauf RSI)
        # Nous conservons 30 points, suffisants pour les bandes de Bollinger et l'analyse de volume
        fetch_period = 30
        
        # Récupérer les données OHLCV pour tous les symboles (un à la fois pour éviter les problèmes d'annulation)
        for symbol in symbols:
            try:
                # Utiliser l'intervalle de 1 minute pour des données récentes
                ohlcv = await self.exchange.fetch_ohlcv(symbol, '1m', None, fetch_period)
                
                if not ohlcv or len(ohlcv) < 20:  # Minimum requis pour les BB
                    self._log(f"❌ Données OHLCV insuffisantes pour {symbol}", "error")
                    # Générer des données factices pour éviter les erreurs
                    # Cela permettra au bot de continuer à fonctionner même en cas de problème
                    current_price = await self.get_current_price(symbol) or 1.0
                    fake_ohlcv = [[int(time.time() * 1000) - (i * 60000), 
                                  current_price, current_price, 
                                  current_price * 0.99, current_price, 
                                  1000.0] for i in range(30)]
                    results[symbol] = fake_ohlcv
                else:
                    results[symbol] = ohlcv
                    
            except asyncio.CancelledError:
                # Gérer proprement l'annulation de la tâche
                self._log(f"Récupération des données OHLCV pour {symbol} annulée", "info")
                # Ne pas propager l'exception pour permettre un arrêt propre
                results[symbol] = None
            except Exception as e:
                self._log(f"❌ Erreur lors de la récupération des données OHLCV pour {symbol}: {str(e)}", "error")
                results[symbol] = None
        
        return results
    
    async def load_historical_data(self, market_data: Dict[str, MarketData]) -> None:
        """Charge les données historiques pour les indicateurs techniques"""
        self._log("Chargement des données historiques pour les indicateurs...")
        
        # Période maximale nécessaire pour les indicateurs (uniquement RSI maintenant)
        max_period = Config.RSI_PERIOD * 2  # Multiplier par 2 pour avoir suffisamment de données
        
        # Période pour les données de tendance (pour l'analyse de tendance)
        period_trend = 24 * 60  # 24 heures en minutes
        
        for symbol in Config.CRYPTO_LIST:
            try:
                # Récupérer les données OHLCV (Open, High, Low, Close, Volume)
                fetch_count = max(max_period, period_trend, 55)  # Au moins 55 points pour un RSI précis
                ohlcv = await self.exchange.fetch_ohlcv(symbol, '1m', None, fetch_count)
                
                if not ohlcv or len(ohlcv) < 55:  # Minimum requis pour un calcul RSI précis
                    self._log(f"❌ Données historiques insuffisantes pour {symbol}", "error")
                    continue
                
                # Extraire les prix de clôture et les volumes
                closes = [x[4] for x in ohlcv]  # Prix de clôture
                volumes = [x[5] for x in ohlcv]  # Volume
                
                # Stocker les données historiques
                symbol_market_data = market_data.get(symbol)
                if symbol_market_data:
                    symbol_market_data.price_history = closes
                    symbol_market_data.volume_history = volumes
                

                
                self._log(f"✓ Données historiques chargées pour {symbol} ({len(closes)} points)")
                
            except Exception as e:
                self._log(f"❌ Erreur lors du chargement des données historiques pour {symbol}: {str(e)}", "error")
