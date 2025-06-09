"""Utilitaires pour les interactions avec l'exchange"""
import time
from datetime import datetime
from typing import Optional, Any, Callable, Dict
from functools import wraps
from logger import trading_logger, error_logger

# Importation directe depuis le module spécifique pour éviter l'importation circulaire
from utils.exchange.ccxt_mexc_api import CCXTMexcAPI

def log_event(message: str, level: str = "info") -> None:
    """Centralise la gestion des logs"""
    if level == "info":
        trading_logger.info(message)
    elif level == "error":
        error_logger.error(message)
    print(message)

def retry_operation(max_retries: int = 3, delay: int = 1):
    """Décorateur pour réessayer les opérations qui échouent"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt < max_retries - 1:
                        log_event(
                            f"Tentative {attempt + 1}/{max_retries} échouée: {str(e)}",
                            "error"
                        )
                        time.sleep(delay)
                    else:
                        log_event(f"Échec après {max_retries} tentatives: {str(e)}", "error")
                        raise
            return None
        return wrapper
    return decorator

class ExchangeOperations:
    """Classe utilitaire pour les opérations d'exchange (ordres limites uniquement)"""
    def __init__(self, exchange: CCXTMexcAPI):
        self.exchange = exchange
    
    # Cache pour les balances
    _balance_cache = {}
    _balance_cache_ttl = 3  # Durée de vie du cache en secondes pour les balances (plus court)

    @retry_operation(max_retries=2, delay=1)  # Réduire le nombre de tentatives et le délai
    async def get_balance(self, symbol: str = "USDC") -> Optional[float]:
        """Récupère la balance disponible pour un symbole avec cache"""
        try:
            log_event(f"Vérification de la balance pour {symbol}...")
            
            # Vérifier le cache
            cache_key = f"balance_{symbol}"
            if cache_key in self._balance_cache:
                balance_data = self._balance_cache[cache_key]
                if (datetime.now() - balance_data['timestamp']).total_seconds() < self._balance_cache_ttl:
                    return balance_data['balance']
            
            # Si pas dans le cache ou expiré, récupérer la balance
            balance = await self.exchange.fetch_balance()
            if not balance or symbol not in balance:
                log_event(f"❌ {symbol} non trouvé dans la balance", "error")
                return None
            
            free_balance = float(balance[symbol].get('free', 0))
            total_balance = float(balance[symbol].get('total', 0))
            
            if free_balance < 0 or total_balance < 0:
                log_event("❌ Balance négative détectée", "error")
                return None
            
            # Calculer la balance disponible
            available_balance = min(free_balance, total_balance)
            
            # Mettre en cache
            self._balance_cache[cache_key] = {
                'balance': available_balance,
                'timestamp': datetime.now()
            }
            
            # Log minimal
            log_event(f"Balance {symbol}: {available_balance}")
            
            return available_balance
        except Exception as e:
            log_event(f"❌ Erreur balance: {str(e)}", "error")
            return None

    # Cache pour les prix et les informations de marché
    _price_cache = {}
    _market_info_cache = {}
    _cache_ttl = 1  # Durée de vie du cache en secondes

    @retry_operation(max_retries=2, delay=1)
    async def create_limit_buy_order(self, symbol: str, quantity: Optional[float] = None, 
                                    cost: Optional[float] = None, price: float = None) -> Optional[dict]:
        """Crée un ordre limite d'achat avec possibilité de spécifier le montant en USDC
        # Normaliser le symbole pour MEXC
        symbol = symbol.replace('/USDC','/USDT')
        
        Args:
            symbol: Symbole à acheter (ex: 'BTC/USDC')
            quantity: Quantité à acheter (optionnel si cost est fourni)
            cost: Montant à dépenser en USDC (optionnel si quantity est fourni)
            price: Prix limite
            
        Returns:
            L'ordre créé ou None si échec
        """
        try:
            if not symbol or not price or price <= 0:
                log_event("❌ Paramètres d'ordre limite invalides", "error")
                return None
            
            # Si quantity et cost sont tous les deux spécifiés, priorité à cost
            if quantity is None and cost is None:
                log_event("❌ Ni quantité ni coût spécifié pour l'ordre limite", "error")
                return None
            
            # Vérification rapide de la balance
            quote_currency = symbol.split('/')[1]
            available_balance = await self.get_balance(quote_currency)
            
            if not available_balance:
                log_event(f"❌ Balance insuffisante pour {quote_currency}", "error")
                return None
            
            # Calcul de la quantité si uniquement le coût est fourni
            if quantity is None and cost is not None:
                if cost <= 0:
                    log_event("❌ Coût invalide pour l'ordre limite", "error")
                    return None
                
                # Calculer la quantité en fonction du coût et du prix
                quantity = cost / price
                
                # Vérifier la validité de la quantité calculée
                if quantity <= 0:
                    log_event("❌ Quantité calculée invalide pour l'ordre limite", "error")
                    return None
            
            # Vérification rapide de la balance (avec le coût total)
            estimated_cost = quantity * price
            if estimated_cost > available_balance * 1.05:  # 5% de marge pour les frais et fluctuations
                log_event(f"❌ Balance insuffisante: {available_balance} < {estimated_cost}", "error")
                return None
            
            # Arrondir la quantité selon la précision du marché (à implémenter si nécessaire)
            
            # Paramètres pour CCXT
            params = {
                'timeInForce': 'GTC'  # Good-Till-Canceled
            }
            
            # Créer l'ordre limite
            log_event(f"Création ordre limite achat {symbol}: {quantity} @ {price}")
            
            order = await self.exchange.create_limit_buy_order(
                symbol=symbol,
                price=price,
                amount=quantity,
                cost=cost,
                params=params
            )
            
            if not order:
                log_event("❌ Échec de création d'ordre limite achat", "error")
                return None
            
            log_event(f"✅ Ordre limite achat créé: {symbol}, ID: {order.get('id', 'N/A')}")
            return order
            
        except Exception as e:
            log_event(f"❌ Erreur ordre limite achat: {str(e)}", "error")
            return None
    
    @retry_operation(max_retries=2, delay=1)
    async def create_limit_sell_order(self, symbol: str, quantity: float, price: float) -> Optional[dict]:
        # Normaliser le symbole pour MEXC
        symbol = symbol.replace('/USDC','/USDT')
        """Crée un ordre limite de vente
        
        Args:
            symbol: Symbole à vendre (ex: 'BTC/USDC')
            quantity: Quantité à vendre
            price: Prix limite
            
        Returns:
            L'ordre créé ou None si échec
        """
        try:
            if not symbol or not quantity or quantity <= 0 or not price or price <= 0:
                log_event("❌ Paramètres d'ordre limite vente invalides", "error")
                return None
            
            # Vérification rapide de la balance
            base_currency = symbol.split('/')[0]
            available_balance = await self.get_balance(base_currency)
            
            if not available_balance:
                log_event(f"❌ Balance insuffisante pour {base_currency}", "error")
                return None
            
            # Ajustement rapide de la quantité si nécessaire
            if available_balance < quantity:
                if (quantity - available_balance) / quantity < 0.01:  # Moins de 1% de différence
                    quantity = available_balance  # Utiliser 100% de la balance disponible
                    log_event(f"Ajustement quantité vente limite: {quantity}")
                else:
                    log_event(f"❌ Balance insuffisante: {available_balance} < {quantity}", "error")
                    return None
            
            # Paramètres pour CCXT
            params = {
                'timeInForce': 'GTC'  # Good-Till-Canceled
            }
            
            # Créer l'ordre limite
            log_event(f"Création ordre limite vente {symbol}: {quantity} @ {price}")
            
            order = await self.exchange.create_limit_sell_order(
                symbol=symbol,
                amount=quantity,
                price=price,
                params=params
            )
            
            if not order:
                log_event("❌ Échec de création d'ordre limite vente", "error")
                return None
            
            log_event(f"✅ Ordre limite vente créé: {symbol}, ID: {order.get('id', 'N/A')}")
            return order
            
        except Exception as e:
            log_event(f"❌ Erreur ordre limite vente: {str(e)}", "error")
            return None
    
    @retry_operation(max_retries=2, delay=1)
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Annule un ordre existant
        
        Args:
            order_id: ID de l'ordre à annuler
            symbol: Symbole concerné par l'ordre
            
        Returns:
            True si l'annulation a réussi, False sinon
        """
        try:
            if not order_id or not symbol:
                log_event("❌ Paramètres d'annulation invalides", "error")
                return False
            
            log_event(f"Annulation ordre {order_id} pour {symbol}")
            
            # Annuler l'ordre
            result = await self.exchange.cancel_order(order_id, symbol)
            
            if not result:
                log_event(f"❌ Échec annulation ordre {order_id}", "error")
                return False
            
            log_event(f"✅ Ordre {order_id} annulé avec succès")
            return True
            
        except Exception as e:
            # Capturer l'erreur spécifique d'ordre déjà annulé ou complété
            error_message = str(e).lower()
            if "order not found" in error_message or "already filled" in error_message or "already closed" in error_message:
                log_event(f"Ordre {order_id} déjà complété ou annulé", "info")
                return True  # Considérer comme un succès si l'ordre n'existe plus
            
            log_event(f"❌ Erreur annulation ordre {order_id}: {str(e)}", "error")
            return False
    
    @retry_operation(max_retries=2, delay=1)
    async def get_order_status(self, order_id: str, symbol: str) -> Optional[Dict[str, Any]]:
        """Récupère le statut d'un ordre
        
        Args:
            order_id: ID de l'ordre
            symbol: Symbole concerné par l'ordre
            
        Returns:
            Informations sur l'ordre ou None si erreur
        """
        try:
            if not order_id or not symbol:
                log_event("❌ Paramètres invalides pour récupération ordre", "error")
                return None
            
            # Récupérer l'ordre
            order = await self.exchange.fetch_order(order_id, symbol)
            
            if not order:
                log_event(f"❌ Ordre {order_id} introuvable", "error")
                return None
            
            return order
            
        except Exception as e:
            log_event(f"❌ Erreur récupération ordre {order_id}: {str(e)}", "error")
            return None
