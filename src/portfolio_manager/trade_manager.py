"""Module de gestion des trades"""
from datetime import datetime
from typing import Optional, Dict
from config import Config
from models.position import Position
from models.trade import Trade
from utils.exchange.exchange_utils import log_event
from utils.telegram_notifier import send_message
from utils.monitoring.excel_logger import trade_logger

from utils.trading.limit_order_manager import LimitOrderManager

class TradeManager:
    """Classe pour la gestion des trades"""
    
    def __init__(self, portfolio_manager):
        """Initialise le gestionnaire de trades"""
        self.portfolio_manager = portfolio_manager
        self.limit_order_manager = None  # Sera initialisé lors de la première utilisation
    
    def _ensure_limit_order_manager(self):
        """S'assure que le gestionnaire d'ordres limites est initialisé"""
        if self.limit_order_manager is None:
            self.limit_order_manager = LimitOrderManager(self.portfolio_manager.exchange_ops.exchange)
            log_event("Gestionnaire d'ordres limites de vente initialisé")
    
    def _determine_optimal_limit_price(self, current_price: float) -> float:
        """Détermine le prix optimal pour un ordre limite de vente : 1% en dessous du marché
        
        Args:
            current_price: Prix actuel du marché
            
        Returns:
            Prix du marché -1%
        """
        adjusted_price = current_price * 0.99
        log_event(f"""
=== VENTE LIMIT 1% SOUS LE MARCHÉ ===
   Prix marché: {current_price:.8f}
   Prix limite: {adjusted_price:.8f}
   Écart: -1.00%
""")
        return adjusted_price
    
    async def _handle_order_timeout(self, symbol: str, position: Position) -> None:
        """Callback à exécuter si un ordre limite de vente expire - tentatives infinies
        
        Args:
            symbol: Symbole concerné
            position: Position à fermer
        """
        # Vérifier combien de tentatives ont déjà été effectuées
        if not self.limit_order_manager:
            self._ensure_limit_order_manager()
            
        attempt_count = self.limit_order_manager.get_sell_attempt_count(symbol)
        next_attempt = attempt_count + 1
        max_attempts = 10  # Nombre maximal de tentatives pour les ventes (plus élevé que pour les achats)
        
        log_event(f"""
=== TIMEOUT ORDRE LIMITE VENTE (TENTATIVE {next_attempt}/{max_attempts}) ===
   Symbole: {symbol}
   Action: Création d'un nouvel ordre de vente
""")
        
        # Si le nombre maximum de tentatives est atteint, réinitialiser le compteur
        if next_attempt > max_attempts:
            if self.limit_order_manager:
                self.limit_order_manager.reset_sell_attempts(symbol)
                log_event(f"Maximum de tentatives de vente atteint pour {symbol}, réinitialisation du compteur")
                next_attempt = 1  # Réinitialiser pour la prochaine tentative
        
        # Tentative pour les ventes: toujours réessayer avec le prix actuel du marché
        try:
            # Récupérer le prix actuel du marché pour la nouvelle tentative
            current_price = await self.portfolio_manager.market_analyzer.get_current_price(symbol)
            if not current_price or current_price <= 0:
                log_event(f"❌ Impossible de récupérer le prix actuel pour {symbol}, réessai au prochain cycle", "error")
                return
            
            log_event(f"""
=== NOUVELLE TENTATIVE VENTE {next_attempt}/{max_attempts} ===
   Symbole: {symbol}
   Nouveau prix: {current_price:.8f}
   Action: Création d'un nouvel ordre limite de vente
""")
            
            # Relancer un nouvel ordre de vente avec le prix actuel
            await self.close_position(symbol, position, current_price)
            
        except Exception as e:
            log_event(f"❌ Erreur lors de la nouvelle tentative de vente: {str(e)}", "error")
        
    async def close_position(self, symbol: str, position: Position, current_price: float) -> Optional[Trade]:
        """Ferme une position existante - version avec ordres limites optimisés"""
        # Log minimal
        log_event(f"Fermeture position {symbol} à ~{current_price}")
        
        # Validation rapide
        if not symbol in self.portfolio_manager.positions:
            log_event(f"❌ Position inexistante pour {symbol}", "error")
            return None
            
        if not current_price or current_price <= 0:
            log_event(f"❌ Prix invalide: {current_price}", "error")
            return None
        
        # Utiliser la quantité exacte de la position comme base (toujours vendre 100% de la position)
        sell_quantity = position.quantity
        # Conserver la quantité originale pour les ajustements éventuels
        original_quantity = sell_quantity
        base_currency = symbol.split('/')[0]
        
        log_event(f"""
=== PRÉPARATION VENTE POSITION COMPLÈTE ===
   Symbole: {symbol}
   Quantité de la position: {sell_quantity} {base_currency}
   Prix de vente: {current_price:.8f}
   Valeur estimée: {sell_quantity * current_price:.2f} USDC
""")
        
        # Par sécurité, vérifier également la balance disponible, mais uniquement pour le logging
        available_quantity = await self.portfolio_manager.exchange_ops.get_balance(base_currency)
        if available_quantity is not None:
            if abs(available_quantity - position.quantity) > 0.001:
                log_event(f"Information: Balance disponible ({available_quantity} {base_currency}) diffère de la quantité de position ({position.quantity} {base_currency})", "info")
        
        # Pas de facteur de sécurité : vendre toute la position
        
        # Vérifier que le montant total respecte le minimum requis par l'exchange
        total_value = sell_quantity * current_price
        min_order_value = self.portfolio_manager.exchange_ops.exchange.markets.get(symbol, {}).get('limits', {}).get('cost', {}).get('min', 1.0)
        
        # Si cette information n'est pas disponible, utiliser la configuration par défaut
        if not min_order_value or min_order_value <= 0:
            min_order_value = Config.MIN_TRANSACTION_QUOTE_AMOUNT
            
        if total_value < min_order_value:
            log_event(f"""
⚠️ MONTANT TOTAL TROP FAIBLE POUR L'EXCHANGE:
   Valeur totale: {total_value:.2f} USDC
   Minimum requis: {min_order_value:.2f} USDC
   Action: Augmentation de la quantité pour respecter le minimum
""", "error")
            
            # Ajuster la quantité pour atteindre le minimum requis
            required_quantity = (min_order_value / current_price) * 1.01  # +1% pour être sûr
            
            # Si la nouvelle quantité est supérieure à la position, on ne peut pas vendre plus que ce qu'on a
            if required_quantity > original_quantity:
                log_event(f"""
❌ IMPOSSIBLE D'ATTEINDRE LE MINIMUM REQUIS SANS DÉPASSER LA POSITION:
   Quantité requise: {required_quantity} {base_currency}
   Quantité disponible: {original_quantity} {base_currency}
   Raison possible: Position trop petite ou prix trop bas
""", "error")
                return None
            
            sell_quantity = required_quantity
            log_event(f"Quantité ajustée à {sell_quantity} {base_currency} pour respecter le minimum de {min_order_value} USDC", "info")
        
        # Vérification finale
        if sell_quantity <= 0:
            log_event(f"❌ Quantité vente invalide: {sell_quantity}", "error")
            return None
        
        try:
            # Déterminer le prix optimal pour l'ordre limite
            limit_price = self._determine_optimal_limit_price(current_price)
            
            log_event(f"""
=== OPTIMISATION ORDRE LIMITE VENTE ===
   Prix du marché: {current_price:.8f}
   Prix limite optimisé: {limit_price:.8f}
   Différence: {((limit_price - current_price) / current_price) * 100:.4f}%
""")
            
            # S'assurer que le gestionnaire d'ordres limites est initialisé
            self._ensure_limit_order_manager()
            # Si un ordre de vente est déjà en attente pour ce symbole, annuler avant de recréer
            for order_id, o in list(self.limit_order_manager.active_orders.items()):
                if o.get('symbol') == symbol and o.get('type') == 'sell':
                    log_event(f"Annulation de l'ordre en attente {order_id} pour {symbol} avant nouvelle tentative", "info")
                    await self.limit_order_manager.cancel_order(order_id, symbol)
                    # Retirer cet ordre de la liste active
                    del self.limit_order_manager.active_orders[order_id]
            # (La suppression du trailing_stop est déplacée au traitement du callback rempli)
            
            # Créer une fonction de callback pour le timeout
            async def on_timeout():
                await self._handle_order_timeout(symbol, position)
            
            # Créer une fonction de callback pour le remplissage de l'ordre
            async def on_fill_callback(order_status):
                await self._process_sell_order_filled(symbol, position, order_status, current_price)
            
            # Obtenir le compteur de tentative actuel
            attempt = 1  # Première tentative par défaut
            if hasattr(self.limit_order_manager, 'get_sell_attempt_count'):
                # Si la vente est relancée suite à un timeout, le compteur sera > 0
                existing_attempts = self.limit_order_manager.get_sell_attempt_count(symbol)
                if existing_attempts > 0:
                    attempt = existing_attempts + 1
            
            log_event(f"📤 Envoi ordre limite vente: symbole={symbol}, quantité={sell_quantity:.8f}, prix_limite={limit_price:.8f}, timeout=2s, tentative={attempt}")
            
            # Créer l'ordre limite avec un timeout de 5 secondes
            order = await self.limit_order_manager.create_limit_sell_order(
                symbol=symbol,
                quantity=sell_quantity,
                price=limit_price,
                timeout=2,  # 2 secondes de timeout comme demandé
                on_timeout_callback=on_timeout,
                on_fill_callback=on_fill_callback,
                attempt=attempt
            )
            
            if not order:
                log_event("❌ Échec création ordre limite vente", "error")
                return None
            
            # Log de la structure de l'ordre pour diagnostic
            log_event(f"Structure de l'ordre de vente reçu: {order}")
            
            # IMPORTANT: On ne considère plus la position comme fermée ici
            # La position sera fermée uniquement lorsque l'ordre sera confirmé comme rempli
            # via le callback on_fill_callback qui appellera _process_sell_order_filled
            
            return None  # Retourner None car le trade n'est pas encore complété
                
        except Exception as e:
            log_event(f"❌ Erreur création ordre limite vente: {str(e)}", "error")
            return None
    
    async def _process_sell_order_filled(self, symbol: str, position: Position, order_status: dict, fallback_price: float) -> Optional[Trade]:
        """Traite la fin d'exécution d'un ordre de vente"""
        try:
            log_event(f"Traitement de l'ordre de vente rempli pour {symbol}")
            
            # Récupération sécurisée du prix moyen
            average_price = order_status.get('average')
            if average_price is not None and average_price != '':
                try:
                    actual_price = float(average_price)
                except (ValueError, TypeError):
                    log_event(f"❌ Impossible de convertir le prix moyen de vente '{average_price}' en float", "error")
                    actual_price = fallback_price
            else:
                actual_price = fallback_price
                log_event(f"Prix moyen de vente non disponible, utilisation du prix actuel: {actual_price}", "info")
            
            # Récupération sécurisée de la quantité remplie
            filled_quantity = order_status.get('filled')
            if filled_quantity is not None and filled_quantity != '':
                try:
                    actual_quantity = float(filled_quantity)
                except (ValueError, TypeError):
                    log_event(f"❌ Impossible de convertir la quantité vendue '{filled_quantity}' en float", "error")
                    actual_quantity = position.quantity
            else:
                actual_quantity = position.quantity
                log_event(f"Quantité vendue non disponible, utilisation de la quantité initiale: {actual_quantity}", "info")
            
            # Vérifier que nous avons toujours la position
            if symbol not in self.portfolio_manager.positions:
                log_event(f"⚠️ La position {symbol} n'existe plus, impossible de finaliser la vente", "error")
                return None
            
            # Calculer les profits
            profit_data = position.calculate_profit(actual_price, self.portfolio_manager.trading_fee)
            
            # Créer l'enregistrement du trade
            trade = Trade.from_position(
                position=position,
                exit_price=actual_price,
                exit_time=datetime.now(),
                profit_data=profit_data
            )
            
            self.portfolio_manager.trade_history.append(trade)
            
            # Enregistrer le trade dans le fichier Excel
            trade_data = {
                "symbol": trade.symbol,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "quantity": trade.quantity,
                "gross_profit": profit_data['gross_profit'],
                "fees": trade.fees,
                "profit": trade.profit,
                "profit_percentage": trade.profit_percentage,
                "entry_time": trade.entry_time,
                "exit_time": trade.exit_time,
                "duration": trade.duration
            }
            trade_logger.log_trade(trade_data)
            # Notification Telegram
            try:
                msg = (
                    f"🔴 Position fermée\n"
                    f"• Symbole : {trade.symbol}\n"
                    f"• Ouverture : {trade.entry_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"- prix ouverture : {trade.entry_price:.8f}\n"
                    f"• Fermeture : {trade.exit_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"- prix fermeture : {trade.exit_price:.8f}\n"
                    f"• P&L : {trade.profit_percentage:.2f}%"
                )
                send_message(msg)
            except Exception as e:
                log_event(f"❌ Erreur notification Telegram: {e}", "error")
            
            # Nettoyage rapide
            if symbol in self.portfolio_manager.trailing_stops:
                del self.portfolio_manager.trailing_stops[symbol]
            
            # Nettoyer le trailing buy RSI dans le market analyzer
            if hasattr(self.portfolio_manager.market_analyzer, 'market_data'):
                market_data = self.portfolio_manager.market_analyzer.market_data.get(symbol)
                if market_data and hasattr(market_data, 'trailing_buy_rsi'):
                    market_data.trailing_buy_rsi = None
            
            # Mettre à jour le prix de référence
            if hasattr(self.portfolio_manager.market_analyzer, 'update_reference_price'):
                await self.portfolio_manager.market_analyzer.update_reference_price(symbol, actual_price, force=True)
            
            # Supprimer la position
            del self.portfolio_manager.positions[symbol]
            
            # Log détaillé du résultat
            log_event(f"""
Position {symbol} fermée avec succès via trailing stop:
   Profit attendu: {profit_data['profit_percentage']:.2f}%
   Profit réel: {profit_data['profit_percentage']:.2f}%
   Différence: {profit_data['profit_percentage'] - profit_data['profit_percentage']:.2f}%
""")
            
            return trade
            
        except Exception as e:
            log_event(f"❌ Erreur traitement vente remplie: {str(e)}", "error")
            return None
    
    def _validate_close_position(self, symbol: str, price: float) -> bool:
        """Valide les conditions pour fermer une position"""
        if not price or price <= 0:
            log_event(f"❌ Prix de fermeture invalide pour {symbol}: {price}", "error")
            return False
        return True
    
    def _validate_quantity(self, quantity: float) -> bool:
        """Valide la quantité pour la vente"""
        if quantity <= 0:
            log_event("❌ Quantité de vente invalide", "error")
            return False
        return True
    
    async def _process_successful_sell_order(self, symbol: str, position: Position, order: dict) -> Optional[Trade]:
        """Traite un ordre de vente réussi"""
        actual_price = float(order.get('average', 0))
        actual_quantity = float(order.get('filled', 0))
        
        if actual_price <= 0 or actual_quantity <= 0:
            log_event("❌ Données d'ordre de vente invalides", "error")
            return None
        
        # Calculer les profits
        profit_data = position.calculate_profit(actual_price, self.portfolio_manager.trading_fee)
        
        # Mettre à jour le prix de référence (méthode asynchrone)
        if hasattr(self.portfolio_manager.market_analyzer, 'update_reference_price'):
            await self.portfolio_manager.market_analyzer.update_reference_price(symbol, actual_price)
        
        # Créer l'enregistrement du trade
        trade = Trade.from_position(
            position=position,
            exit_price=actual_price,
            exit_time=datetime.now(),
            profit_data=profit_data
        )
        
        self.portfolio_manager.trade_history.append(trade)
        
        log_event(f"""
✅ Position fermée avec succès:
   Symbole: {symbol}
   Prix de vente: {actual_price:.8f} USDC
   Quantité vendue: {actual_quantity:.8f}
   Profit net: {profit_data['net_profit']:.2f} USDC ({profit_data['profit_percentage']:.2f}%)
   Frais totaux: {profit_data['fees']:.2f} USDC
   Durée: {trade.duration:.1f} minutes
""")
        
        # Supprimer la position
        del self.portfolio_manager.positions[symbol]
        
        return trade
