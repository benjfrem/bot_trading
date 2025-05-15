"""Module d'analyse du portfolio"""
from typing import Dict, List, Optional
from models.trade import Trade

class PortfolioAnalyzer:
    """Classe pour l'analyse du portfolio"""
    
    def __init__(self, portfolio_manager):
        """Initialise l'analyseur de portfolio"""
        self.portfolio_manager = portfolio_manager
    
    def get_portfolio_stats(self) -> dict:
        """Retourne les statistiques du portfolio"""
        stats = {
            'active_positions': len(self.portfolio_manager.positions),
            'total_trades': len(self.portfolio_manager.trade_history),
            'profitable_trades': sum(1 for trade in self.portfolio_manager.trade_history if trade.profit > 0),
            'total_profit': sum(trade.profit for trade in self.portfolio_manager.trade_history),
            'average_profit': 0,
            'win_rate': 0,
            'average_duration': 0,
            'best_trade': None,
            'worst_trade': None
        }
        
        if stats['total_trades'] > 0:
            stats['win_rate'] = (stats['profitable_trades'] / stats['total_trades']) * 100
            stats['average_profit'] = stats['total_profit'] / stats['total_trades']
            stats['average_duration'] = sum(trade.duration for trade in self.portfolio_manager.trade_history) / stats['total_trades']
            
            best_trade = max(self.portfolio_manager.trade_history, key=lambda x: x.profit_percentage)
            worst_trade = min(self.portfolio_manager.trade_history, key=lambda x: x.profit_percentage)
            
            stats['best_trade'] = {
                'symbol': best_trade.symbol,
                'profit': best_trade.profit,
                'percentage': best_trade.profit_percentage
            }
            
            stats['worst_trade'] = {
                'symbol': worst_trade.symbol,
                'profit': worst_trade.profit,
                'percentage': worst_trade.profit_percentage
            }
        
        return stats
    
    def get_position_stats(self, symbol: str) -> Optional[dict]:
        """Retourne les statistiques d'une position spécifique"""
        if symbol not in self.portfolio_manager.positions:
            return None
        
        position = self.portfolio_manager.positions[symbol]
        
        return {
            'symbol': symbol,
            'entry_price': position.entry_price,
            'quantity': position.quantity,
            'total_cost': position.total_cost,
            'timestamp': position.timestamp,
            'order_id': position.order_id
        }
    
    def get_trade_history_stats(self) -> Dict[str, List[dict]]:
        """Retourne les statistiques de l'historique des trades par symbole"""
        stats = {}
        
        for trade in self.portfolio_manager.trade_history:
            symbol = trade.symbol
            
            if symbol not in stats:
                stats[symbol] = []
            
            stats[symbol].append({
                'entry_price': trade.entry_price,
                'exit_price': trade.exit_price,
                'quantity': trade.quantity,
                'profit': trade.profit,
                'profit_percentage': trade.profit_percentage,
                'fees': trade.fees,
                'entry_time': trade.entry_time,
                'exit_time': trade.exit_time,
                'duration': trade.duration
            })
        
        return stats
    
    def get_performance_by_symbol(self) -> Dict[str, dict]:
        """Retourne les performances par symbole"""
        performance = {}
        
        for trade in self.portfolio_manager.trade_history:
            symbol = trade.symbol
            
            if symbol not in performance:
                performance[symbol] = {
                    'total_trades': 0,
                    'profitable_trades': 0,
                    'total_profit': 0,
                    'average_profit': 0,
                    'win_rate': 0,
                    'best_trade': None,
                    'worst_trade': None
                }
            
            performance[symbol]['total_trades'] += 1
            
            if trade.profit > 0:
                performance[symbol]['profitable_trades'] += 1
                
            performance[symbol]['total_profit'] += trade.profit
            
            # Mettre à jour le meilleur trade
            if performance[symbol]['best_trade'] is None or trade.profit_percentage > performance[symbol]['best_trade']['percentage']:
                performance[symbol]['best_trade'] = {
                    'profit': trade.profit,
                    'percentage': trade.profit_percentage,
                    'entry_time': trade.entry_time,
                    'exit_time': trade.exit_time
                }
            
            # Mettre à jour le pire trade
            if performance[symbol]['worst_trade'] is None or trade.profit_percentage < performance[symbol]['worst_trade']['percentage']:
                performance[symbol]['worst_trade'] = {
                    'profit': trade.profit,
                    'percentage': trade.profit_percentage,
                    'entry_time': trade.entry_time,
                    'exit_time': trade.exit_time
                }
        
        # Calculer les moyennes et les taux
        for symbol, stats in performance.items():
            if stats['total_trades'] > 0:
                stats['average_profit'] = stats['total_profit'] / stats['total_trades']
                stats['win_rate'] = (stats['profitable_trades'] / stats['total_trades']) * 100
        
        return performance
