"""Module de gestion des positions"""
import asyncio
from datetime import datetime
from typing import Optional, Dict

from config import Config
from models.position import Position
from utils.exchange.exchange_utils import log_event
from utils.trading.adaptive_stoploss import StopLossManager
from utils.trading.trailing_stop import TrailingStopLoss
from utils.trading.limit_order_manager import LimitOrderManager

class PositionManager:
    """Classe pour la gestion des positions"""

    def __init__(self, portfolio_manager):
        self.portfolio_manager = portfolio_manager
        self.limit_order_manager: Optional[LimitOrderManager] = None
        self.pending_orders: Dict[str, Dict] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        # Binding can_open_position pour garantir que l'attribut existe à l'exécution
        self.can_open_position = self.can_open_position.__get__(self, self.__class__)

    def _get_lock(self, symbol: str) -> asyncio.Lock:
        """Retourne un verrou unique par symbole pour éviter les appels concurrentiels"""
        lock = self._locks.get(symbol)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[symbol] = lock
        return lock

    def _ensure_limit_order_manager(self):
        """Initialise le gestionnaire d'ordres limites si nécessaire"""
        if self.limit_order_manager is None:
            self.limit_order_manager = LimitOrderManager(self.portfolio_manager.exchange_ops.exchange)
            log_event("Gestionnaire d'ordres limites initialisé")

    def _determine_optimal_limit_price(self, current_price: float) -> float:
        """Retourne le prix ajusté pour un ordre limit 1% au-dessus du prix du marché"""
        adjusted_price = current_price * 1.01
        log_event(f"""
=== ACHAT LIMIT 1% AU-DESSUS DU MARCHÉ ===
   Prix marché: {current_price:.8f}
   Prix limite: {adjusted_price:.8f}
   Écart: 1.00%
""")
        return adjusted_price

    async def _handle_order_timeout(self, symbol: str, price: float, position_size: float) -> None:
        """Callback exécuté si un ordre limite expire"""
        self.pending_orders.pop(symbol, None)
        self._ensure_limit_order_manager()
        attempt = self.limit_order_manager.get_buy_attempt_count(symbol)
        max_attempts = 5
        log_event(f"""
=== TIMEOUT ACHAT (TENTATIVE {attempt}/{max_attempts}) ===
   Symbole: {symbol}
   Prix initial: {price:.8f}
""")
        if symbol in self.portfolio_manager.positions:
            log_event(f"Suppression position {symbol} après timeout")
            del self.portfolio_manager.positions[symbol]
            self.portfolio_manager.trailing_stops.pop(symbol, None)
        if attempt < max_attempts:
            try:
                current_price = await self.portfolio_manager.market_analyzer.get_current_price(symbol)
                if not current_price or current_price <= 0:
                    log_event(f"❌ Impossible de récupérer le prix actuel pour {symbol}", "error")
                    return
                log_event(f"=== REESSAI ACHAT {attempt+1}/{max_attempts} à {current_price:.8f} ===")
                await self.open_position(symbol, current_price, position_size, is_retry=True)
            except Exception as e:
                log_event(f"❌ Erreur lors réessai achat: {e}", "error")
        else:
            log_event(f"❌ Échec après {max_attempts} tentatives pour {symbol}", "error")
            self.limit_order_manager.reset_buy_attempts(symbol)
            md = self.portfolio_manager.market_analyzer.market_data.get(symbol)
            if md and hasattr(md, 'trailing_buy_rsi'):
                md.trailing_buy_rsi.reset()
                log_event(f"Trailing Buy RSI réinitialisé pour {symbol}")

    async def open_position(self, symbol: str, price: float, position_size: float = 1.0, is_retry: bool = False) -> bool:
        """Ouvre une nouvelle position: achat fixe de Config.TRANSACTION_QUANTITY ETH avec verrouillage"""
        lock = self._get_lock(symbol)
        async with lock:
            if symbol in self.pending_orders:
                log_event(f"Annulation de l'ordre en attente pour {symbol}", "info")
                self._ensure_limit_order_manager()
                await self.limit_order_manager.cancel_all_orders(symbol)
                del self.pending_orders[symbol]

            self.pending_orders[symbol] = {"state": "initiated"}
            log_event(f"Ouverture position {symbol}: qt={Config.TRANSACTION_QUANTITY} ETH à ~{price:.8f}")
            self._ensure_limit_order_manager()

            if not is_retry:
                self.limit_order_manager.reset_buy_attempts(symbol)
                await self.limit_order_manager.cancel_all_orders(symbol)

            if symbol in self.portfolio_manager.positions:
                log_event(f"❌ Position existante pour {symbol}", "error")
                self.pending_orders.pop(symbol, None)
                return False
            if len(self.portfolio_manager.positions) >= Config.MAX_POSITIONS:
                log_event(f"❌ Nombre max de positions atteint", "error")
                self.pending_orders.pop(symbol, None)
                return False

            quantity = Config.TRANSACTION_QUANTITY
            required_cost = quantity * price
            available_balance = await self.portfolio_manager.exchange_ops.get_balance()
            if not available_balance or available_balance < required_cost:
                log_event(f"❌ Balance insuffisante ({available_balance} USDC, requis {required_cost})", "error")
                self.pending_orders.pop(symbol, None)
                return False

            limit_price = self._determine_optimal_limit_price(price)
            log_event(f"=== OPTIMISATION ORDRE LIMITÉ ===\n   Marché: {price:.8f}\n   Limite: {limit_price:.8f}\n   Écart: {((limit_price-price)/price)*100:.4f}%")

            async def on_timeout():
                self.pending_orders.pop(symbol, None)
                await self._handle_order_timeout(symbol, price, position_size)

            async def on_fill(order_info):
                await self._process_successful_buy_order(symbol, order_info)

            attempt = self.limit_order_manager.get_buy_attempt_count(symbol) + 1
            log_event(f"📤 Tentative {attempt}/3: {Config.TRANSACTION_QUANTITY} ETH à {limit_price:.8f}")
            self.pending_orders[symbol].update({"quantity": quantity, "limit_price": limit_price, "attempt": attempt})

            order = await self.limit_order_manager.create_limit_buy_order(
                symbol=symbol,
                amount=quantity,
                price=limit_price,
                timeout=4,
                on_timeout_callback=on_timeout,
                on_fill_callback=on_fill,
                attempt=attempt,
                max_attempts=3
            )
            if not order:
                log_event("❌ Échec création ordre limite", "error")
                self.pending_orders.pop(symbol, None)
                return False

            log_event(f"⏳ Ordre créé: {order.get('id')} en attente")
            return True

    async def can_open_position(self, symbol: str = None) -> bool:
        """Vérifie si une nouvelle position peut être ouverte"""
        try:
            if symbol and symbol in self.pending_orders:
                return False
            if symbol and symbol in self.portfolio_manager.positions:
                return False
            if len(self.portfolio_manager.positions) >= Config.MAX_POSITIONS:
                log_event(f"❌ Maximum de positions atteint: {len(self.portfolio_manager.positions)}/{Config.MAX_POSITIONS}", "error")
                return False
            balance = await self.portfolio_manager.exchange_ops.get_balance()
            if not balance or balance < Config.TRANSACTION_QUANTITY:
                log_event(f"❌ Balance insuffisante: {balance}", "error")
                return False
            return True
        except Exception as e:
            log_event(f"❌ Erreur can_open_position: {e}", "error")
            return False

    async def _process_successful_buy_order(self, symbol: str, order: dict) -> bool:
        """Met à jour la position après ordre acheté"""
        if not order:
            log_event("❌ Callback on_fill sans order_info", "error")
            return False
        price_avg = float(order.get('average') or 0)
        qty_filled = float(order.get('filled') or order.get('amount') or 0)
        if price_avg <= 0 or qty_filled <= 0:
            log_event("❌ Données ordre invalides", "error")
            return False

        latest_opps = getattr(self.portfolio_manager.market_analyzer, 'latest_opportunities', [])
        opportunity = next((opp for opp in latest_opps if opp.get('symbol') == symbol), None)
        trailing_levels = opportunity.get('trailing_stop_levels', Config.TRAILING_STOP_LEVELS) if opportunity else Config.TRAILING_STOP_LEVELS

        pos = Position(symbol=symbol, entry_price=price_avg, quantity=qty_filled, timestamp=datetime.now(), order_id=order.get('id',''), total_cost=price_avg*qty_filled)
        self.portfolio_manager.positions[symbol] = pos

        adx = opportunity.get('adx', 0) if opportunity else 0
        plus_di = opportunity.get('plus_di', 0) if opportunity else 0
        minus_di = opportunity.get('minus_di', 0) if opportunity else 0
        if adx >= 25:
            multiplier = 2.2 if plus_di > minus_di else 1.2
        else:
            multiplier = 1.6
        log_event(f"SL adaptatif choisi : ATR×{multiplier:.2f} (ADX={adx:.2f}, +DI={plus_di:.2f}, -DI={minus_di:.2f})", "info")
        self.portfolio_manager.trailing_stops[symbol] = StopLossManager(entry_price=price_avg, symbol=symbol, multiplier=multiplier)
        
        # CORRECTION: Suppression du paramètre "levels" qui n'est pas attendu par TrailingStopLoss
        self.portfolio_manager.trailing_stop_paliers[symbol] = TrailingStopLoss(entry_price=price_avg)
        # Modification du log pour indiquer quel type de trailing stop est utilisé
        log_event(f"✅ Position ouverte: {symbol} à {price_avg:.8f}, qt={qty_filled:.8f}, trailing stop configurable activé")
        log_event(f"DEBUG [PositionManager] trailing_stops keys: {list(self.portfolio_manager.trailing_stops.keys())}", "info")
        log_event(f"DEBUG [PositionManager] trailing_stop_paliers keys: {list(self.portfolio_manager.trailing_stop_paliers.keys())}", "info")
        
        self.pending_orders.pop(symbol, None)
        return True
