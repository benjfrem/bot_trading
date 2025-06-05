"""Module pour la détection des opportunités de trading (simplifié)"""
import time
from typing import Dict, Optional, List, Tuple, Any
from datetime import datetime
from collections import deque

from config import Config
from .market_data import MarketData
from .indicator_calculator import get_atr
from utils.trading.trailing_buy import TrailingBuyRsi
from logger import trading_logger, error_logger
from utils.indicators.taapi_client import taapi_client

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
                # Désactivation Fisher Transform (non utilisé)
                #willr = await taapi_client.get_williams_r(symbol.replace('/USDC','/USDT'))
                #williams_str = f"{willr:.2f}" if willr is not None else "N/A"
                willr_val = await taapi_client.get_williams_r(symbol.replace('/USDC','/USDT'))
                williams_str = f"{willr_val:.2f}" if willr_val is not None else "N/A"
                
                if not hasattr(md, 'obv_history'):
                    md.obv_history = deque(maxlen=4)
                obv_val = await taapi_client.get_obv(symbol.replace('/USDC','/USDT'))
                obv_str = f"{obv_val:.2f}" if obv_val is not None else "N/A"
                md.obv_history.append(obv_val or 0.0)
                obv_sma = sum(md.obv_history) / len(md.obv_history)
                obv_sma_str = f"{obv_sma:.2f}"
                
                self._log(f"""
=== INDICATEURS {symbol} ===
   Prix actuel: {current_price:.8f}
   RSI: {rsi:.2f}
   ATR: {atr_str}
   Williams %R: {williams_str}
   OBV: {obv_str} / OBV SMA4: {obv_sma_str}
""", "info")
                
                # Trailing Buy RSI -> detection initiale RSI survente puis double tick
                if not hasattr(md, 'trailing_buy_rsi') or md.trailing_buy_rsi is None:
                    md.trailing_buy_rsi = TrailingBuyRsi()
                    md.rsi_confirm_counter = 0
                    md.rsi_last_value = None
                    self._log(f"Trailing Buy RSI initialisé pour {symbol}", "info")
                
                md.trailing_buy_rsi.update(rsi, current_price)
                level = md.trailing_buy_rsi.current_level
                if not level:
                    continue
                threshold = level.buy_level
                self._log(f"Confirmation RSI: seuil d'achat = {threshold:.2f} pour {symbol}", "info")
                
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
                
                # Conditions supplémentaires
                # Williams %R strict entre -80 et -40
                if willr_val is None or not(-80 < willr_val < -40):
                    self._log(f"Williams %R hors plage: {williams_str}", "info")
                    continue
                
                # DMI négatif
                dmi = await taapi_client.get_dmi(symbol.replace('/USDC','/USDT'), period=Config.ADX_LENGTH_VALID, interval=Config.ADX_INTERVAL_VALID)
                mdi = dmi['mdi'] if dmi else None
                mdi_str = f"{mdi:.2f}" if mdi is not None else "N/A"
                if mdi is not None and mdi > Config.DMI_NEGATIVE_THRESHOLD:
                    self._log(f"DMI- trop élevé: {mdi_str}", "info")
                    continue
                
                # OBV vs SMA : choix des trailing stop levels
                obv_ok = obv_val is not None and obv_val > obv_sma
                trailing_levels = Config.TRAILING_STOP_LEVELS if obv_ok else Config.ADAPTIVE_TRAILING_STOP_LEVELS
                self._log(f"OBV {'>' if obv_ok else '<='} SMA4 -> stop_levels = {'standard' if obv_ok else 'adaptive'}", "info")
                
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
                    'trailing_stop_levels': trailing_levels
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
