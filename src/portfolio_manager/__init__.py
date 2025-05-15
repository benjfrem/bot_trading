"""Module principal de gestion du portfolio"""
from datetime import datetime
from typing import Dict, List, Optional

from config import Config
from models.position import Position
from models.trade import Trade
from utils.exchange.exchange_utils import ExchangeOperations, log_event
from utils.trading.adaptive_stoploss import StopLossManager
from utils.trading.trailing_buy import TrailingBuyRsi
from utils.monitoring.excel_logger import trade_logger
from utils.trading.trailing_stop import TrailingStopLoss

from .position_manager import PositionManager
from .position_tracker import PositionTracker
from .trade_manager import TradeManager
from .portfolio_analyzer import PortfolioAnalyzer

class PortfolioManager:
    """Classe principale pour la gestion du portfolio"""
    
    def __init__(self, exchange, market_analyzer):
        """Initialise le gestionnaire de portfolio"""
        self.positions: Dict[str, Position] = {}
        self.trailing_stops: Dict[str, StopLossManager] = {}
        self.trailing_stop_paliers: Dict[str, TrailingStopLoss] = {}
        self.market_analyzer = market_analyzer
        self.exchange_ops = ExchangeOperations(exchange)
        self.trading_fee = 0.001
        self.trade_history: List[Trade] = []
        
        # Initialiser les gestionnaires spécialisés
        self.position_manager = PositionManager(self)
        self.position_tracker = PositionTracker(self)
        self.trade_manager = TradeManager(self)
        self.portfolio_analyzer = PortfolioAnalyzer(self)
        
        log_event("Portfolio Manager initialisé")
    
    # Méthodes déléguées au PositionManager
    async def open_position(self, symbol: str, price: float, position_size: float = 1.0) -> bool:
        """Ouvre une nouvelle position avec une taille optionnelle"""
        return await self.position_manager.open_position(symbol, price, position_size)
    
    async def calculate_quantity(self, symbol: str, price: float, position_size: float = 1.0) -> Optional[float]:
        """Calcule la quantité à acheter en tenant compte de la taille de position"""
        return await self.position_manager.calculate_quantity(symbol, price, position_size)
    
    async def can_open_position(self, symbol: str = None) -> bool:
        """Vérifie si une nouvelle position peut être ouverte"""
        return await self.position_manager.can_open_position(symbol)
    
    # Méthodes déléguées au PositionTracker
    async def check_positions(self) -> List[Trade]:
        """Vérifie et gère les positions ouvertes"""
        return await self.position_tracker.check_positions()
    
    # Méthodes déléguées au TradeManager
    async def close_position(self, symbol: str, position: Position, current_price: float) -> Optional[Trade]:
        """Ferme une position existante"""
        return await self.trade_manager.close_position(symbol, position, current_price)
    
    # Méthodes déléguées au PortfolioAnalyzer
    def get_portfolio_stats(self) -> dict:
        """Retourne les statistiques du portfolio"""
        return self.portfolio_analyzer.get_portfolio_stats()
        
    # Méthodes supplémentaires
    async def cancel_all_orders(self) -> bool:
        """Annule tous les ordres ouverts"""
        try:
            if hasattr(self.exchange_ops, 'exchange'):
                await self.exchange_ops.exchange.cancel_all_orders()
                log_event("Tous les ordres ont été annulés")
                return True
            return False
        except Exception as e:
            log_event(f"Erreur lors de l'annulation des ordres: {str(e)}", "error")
            return False
