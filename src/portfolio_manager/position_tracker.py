"""Module de suivi des positions"""
from typing import List, Dict
from models.trade import Trade
from utils.exchange.exchange_utils import log_event

class PositionTracker:
    """Classe pour le suivi des positions"""
    
    def __init__(self, portfolio_manager):
        """Initialise le tracker de positions"""
        self.portfolio_manager = portfolio_manager
    
    async def check_positions(self) -> List[Trade]:
        """Vérifie et gère les positions ouvertes de manière optimisée"""
        if not self.portfolio_manager.positions:
            return []
        
        closed_positions = []
        log_event(f"DEBUG [PositionTracker] positions: {list(self.portfolio_manager.positions.keys())}", "info")
        log_event(f"DEBUG [PositionTracker] trailing_stops: {list(self.portfolio_manager.trailing_stops.keys())}", "info")
        symbols = list(self.portfolio_manager.positions.keys())
        
        # Optimisation: Récupérer les prix actuels en une seule requête si possible
        current_prices = {}
        try:
            # Méthode plus robuste: récupérer les prix un par un
            # Cela évite les problèmes potentiels avec fetch_tickers qui peut causer des erreurs
            # lors de la fermeture du bot ou si certains symboles ont des données manquantes
            for symbol in symbols:
                try:
                    price = await self.portfolio_manager.market_analyzer.get_current_price(symbol)
                    if price and price > 0:
                        current_prices[symbol] = price
                except Exception as symbol_error:
                    log_event(f"Erreur lors de la récupération du prix pour {symbol}: {str(symbol_error)}", "error")
                    continue
        except Exception as e:
            log_event(f"Erreur lors de la récupération des prix: {str(e)}", "error")
            # Continuer avec les prix qu'on a pu récupérer
        
        # Traiter chaque position avec les prix déjà récupérés
        for symbol in list(self.portfolio_manager.positions.keys()):
            try:
                if symbol not in self.portfolio_manager.positions:
                    continue
                
                position = self.portfolio_manager.positions[symbol]
                current_price = current_prices.get(symbol)
                
                if not current_price or current_price <= 0:
                    log_event(f"❌ Prix actuel invalide ou non disponible pour {symbol}", "error")
                    continue
                
                # Calculer le profit actuel
                profit_data = position.calculate_profit(current_price)
                profit_percentage = profit_data['profit_percentage']

                # Gestion du trailing stop paliers
                palier = self.portfolio_manager.trailing_stop_paliers.get(symbol)
                if palier:
                    sell_price = palier.update(current_price)
                    if sell_price:
                        log_event(f"🔴 TRAILING STOP PALIERS DÉCLENCHÉ pour {symbol} à {sell_price:.8f}")
                        trade = await self.portfolio_manager.close_position(symbol, position, sell_price)
                        if trade:
                            closed_positions.append(trade)
                        continue
                
                trailing_stop = self.portfolio_manager.trailing_stops.get(symbol)
                stop_level = trailing_stop.current_stop_level if trailing_stop else position.entry_price
                stop_distance_pct = (1 - stop_level / position.entry_price) * 100
                log_event(f"""
Position {symbol}:
   Prix d'entrée: {position.entry_price:.8f}
   Prix actuel: {current_price:.8f}
   Profit actuel: {profit_percentage:.2f}%
   Stop loss actuel: {stop_distance_pct:.2f}%
""")
                
                # Note: La règle de take profit à 0.8% a été supprimée pour laisser le trailing stop gérer tous les niveaux de profit
                
                # Gestion du trailing stop adaptatif
                trailing_stop = self.portfolio_manager.trailing_stops.get(symbol)
                if trailing_stop:
                    # Mettre à jour le stop loss adaptatif et vérifier s'il doit être liquidé
                    triggered = trailing_stop.update(current_price)
                    
                    if triggered:
                        # Prix de vente = niveau de stop loss actuel
                        sell_price = trailing_stop.current_stop_level
                        # Calculer le profit potentiel à la vente
                        potential_profit_data = position.calculate_profit(sell_price)
                        potential_profit_percentage = potential_profit_data['profit_percentage']
                        
                        log_event(f"""
🔴 STOP LOSS ADAPTATIF DÉCLENCHÉ POUR {symbol}:
   Prix d'entrée: {position.entry_price:.8f}
   Prix actuel: {current_price:.8f}
   Niveau de stop: {sell_price:.8f}
   Profit potentiel: {potential_profit_percentage:.2f}%
""")
                        
                        # Exécuter la vente dès que le stop est déclenché
                        log_event(f"""
Stop loss déclenché - Exécution de la vente:
   Profit potentiel: {potential_profit_percentage:.2f}%
   Action: Exécution immédiate de la vente
""")
                        trade_result = await self.portfolio_manager.close_position(symbol, position, sell_price)
                        
                        if trade_result is not None:
                            closed_positions.append(trade_result)
                            log_event(f"""
Position {symbol} fermée avec succès via stop loss adaptatif:
   Profit attendu: {potential_profit_percentage:.2f}%
   Profit réel: {trade_result.profit_percentage:.2f}%
   Différence: {trade_result.profit_percentage - potential_profit_percentage:.2f}%
""")
                        else:
                            log_event(f"""
Ordre de vente pour {symbol} créé avec succès (en attente d'exécution):
   Niveau de stop: {sell_price:.8f}
   Profit potentiel: {potential_profit_percentage:.2f}%
   Statut: En attente de confirmation...
""")
                    else:
                        log_event(f"Stop loss adaptatif non déclenché pour {symbol}")
                else:
                    log_event(f"❌ Pas de stop loss adaptatif configuré pour {symbol}", "error")
                
            except Exception as e:
                log_event(f"Erreur vérification {symbol}: {str(e)}", "error")
                continue
        
        return closed_positions
    
    def update_trailing_stop(self, symbol: str, current_price: float) -> bool:
        """Met à jour le stop loss adaptatif pour un symbole"""
        if symbol not in self.portfolio_manager.positions or symbol not in self.portfolio_manager.trailing_stops:
            return False

        trailing_stop = self.portfolio_manager.trailing_stops[symbol]
        triggered = trailing_stop.update(current_price)

        if triggered:
            sell_price = trailing_stop.current_stop_level
            log_event(f"Stop loss adaptatif déclenché pour {symbol} à {sell_price}")
            return True

        return False
    
    async def update_reference_prices(self) -> None:
        """Met à jour les prix de référence pour tous les symboles"""
        for symbol in self.portfolio_manager.positions.keys():
            try:
                current_price = await self.portfolio_manager.market_analyzer.get_current_price(symbol)
                if current_price and current_price > 0:
                    await self.portfolio_manager.market_analyzer.update_reference_price(symbol, current_price)
            except Exception as e:
                log_event(f"Erreur mise à jour prix référence {symbol}: {str(e)}", "error")
