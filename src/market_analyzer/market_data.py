"""Module contenant la structure de données pour les informations de marché"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from utils.trading.scoring_system import ScoringResult

@dataclass
class RsiState:
    """État du calcul du RSI qui peut être réutilisé entre les mises à jour"""
    avg_gain: float = 0.0
    avg_loss: float = 0.0
    last_price: float = 0.0
    initialized: bool = False
    last_update: Optional[datetime] = None

@dataclass
class MarketData:
    """Structure de données pour les informations de marché"""
    reference_price: float
    last_update: datetime
    consecutive_increases: int
    last_price: float
    rsi_value: Optional[float] = None
    rsi_timestamp: Optional[datetime] = None

    # Données historiques pour les indicateurs
    price_history: List[float] = None
    volume_history: List[float] = None

    # RSI multi-périodes (clé: période, valeur: RSI)
    multi_period_rsi: Dict[int, Optional[float]] = field(default_factory=dict)

    # État du RSI pour le calcul incrémental
    rsi_state: RsiState = field(default_factory=RsiState)

    # Derniers scores calculés
    last_score: Optional[ScoringResult] = None

    # Tendance du marché
    market_trend: str = "neutral"
    trend_variation: float = 0.0

    # Flag pour indiquer qu'un signal d'achat RSI a été détecté mais pas encore traité
    rsi_buy_signal_pending: bool = False

    # Prix du signal d'achat RSI en attente
    rsi_buy_signal_price: Optional[float] = None

    # Compteurs pour la confirmation RSI
    rsi_confirm_counter: int = 0
    rsi_last_confirm_value: Optional[float] = None

    # Données DMI (ADX et DI)
    adx: Optional[float] = None
    plus_di: Optional[float] = None
    minus_di: Optional[float] = None
    adx_last_check: float = 0.0
    
    # Williams %R
    williams_value: Optional[float] = None
    
    # SMA du RSI
    rsi_sma_value: Optional[float] = None
