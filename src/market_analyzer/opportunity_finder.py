"""Module pour la détection des opportunités de trading (simplifié)"""
import time
from typing import Dict, List, Tuple, Any
from datetime import datetime
from collections import deque

from config import Config
from .market_data import MarketData
from .indicator_calculator import get_atr
from utils.trading.trailing_buy import TrailingBuyRsi
from logger import trading_logger, error_logger
from utils.indicators.taapi_client import taapi_client

class OpportunityFinder:
    """Classe pour la détection des opportunités de trading"""
    def __init__(self, log_callback=None):
        self._log_callback = log_callback

    def _log(self, message: str, level: str = "info") -> None:
        if self._log_callback:
            self._log_callback(message, level)
        else:
            if level == "info":
                trading_logger.info(message)
            else:
                error_logger.error(message)
            print(message)

    def _format_rsi(self, v): return f"{v:.2f}" if v is not None else "N/A"

    
    def init_scoring_system(self, rsi_analyzer):
        """Méthode maintenue pour compatibilité mais qui n'initialise plus de scoring system"""
        self._log("✓ Mode trading RSI direct activé (sans système de scoring)")
    
    def _validate_opportunity(self, opportunity: Dict[str, Any]) -> bool:
        """Valide une opportunité de trading"""
        try:
            required_fields = ['symbol', 'current_price', 'rsi', 'market_info']
            if not all(field in opportunity for field in required_fields):
                self._log("❌ Champs manquants dans l'opportunité")
                return False
            
            if opportunity['current_price'] <= 0:
                self._log("❌ Prix actuel invalide")
                return False
                
            market_info = opportunity['market_info']
            if not market_info:
                self._log("❌ Informations de marché manquantes, utilisation de valeurs par défaut")
                opportunity['market_info'] = {
                    'min_amount': 0.0001,
                    'precision': {'amount': 8, 'price': 8},
                    'taker_fee': 0.00,
                    'maker_fee': 0.00
                }
                return True
            
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
    
    async def find_opportunities(
        self,
        symbols_to_analyze: List[str],
        market_data: Dict[str, MarketData],
        indicators_results: Dict[str, Tuple],
        market_infos: Dict[str, Dict],
        active_positions: set = None
    ) -> List[Dict[str, Any]]:
        """Analyse le marché pour identifier les opportunités de trading basées uniquement sur le trailing buy RSI"""
        if active_positions is None:
            active_positions = set()
        results = []
        
        for symbol in symbols_to_analyze:
            try:
                if symbol in active_positions:
                    self._log(f"Symbole {symbol} ignoré car position déjà ouverte", "info")
                    continue
                
                current_price, rsi, variation = indicators_results.get(symbol, (None, None, 0.0))
                if current_price is None or rsi is None:
                    self._log(f"Données insuffisantes pour {symbol}: prix={current_price}, RSI={rsi}", "error")
                    continue
                
                md = market_data.get(symbol)
                if not md:
                    self._log(f"Données de marché non disponibles pour {symbol}", "error")
                    continue
                
                md.last_price = current_price
                md.market_trend = "neutral"
                md.trend_variation = variation
                
                price_change = ((current_price - md.reference_price) / md.reference_price) * 100
                
                # Logs indicateurs de base
                atr_price = get_atr(symbol)
                atr_str = f"{atr_price:.8f}"
                willr_val = await taapi_client.get_williams_r(symbol.replace('/USDC','/USDT'))
                williams_str = f"{willr_val:.2f}" if willr_val is not None else "N/A"
                
                # OBV supprimé
                
                self._log(f"""
=== INDICATEURS {symbol} ===
   Prix actuel: {current_price:.8f}
   RSI: {rsi:.2f}
   ATR: {atr_str}
   Williams %R: {williams_str}
""", "info")
                
                # Trailing Buy RSI -> detection initiale RSI survente puis double tick
                if not hasattr(md, 'trailing_buy_rsi') or md.trailing_buy_rsi is None:
                    md.trailing_buy_rsi = TrailingBuyRsi()
                    md.rsi_confirm_counter = 0
                    md.rsi_last_value = None
                    md.rsi_wait_for_down = False
                    self._log(f"Trailing Buy RSI initialisé pour {symbol}", "info")
                
                md.trailing_buy_rsi.update(rsi, current_price)
                level = md.trailing_buy_rsi.current_level
                if not level:
                    continue
                threshold = level.buy_level
                self._log(f"Confirmation RSI: seuil d'achat = {threshold:.2f} pour {symbol}", "info")
                
                # Gestion attente après échec : bloquer ticks tant que RSI ne redescend pas
                if hasattr(md, 'rsi_wait_for_down') and md.rsi_wait_for_down:
                    if rsi < threshold:
                        self._log(f"RSI redescendu sous {threshold:.2f}, reprise ticks", "info")
                        md.rsi_wait_for_down = False
                        md.rsi_confirm_counter = 0
                    continue

                # Double tick confirmation
                if rsi >= threshold:
                    md.rsi_confirm_counter += 1
                    self._log(f"Tick {md.rsi_confirm_counter}/{Config.DOUBLE_CONFIRMATION_TICKS} RSI >= {threshold:.2f}", "info")
                else:
                    if md.rsi_confirm_counter > 0:
                        self._log(f"Réinitialisation ticks RSI pour {symbol} (RSI={rsi:.2f} < {threshold:.2f})", "info")
                    md.rsi_confirm_counter = 0
                
                if md.rsi_confirm_counter < Config.DOUBLE_CONFIRMATION_TICKS:
                    continue
                self._log(f"RSI confirmé pour {symbol}", "info")
                md.rsi_confirm_counter = 0
                md.trailing_buy_rsi._lock_state_for_buy = True
                md.trailing_buy_rsi._signal_emitted = True
                md.rsi_wait_for_down = True
                
                # Conditions supplémentaires
                # Williams %R strict entre -80 et -30
                if willr_val is None or not(-80 < willr_val < -30): #########
                    self._log(f"Williams %R hors plage: {williams_str}", "info")
                    md.trailing_buy_rsi.lowest_rsi = rsi
                    md.rsi_confirm_counter = 0
                    md.trailing_buy_rsi.reset()
                    md.rsi_wait_for_down = True
                    continue
                
                # DMI négatif avec la nouvelle logique à 3 niveaux
                dmi = await taapi_client.get_dmi(symbol.replace('/USDC','/USDT'), period=Config.ADX_LENGTH_VALID, interval=Config.ADX_INTERVAL_VALID)
                mdi = dmi['mdi'] if dmi else None
                mdi_str = f"{mdi:.2f}" if mdi is not None else "N/A"
                
                # Logique DMI améliorée avec trois niveaux
                # 1. Si DMI- > 30: Position annulée
                if mdi is not None and mdi > Config.DMI_NEGATIVE_THRESHOLD:
                    self._log(f"DMI- trop élevé: {mdi_str} > {Config.DMI_NEGATIVE_THRESHOLD}", "info")
                    md.trailing_buy_rsi.lowest_rsi = rsi
                    md.rsi_confirm_counter = 0
                    md.trailing_buy_rsi.reset()
                    md.rsi_wait_for_down = True
                    continue
                
                # Par défaut, utiliser les niveaux standard de trailing stop
                trailing_levels = Config.TRAILING_STOP_LEVELS
                
                # 2. Si 25 < DMI- <= 30: Utiliser les niveaux adaptatifs de trailing stop
                if mdi is not None and Config.DMI_MODERATE_THRESHOLD < mdi <= Config.DMI_NEGATIVE_THRESHOLD:
                    self._log(f"DMI- modéré: {mdi_str} (entre {Config.DMI_MODERATE_THRESHOLD} et {Config.DMI_NEGATIVE_THRESHOLD})", "info")
                    self._log(f"Utilisation du trailing stop adaptatif", "info")
                    trailing_levels = Config.ADAPTIVE_TRAILING_STOP_LEVELS
                
                # Calcul du score (Williams %R validée uniquement)
                score = 1
                self._log(f"Score calculé: {score}", "info")

                self._log("─────────────────────────────", "info")
                self._log(f"=== VERIFICATION DES INDICATEURS POUR {symbol} ===", "info")
                self._log("─────────────────────────────", "info")
                self._log(f"RSI actuel: {self._format_rsi(rsi)} | Seuil: {threshold:.2f}", "info")
                self._log(f"Williams %R: {self._format_rsi(willr_val)} | Condition requise [-80;-30] → {'OK' if willr_val is not None and -80 < willr_val < -30 else 'HORS PLAGE'}", "info")##############
                # Message DMI avec trois niveaux
                dmi_status = "N/A"
                if mdi is not None:
                    if mdi > Config.DMI_NEGATIVE_THRESHOLD:
                        dmi_status = "TROP ÉLEVÉ (position annulée)"
                    elif mdi > Config.DMI_MODERATE_THRESHOLD:
                        dmi_status = f"MODÉRÉ (trailing stop adaptatif)"
                    else:
                        dmi_status = "OK (trailing stop standard)"
                self._log(f"DMI (mdi): {self._format_rsi(mdi)} | Seuils: [{Config.DMI_MODERATE_THRESHOLD};{Config.DMI_NEGATIVE_THRESHOLD}] → {dmi_status}", "info")
                self._log(f"=== FIN DE LA VERIFICATION POUR {symbol} ===", "info")
                self._log("─────────────────────────────", "info")
                
                # Création de l'opportunité
                opp = {
                    'symbol': symbol,
                    'current_price': current_price,
                    'buy_price': current_price,
                    'reference_price': md.reference_price,
                    'price_change': price_change,
                    'rsi': rsi,
                    'market_info': market_infos.get(symbol, {}),
                    'timestamp': datetime.now(),
                    'trailing_buy_triggered': True,
                    'trailing_stop_levels': trailing_levels,
                    'score': score,
                    'position_size': 1.0
                }
                results.append(opp)
                
                self._log(f"""
=== SIGNAL D'ACHAT DÉTECTÉ ===
   Symbole: {symbol}
   RSI actuel: {rsi:.2f}
   Prix signal: {current_price:.8f}
""", "info")
                
            except Exception as e:
                self._log(f"Erreur d'analyse pour {symbol}: {e}", "error")
                continue
        
        return results
