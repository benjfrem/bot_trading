"""Gestionnaire des statistiques de trading"""
from dataclasses import dataclass
from typing import Optional

@dataclass
class TradeStats:
    """Statistiques d'un trade"""
    symbol: str
    profit: float
    percentage: float

@dataclass
class TradingStats:
    """Statistiques globales de trading"""
    trades_total: int = 0
    trades_profit: int = 0
    trades_loss: int = 0
    total_profit: float = 0.0
    
    def log_trade(self, profit: float) -> None:
        """Enregistre un nouveau trade"""
        self.trades_total += 1
        if profit > 0:
            self.trades_profit += 1
        else:
            self.trades_loss += 1
        self.total_profit += profit
    
    def get_win_rate(self) -> float:
        """Calcule le taux de réussite"""
        if self.trades_total == 0:
            return 0.0
        return (self.trades_profit / self.trades_total) * 100
    
    def format_stats(self) -> str:
        """Formate les statistiques pour l'affichage"""
        stats = "\n=== STATISTIQUES DE TRADING ===\n"
        stats += f"Trades totaux: {self.trades_total}\n"
        stats += f"Trades gagnants: {self.trades_profit}\n"
        stats += f"Trades perdants: {self.trades_loss}\n"
        stats += f"Profit total: {self.total_profit:.2f} USDC\n"
        
        if self.trades_total > 0:
            stats += f"Taux de réussite: {self.get_win_rate():.2f}%\n"
        
        stats += "=" * 30 + "\n"
        return stats