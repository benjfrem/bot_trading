"""Module pour la gestion des positions de trading"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Position:
    """Représente une position de trading ouverte"""
    symbol: str
    entry_price: float
    quantity: float
    timestamp: datetime
    order_id: str
    total_cost: float
    
    def calculate_profit(self, current_price: float, trading_fee: float = 0.00) -> dict:
        """Calcule les profits pour la position"""
        gross_profit = (current_price - self.entry_price) * self.quantity
        net_profit = gross_profit  # Suppression de la déduction des frais
        profit_percentage = (
            (current_price - self.entry_price)
            / self.entry_price * 100
        )
        
        return {
            'gross_profit': gross_profit,
            'net_profit': net_profit,
            'profit_percentage': profit_percentage,
            'fees': 0.0  # Frais supprimés
        }
