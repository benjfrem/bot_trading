"""Module pour l'enregistrement des trades"""
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Trade:
    """Représente un trade complété"""
    symbol: str
    entry_price: float
    exit_price: float
    quantity: float
    profit: float
    profit_percentage: float
    fees: float
    entry_time: datetime
    exit_time: datetime
    duration: float  # en minutes
    
    @classmethod
    def from_position(cls, position, exit_price: float, exit_time: datetime, profit_data: dict):
        """Crée un Trade à partir d'une Position fermée"""
        return cls(
            symbol=position.symbol,
            entry_price=position.entry_price,
            exit_price=exit_price,
            quantity=position.quantity,
            profit=profit_data['net_profit'],
            profit_percentage=profit_data['profit_percentage'],
            fees=profit_data['fees'],
            entry_time=position.timestamp,
            exit_time=exit_time,
            duration=(exit_time - position.timestamp).total_seconds() / 60
        )