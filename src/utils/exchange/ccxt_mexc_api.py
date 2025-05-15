"""Module d'API MEXC utilisant exclusivement CCXT

Ce module implémente une approche unifiée pour interagir avec l'exchange MEXC,
utilisant exclusivement la bibliothèque CCXT pour toutes les opérations:
- Récupération des données de marché (tickers, OHLCV, etc.)
- Opérations de trading (ordres limites uniquement)
- Gestion du compte (balance, historique des transactions, etc.)

Cette approche simplifie la codebase et garantit une compatibilité avec 
différents exchanges si besoin dans le futur.
"""

import os
import time
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

# Import CCXT de manière sécurisée
try:
    import ccxt.async_support as ccxt
except Exception:
    ccxt = None

import uuid
from logger import trading_logger, error_logger

class CCXTMexcAPI:
    """Classe utilisant exclusivement CCXT pour toutes les interactions avec MEXC"""
    
    def __init__(self, api_key: str, api_secret: str):
        """Initialise le client API MEXC basé sur CCXT.
           Mode réel pour les ordres avec CCXT."""
        self.simulation = False
        # Initialiser l'instance CCXT pour la récupération de données et ordres réels
        if ccxt is None:
            self._log("Import CCXT asynchrone échoué : CCXT non disponible", "error")
            raise RuntimeError("CCXT asynchrone non disponible")
        self.ccxt_instance = ccxt.mexc({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
                'adjustForTimeDifference': True,
                'recvWindow': 60000,  # 60 secondes
                'createOrderDefaultExpiry': 30000  # 60 secondes
            }
        })
        self._log("Client API CCXT pour MEXC initialisé")
        
        # Attributs pour la compatibilité avec le code existant
        self.markets = {}
        self.markets_loaded = False
        
        # Cache pour les données fréquemment utilisées
        self._ticker_cache = {}
        self._balance_cache = {}
        self._ohlcv_cache = {}
        
        # TTL du cache en secondes
        self._ticker_cache_ttl = 1
        self._balance_cache_ttl = 1
        self._ohlcv_cache_ttl = 0.5 # 2 secondes pour actualiser les données fréquemment
        
        self._log("Client API CCXT pour MEXC initialisé")
    
    def _log(self, message: str, level: str = "info") -> None:
        """Centralise la gestion des logs"""
        if level == "info":
            trading_logger.info(message)
        elif level == "error":
            error_logger.error(message)
        print(message)
    
    async def close(self):
        """Ferme la connexion CCXT"""
        try:
            await self.ccxt_instance.close()
            self._log("Connexion API MEXC fermée")
        except Exception as e:
            self._log(f"Erreur lors de la fermeture de la connexion: {str(e)}", "error")
    
    # ========== MÉTHODES DE DONNÉES (UTILISANT CCXT) ==========
    
    async def load_markets(self) -> Dict[str, Any]:
        """Charge les informations sur tous les marchés disponibles
        
        Returns:
            Dict[str, Any]: Informations sur les marchés
        """
        # En mode simulation sans CCXT, on ignore le chargement des marchés
        if self.ccxt_instance is None:
            self._log("CCXT non initialisé, skip load_markets (simulation)", "info")
            self.markets_loaded = True
            return self.markets
        if self.markets_loaded:
            return self.markets
        
        try:
            # Charger les marchés via CCXT
            ccxt_markets = await self.ccxt_instance.load_markets()
            
            # Convertir au format attendu par le code existant
            for symbol, market_info in ccxt_markets.items():
                self.markets[symbol] = market_info
            
            self.markets_loaded = True
            self._log(f"Marchés chargés via CCXT: {len(self.markets)} paires de trading")
            
            return self.markets
        except Exception as e:
            self._log(f"Erreur lors du chargement des marchés via CCXT: {str(e)}", "error")
            raise
    
    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """Récupère le prix actuel d'un symbole
        
        Args:
            symbol: Symbole au format standard (ex: BTC/USDT)
            
        Returns:
            Dict[str, Any]: Informations sur le ticker
        """
        # Vérifier le cache
        cache_key = f"ticker_{symbol}"
        if cache_key in self._ticker_cache:
            cache_data = self._ticker_cache[cache_key]
            if (datetime.now() - cache_data['timestamp']).total_seconds() < self._ticker_cache_ttl:
                return cache_data['data']
        
        try:
            # Récupérer le ticker via CCXT
            ticker = await self.ccxt_instance.fetch_ticker(symbol)
            
            # Mettre en cache
            self._ticker_cache[cache_key] = {
                'data': ticker,
                'timestamp': datetime.now()
            }
            
            return ticker
        except Exception as e:
            self._log(f"Erreur lors de la récupération du ticker via CCXT pour {symbol}: {str(e)}", "error")
            raise
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1m', since: Optional[int] = None, 
                         limit: Optional[int] = None) -> List[List[float]]:
        """Récupère les données historiques OHLCV
        
        Args:
            symbol: Symbole au format standard (ex: BTC/USDT)
            timeframe: Intervalle de temps (1m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d)
            since: Timestamp de début (en millisecondes)
            limit: Nombre maximum de bougies à récupérer
            
        Returns:
            List[List[float]]: Données OHLCV au format [timestamp, open, high, low, close, volume]
        """
        # Vérifier le cache
        cache_key = f"ohlcv_{symbol}_{timeframe}_{since}_{limit}"
        if cache_key in self._ohlcv_cache:
            cache_data = self._ohlcv_cache[cache_key]
            if (datetime.now() - cache_data['timestamp']).total_seconds() < self._ohlcv_cache_ttl:
                return cache_data['data']
        
        try:
            # Récupérer les données OHLCV via CCXT
            ohlcv = await self.ccxt_instance.fetch_ohlcv(symbol, timeframe, since, limit)
            
            # Mettre en cache
            self._ohlcv_cache[cache_key] = {
                'data': ohlcv,
                'timestamp': datetime.now()
            }
            
            return ohlcv
        except Exception as e:
            self._log(f"Erreur lors de la récupération des données OHLCV via CCXT pour {symbol}: {str(e)}", "error")
            raise
    
    async def fetch_balance(self) -> Dict[str, Any]:
        """Récupère les balances du compte
        
        Returns:
            Dict[str, Any]: Balances du compte
        """
        # Vérifier le cache
        if self._balance_cache:
            cache_data = self._balance_cache
            if (datetime.now() - cache_data['timestamp']).total_seconds() < self._balance_cache_ttl:
                return cache_data['data']
        
        try:
            # Récupérer les balances via CCXT
            balance = await self.ccxt_instance.fetch_balance()
            
            # Mettre en cache
            self._balance_cache = {
                'data': balance,
                'timestamp': datetime.now()
            }
            
            return balance
        except Exception as e:
            self._log(f"Erreur lors de la récupération des balances via CCXT: {str(e)}", "error")
            raise
    
    # ========== MÉTHODES D'ORDRES (UNIQUEMENT ORDRES LIMITES) ==========
    
    async def create_limit_buy_order(self, symbol: str, price: float, amount: Optional[float] = None, 
                                    cost: Optional[float] = None, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Crée un ordre d'achat limite à un prix spécifié
        
        Args:
            symbol: Symbole au format standard (ex: BTC/USDT)
            price: Prix limite pour l'achat
            amount: Quantité à acheter (en unités de la crypto)
            cost: Montant à dépenser (en unités de la devise de cotation)
            params: Paramètres supplémentaires
            
        Returns:
            Dict: Informations sur l'ordre créé
        """
        if self.simulation:
            fake_id = str(uuid.uuid4())
            timestamp = int(datetime.now().timestamp() * 1000)
            amount_calc = amount if amount is not None else (cost / price if cost else 0)
            order = {
                'id': fake_id,
                'symbol': symbol,
                'timestamp': timestamp,
                'datetime': datetime.utcnow().isoformat(),
                'type': 'limit',
                'side': 'buy',
                'price': price,
                'amount': amount_calc,
                'filled': amount_calc,
                'remaining': 0,
                'status': 'closed',
                'average': price
            }
            self._log(f"Simulation d'ordre d'achat : {fake_id}")
            return order
        if params is None:
            params = {}
            
        try:
            # Gestion du cas où on a le coût plutôt que la quantité
            if amount is None and cost is not None:
                # Calculer la quantité à partir du coût et du prix
                amount = cost / price
                self._log(f"Quantité calculée à partir du coût: {amount} (coût: {cost}, prix: {price})")
                
            # Vérification des paramètres
            if amount is None or amount <= 0:
                raise ValueError(f"Quantité invalide pour create_limit_buy_order: {amount}")
                
            if price is None or price <= 0:
                raise ValueError(f"Prix invalide pour create_limit_buy_order: {price}")
            
            # Créer l'ordre limite d'achat via CCXT
            self._log(f"Création d'un ordre limite d'achat pour {symbol}: quantité={amount}, prix={price}")
            order = await self.ccxt_instance.create_limit_buy_order(symbol, amount, price, params)
            
            self._log(f"Ordre limite d'achat créé avec succès: {order['id']}")
            return order
            
        except Exception as e:
            self._log(f"Erreur lors de la création de l'ordre limite d'achat: {str(e)}", "error")
            raise
    
    async def create_limit_sell_order(self, symbol: str, amount: float, price: float, 
                                     params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Crée un ordre de vente limite à un prix spécifié
        
        Args:
            symbol: Symbole au format standard (ex: BTC/USDT)
            amount: Quantité à vendre (en unités de la crypto)
            price: Prix limite pour la vente
            params: Paramètres supplémentaires
            
        Returns:
            Dict: Informations sur l'ordre créé
        """
        if self.simulation:
            fake_id = str(uuid.uuid4())
            timestamp = int(datetime.now().timestamp() * 1000)
            order = {
                'id': fake_id,
                'symbol': symbol,
                'timestamp': timestamp,
                'datetime': datetime.utcnow().isoformat(),
                'type': 'limit',
                'side': 'sell',
                'price': price,
                'amount': amount,
                'filled': amount,
                'remaining': 0,
                'status': 'closed',
                'average': price
            }
            self._log(f"Simulation d'ordre de vente : {fake_id}")
            return order
        if params is None:
            params = {}
            
        try:
            # Vérification des paramètres
            if amount is None or amount <= 0:
                raise ValueError(f"Quantité invalide pour create_limit_sell_order: {amount}")
                
            if price is None or price <= 0:
                raise ValueError(f"Prix invalide pour create_limit_sell_order: {price}")
            
            # Créer l'ordre limite de vente via CCXT
            self._log(f"Création d'un ordre limite de vente pour {symbol}: quantité={amount}, prix={price}")
            order = await self.ccxt_instance.create_limit_sell_order(symbol, amount, price, params)
            
            self._log(f"Ordre limite de vente créé avec succès: {order['id']}")
            return order
            
        except Exception as e:
            self._log(f"Erreur lors de la création de l'ordre limite de vente: {str(e)}", "error")
            raise
    
    async def fetch_order(self, id: str, symbol: str) -> Dict[str, Any]:
        """Récupère les informations sur un ordre
        
        Args:
            id: Identifiant de l'ordre
            symbol: Symbole au format standard (ex: BTC/USDT)
            
        Returns:
            Dict: Informations sur l'ordre
        """
        try:
            # Récupérer les informations sur l'ordre via CCXT
            order = await self.ccxt_instance.fetch_order(id, symbol)
            return order
            
        except Exception as e:
            self._log(f"Erreur lors de la récupération de l'ordre {id} pour {symbol}: {str(e)}", "error")
            raise
    
    async def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Récupère les ordres ouverts
        
        Args:
            symbol: Symbole au format standard (ex: BTC/USDT) ou None pour tous les symboles
            
        Returns:
            List[Dict]: Liste des ordres ouverts
        """
        try:
            # Récupérer les ordres ouverts via CCXT
            orders = await self.ccxt_instance.fetch_open_orders(symbol)
            return orders
            
        except Exception as e:
            symbol_info = f" pour {symbol}" if symbol else ""
            self._log(f"Erreur lors de la récupération des ordres ouverts{symbol_info}: {str(e)}", "error")
            raise
    
    async def cancel_order(self, id: str, symbol: str) -> Dict[str, Any]:
        """Annule un ordre
        
        Args:
            id: Identifiant de l'ordre
            symbol: Symbole au format standard (ex: BTC/USDT)
            
        Returns:
            Dict: Informations sur l'annulation
        """
        try:
            if self.simulation:
                self._log(f"Simulation d'annulation de l'ordre {id} pour {symbol}")
                return {'id': id, 'symbol': symbol, 'status': 'canceled'}
            # Annuler l'ordre via CCXT
            self._log(f"Annulation de l'ordre {id} pour {symbol}")
            result = await self.ccxt_instance.cancel_order(id, symbol)
            
            self._log(f"Ordre {id} annulé avec succès")
            return result
            
        except Exception as e:
            self._log(f"Erreur lors de l'annulation de l'ordre {id} pour {symbol}: {str(e)}", "error")
            raise
    
    async def cancel_all_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Annule tous les ordres ouverts
        
        Args:
            symbol: Symbole au format standard (ex: BTC/USDT) ou None pour tous les symboles
            
        Returns:
            List[Dict]: Liste des résultats d'annulation
        """
        try:
            symbol_info = f" pour {symbol}" if symbol else ""
            self._log(f"Annulation de tous les ordres ouverts{symbol_info}")
            
            # Récupérer d'abord tous les ordres ouverts
            open_orders = await self.fetch_open_orders(symbol)
            
            # Annuler chaque ordre individuellement
            results = []
            for order in open_orders:
                order_id = order['id']
                order_symbol = order['symbol']
                result = await self.cancel_order(order_id, order_symbol)
                results.append(result)
            
            self._log(f"{len(results)} ordres annulés avec succès")
            return results
            
        except Exception as e:
            symbol_info = f" pour {symbol}" if symbol else ""
            self._log(f"Erreur lors de l'annulation de tous les ordres{symbol_info}: {str(e)}", "error")
            raise
    
    async def fetch_my_trades(self, symbol: str, since: Optional[int] = None, 
                             limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Récupère l'historique des trades du compte
        
        Args:
            symbol: Symbole au format standard (ex: BTC/USDT)
            since: Timestamp de début (en millisecondes)
            limit: Nombre maximum de trades à récupérer
            
        Returns:
            List[Dict]: Liste des trades
        """
        try:
            # Récupérer l'historique des trades via CCXT
            trades = await self.ccxt_instance.fetch_my_trades(symbol, since, limit)
            return trades
            
        except Exception as e:
            self._log(f"Erreur lors de la récupération de l'historique des trades pour {symbol}: {str(e)}", "error")
            raise
    
    # ========== MÉTHODES UTILITAIRES ==========
    
    async def get_market_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Récupère les informations du marché pour un symbole
        
        Args:
            symbol: Symbole au format standard (ex: BTC/USDT)
            
        Returns:
            Optional[Dict[str, Any]]: Informations du marché
        """
        if not self.markets_loaded:
            await self.load_markets()
        
        market = self.markets.get(symbol)
        if not market:
            self._log(f"Marché non trouvé pour {symbol}", "error")
            return None
        
        # Extraire les informations pertinentes
        market_info = {
            'min_amount': market.get('limits', {}).get('amount', {}).get('min', 0.0001),
            'precision': market.get('precision', {'amount': 8, 'price': 8}),
            'taker_fee': market.get('taker', 0.001),
            'maker_fee': market.get('maker', 0.001)
        }
        
        return market_info
