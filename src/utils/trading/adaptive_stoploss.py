"""
Module de gestion du Stop Loss pour le bot de trading.

Ce module intègre le système de Stop Loss adaptatif basé sur l'ATR.
Le stop loss est calculé à partir de l'ATR :
  - atr_ratio = atr_price / last_price
  - stop_distance = atr_ratio × ATR_MULTIPLIER
  - stop_level = entry_price × (1 − stop_distance)
Un délai anti-mèche (STOP_TIMEOUT_SEC) est appliqué avant de déclencher la liquidation.
"""

import time
from config import Config
from market_analyzer.indicator_calculator import get_atr
from utils.exchange.exchange_utils import log_event

class AdaptiveStopLoss:
    """
    Stop Loss adaptatif basé sur l'ATR.
    - entry_price : prix d'entrée de la position
    - symbol      : paire de trading (ex. 'BTC/USDT')
    """
    def __init__(self, entry_price: float = 0.0, symbol: str = ""):
        self.entry_price = entry_price
        self.symbol = symbol
        # Niveau initial du stop loss = prix d'entrée (0% de perte)
        self.current_stop_level = entry_price
        self.trigger_time = None

    def update(self, last_price: float) -> bool:
        """
        Met à jour le niveau de stop loss et renvoie True si la position
        doit être liquidée (prix sous stop_level depuis >= STOP_TIMEOUT_SEC).
        """
        # Récupérer l'ATR brut
        atr_price = get_atr(self.symbol)
        if not atr_price or last_price <= 0:
            return False

        # Calcul du ratio ATR et de la distance de stop
        atr_ratio = atr_price / last_price
        stop_distance = atr_ratio * Config.ATR_MULTIPLIER

        # Calcul du nouveau niveau de stop loss
        new_stop_level = self.entry_price * (1 - stop_distance)
        log_event(
            f"CALCUL STOP LOSS ADAPTATIF {self.symbol}: "
            f"ATR={atr_price:.8f}, ATR_RATIO={atr_ratio:.6f}, "
            f"STOP_DISTANCE={stop_distance:.6f}, NEW_STOP_LEVEL={new_stop_level:.8f}",
            "info"
        )

        # Mise à jour si on peut resserrer le stop loss
        if new_stop_level < self.current_stop_level:
            old_level = self.current_stop_level
            self.current_stop_level = new_stop_level
            self.trigger_time = None
            log_event(
                f"NOUVEAU STOP LEVEL pour {self.symbol}: "
                f"{old_level:.8f} → {new_stop_level:.8f}",
                "info"
            )

        # Anti-mèche : déclencher la liquidation si le prix reste sous le stop level
        if last_price <= self.current_stop_level:
            if self.trigger_time is None:
                self.trigger_time = time.time()
                return False
            elif time.time() - self.trigger_time >= Config.STOP_TIMEOUT_SEC:
                self.trigger_time = None
                return True
        else:
            self.trigger_time = None

        return False

# Alias pour la gestion du stop loss
StopLossManager = AdaptiveStopLoss
