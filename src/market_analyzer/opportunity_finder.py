"""Module pour la détection des opportunités de trading (simplifié)"""
import time
from typing import Dict, Optional, List, Tuple, Any
from datetime import datetime

from config import Config
from .market_data import MarketData
from .indicator_calculator import get_atr
from utils.trading.trailing_buy import TrailingBuyRsi
from logger import trading_logger, error_logger

class OpportunityFinder:
    """Classe pour la détection des opportunités de trading (basée uniquement sur RSI)"""
    
    def __init__(self, log_callback=None):
        """Initialise le détecteur d'opportunités"""
        self._log_callback = log_callback
        
    def _log(self, message: str, level: str = "info") -> None:
        """Centralise la gestion des logs"""
        if self._log_callback:
            self._log_callback(message, level)
        else:
            if level == "info":
                trading_logger.info(message)
            elif level == "error":
                error_logger.error(message)
            print(message)
    
    def init_scoring_system(self, rsi_analyzer):
        """Méthode maintenue pour compatibilité mais qui n'initialise plus de scoring system"""
        self._log("✓ Mode trading RSI direct activé (sans système de scoring)")
    
    def _validate_opportunity(self, opportunity: Dict[str, Any]) -> bool:
        """Valide une opportunité de trading"""
        try:
            # Vérification des champs requis
            required_fields = ['symbol', 'current_price', 'rsi', 'market_info']
            if not all(field in opportunity for field in required_fields):
                self._log("❌ Champs manquants dans l'opportunité")
                return False
            
            # Validation des valeurs
            if opportunity['current_price'] <= 0:
                self._log("❌ Prix actuel invalide")
                return False
                
            # Vérification des informations de marché
            market_info = opportunity['market_info']
            
            # Si les informations de marché sont manquantes ou incomplètes, utiliser des valeurs par défaut
            if not market_info:
                self._log("❌ Informations de marché manquantes, utilisation de valeurs par défaut")
                opportunity['market_info'] = {
                    'min_amount': 0.0001,
                    'precision': {'amount': 8, 'price': 8},
                    'taker_fee': 0.00,
                    'maker_fee': 0.00
                }
                return True
            
            # Vérifier et compléter les champs manquants
            if not market_info.get('min_amount'):
                self._log("❌ min_amount manquant, utilisation de valeur par défaut")
                market_info['min_amount'] = 0.0001
                
            if not market_info.get('precision'):
                self._log("❌ precision manquante, utilisation de valeur par défaut")
                market_info['precision'] = {'amount': 8, 'price': 8}
            
            return True
            
        except Exception as e:
            self._log(f"❌ Erreur de validation: {str(e)}", "error")
            return False
    
    def _format_rsi_value(self, rsi_value):
        """Formate une valeur de RSI pour l'affichage"""
        if rsi_value is None:
            return "N/A"
        return f"{rsi_value:.2f}"
    
    async def find_opportunities(self, symbols_to_analyze: List[str], market_data: Dict[str, MarketData], 
                                indicators_results: Dict[str, Tuple], market_infos: Dict[str, Dict], active_positions: set = None) -> List[Dict[str, Any]]:
        """Analyse le marché pour identifier les opportunités de trading basées uniquement sur le trailing buy RSI"""
        start_time = time.time()
        results = []
        
        if active_positions is None:
            active_positions = set()
        
        for symbol in symbols_to_analyze:
            try:
                # Exclure les symboles avec position ouverte
                if symbol in active_positions:
                    self._log(f"Symbole {symbol} ignoré car position déjà ouverte")
                    continue
                
                # Récupérer les données des indicateurs (tendance toujours neutre)
                current_price, rsi, adx, variation = indicators_results.get(symbol, (None, None, None, None))
                if not current_price or not rsi:
                    self._log(f"Données insuffisantes pour {symbol}: prix={current_price}, RSI={rsi}")
                    continue
                
                # Mise à jour du prix actuel dans les données de marché
                symbol_market_data = market_data.get(symbol)
                if not symbol_market_data:
                    self._log(f"Données de marché non disponibles pour {symbol}")
                    continue
                
                symbol_market_data.last_price = current_price
                symbol_market_data.market_trend = "neutral"  # Toujours tendance neutre
                symbol_market_data.trend_variation = variation
                
                # Calcul de la variation de prix
                price_change = ((current_price - symbol_market_data.reference_price) / symbol_market_data.reference_price) * 100
                
                # Récupérer le RSI
                multi_period_rsi = getattr(symbol_market_data, 'multi_period_rsi', {})
                rsi_14 = multi_period_rsi.get(14, rsi)  # Utiliser le RSI passé en paramètre si non disponible dans multi_period_rsi
                
                # Formater la valeur de RSI pour l'affichage
                rsi_14_str = self._format_rsi_value(rsi_14)
                
                # Log des indicateurs clés pour chaque symbole analysé avec ATR
                # Récupérer l'ATR brut pour logs
                atr_price = get_atr(symbol)
                atr_str = f"{atr_price:.8f}"
                self._log(f"""
=== INDICATEURS {symbol} ===
   Prix actuel: {current_price:.8f}
   RSI: {rsi_14_str}
   ATR: {atr_str}
   ADX: {adx if adx is not None else 'N/A'}
""")
                
                # Initialiser le trailing buy RSI si ce n'est pas déjà fait
                if not hasattr(symbol_market_data, 'trailing_buy_rsi') or symbol_market_data.trailing_buy_rsi is None:
                    symbol_market_data.trailing_buy_rsi = TrailingBuyRsi()
                    symbol_market_data.rsi_confirm_counter = 0
                    symbol_market_data.rsi_last_confirm_value = None
                    self._log(f"Trailing Buy RSI initialisé pour {symbol}")
                
                # Double confirmation RSI: mise à jour du trailing buy RSI (état et logs)
                symbol_market_data.trailing_buy_rsi.update(rsi, current_price, log_enabled=True)
                # Récupérer le niveau applicable
                level = symbol_market_data.trailing_buy_rsi.current_level
                if not level:
                    continue
                threshold = level.buy_level
                self._log(f"Confirmation RSI: seuil d'achat = {threshold:.2f} pour {symbol}", "info")
                # Mise à jour du compteur de ticks avec vérification du changement de RSI
                if rsi >= threshold:
                    # Premier tick
                    if not hasattr(symbol_market_data, 'rsi_confirm_counter') or symbol_market_data.rsi_confirm_counter == 0:
                        symbol_market_data.rsi_confirm_counter = 1
                        symbol_market_data.rsi_last_confirm_value = rsi
                        self._log(
                            f"Tick 1/{Config.DOUBLE_CONFIRMATION_TICKS} de confirmation RSI pour {symbol} (RSI initial = {rsi:.2f})",
                            "info"
                        )
                    else:
                        # Tick suivant : incrémenter si le RSI a changé
                        if rsi != symbol_market_data.rsi_last_confirm_value:
                            symbol_market_data.rsi_confirm_counter += 1
                            symbol_market_data.rsi_last_confirm_value = rsi
                            self._log(
                                f"Tick {symbol_market_data.rsi_confirm_counter}/{Config.DOUBLE_CONFIRMATION_TICKS} "
                                f"de confirmation RSI pour {symbol} (RSI = {rsi:.2f}, différent de précédent)",
                                "info"
                            )
                        else:
                            self._log(
                                f"Mise à jour RSI identique pour {symbol} (RSI = {rsi:.2f}); tick non comptabilisé",
                                "info"
                            )
                else:
                    # RSI repassé sous le seuil : réinitialisation complète
                    if symbol_market_data.rsi_confirm_counter > 0:
                        self._log(
                            f"Réinitialisation du compteur RSI pour {symbol} (RSI = {rsi:.2f} < {threshold:.2f})",
                            "info"
                        )
                    symbol_market_data.rsi_confirm_counter = 0
                    if hasattr(symbol_market_data, 'rsi_last_confirm_value'):
                        del symbol_market_data.rsi_last_confirm_value
                # Vérifier si le nombre de ticks requis est atteint
                if symbol_market_data.rsi_confirm_counter < Config.DOUBLE_CONFIRMATION_TICKS:
                    continue
                # Confirmation obtenue, générer le signal d'achat
                self._log(
                    f"Confirmation RSI validée "
                    f"({Config.DOUBLE_CONFIRMATION_TICKS}/{Config.DOUBLE_CONFIRMATION_TICKS}) pour {symbol}",
                    "info"
                )
                buy_signal = current_price
                # Verrouiller l'état du trailing buy RSI jusqu'au traitement de l'ordre
                tb = symbol_market_data.trailing_buy_rsi
                tb._lock_state_for_buy = True
                tb._signal_emitted = True
                # Réinitialiser le compteur
                symbol_market_data.rsi_confirm_counter = 0

                # VERIFICATION ADX
                mode = ("Rejeté" if adx is not None and adx > Config.DMI_NEGATIVE_THRESHOLD_WARNING else
                        "Vigilance Stop" if adx is not None and adx >= Config.DMI_NEGATIVE_THRESHOLD_SAFE else
                        "Normal")
                self._log("--------------------------", "info")
                self._log(f">>> VERIFICATION ADX pour {symbol} :", "info")
                self._log(f"    ADX mesuré       : {adx:.2f}", "info")
                self._log(f"    Seuil Normal     : < {Config.DMI_NEGATIVE_THRESHOLD_SAFE:.2f}", "info")
                self._log(f"    Seuil Vigilance  : [{Config.DMI_NEGATIVE_THRESHOLD_SAFE:.2f} - {Config.DMI_NEGATIVE_THRESHOLD_WARNING:.2f}]", "info")
                self._log(f"    Seuil Rejeté     : > {Config.DMI_NEGATIVE_THRESHOLD_WARNING:.2f}", "info")
                self._log(f"    Décision         : {mode}", "info")
                self._log("--------------------------", "info")
                # Vérification ADX
                if adx is not None and adx > Config.DMI_NEGATIVE_THRESHOLD_WARNING:
                    self._log(f"ADX trop élevé ({adx:.2f}), opportunité rejetée", "info")
                    continue
                dmi_zone = 'warning' if adx is not None and adx >= Config.DMI_NEGATIVE_THRESHOLD_SAFE else 'safe'
 
                # Récupérer les infos du marché
                
                # Récupérer les infos du marché
                market_info = market_infos.get(symbol)
                if not market_info:
                    continue
                
                # Création de l'opportunité basée uniquement sur le signal trailing buy
                opportunity = {
                    'symbol': symbol,
                    'current_price': current_price,
                    'buy_price': buy_signal,  # Utiliser le prix retourné par le trailing buy
                    'reference_price': symbol_market_data.reference_price,
                    'price_change': price_change,
                    'rsi': rsi,
                    'adx': adx,
                    'market_info': market_info,
                    'timestamp': datetime.now(),
                    'score': 100,  # Score fixe de 100 (plus besoin de scoring)
                    'position_size': 1.0,  # Toujours position complète
                    'trailing_buy_triggered': True,  # Signal trailing buy confirmé
                    'market_trend': "neutral",  # Toujours tendance neutre
                    'trend_variation': variation,
                    'lowest_rsi': symbol_market_data.trailing_buy_rsi.lowest_rsi,  # Ajout du RSI minimum pour référence
                    'dmi_zone': dmi_zone
                }
                
                # Validation finale de l'opportunité
                if not self._validate_opportunity(opportunity):
                    continue
                
                # Journaliser les informations de l'opportunité
                self._log(f"""
=== SIGNAL D'ACHAT RSI DÉTECTÉ ===
   Symbole: {symbol}
   RSI actuel: {rsi_14_str}
   RSI minimum atteint: {symbol_market_data.trailing_buy_rsi.lowest_rsi:.2f}
   Prix actuel: {current_price:.8f}
   Prix signal: {buy_signal:.8f}
""")
                
                results.append(opportunity)
                
            except Exception as e:
                self._log(f"Erreur d'analyse pour {symbol}: {str(e)}", "error")
                continue
        
        # Filtrer les résultats valides
        opportunities = [r for r in results if r is not None]
        # Afficher les détails des opportunités retenues (avec moins de détails)
        if opportunities:
            self._log("\n=== OPPORTUNITÉS DÉTECTÉES ===")
            for opp in opportunities:
                symbol = opp['symbol']
                # Recalcul de l'ATR pour chaque opportunité affichée
                atr_price_loop = get_atr(symbol)
                atr_str_loop = f"{atr_price_loop:.8f}"
                self._log(f"""
=== INDICATEURS {symbol} ===
   Prix actuel: {opp['current_price']:.8f}
   RSI: {opp['rsi']:.2f}
   ATR: {atr_str_loop}
   ADX: {opp['adx'] if opp.get('adx') is not None else 'N/A'}
""")

        return opportunities
