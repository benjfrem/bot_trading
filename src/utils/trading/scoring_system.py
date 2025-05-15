"""Module de scoring pour les décisions de trading"""
from typing import Dict, Optional, Any, List, Tuple
from dataclasses import dataclass
from datetime import datetime
from logger import trading_logger
from config import Config
from utils.trading.trailing_buy import TrailingBuyRsi

@dataclass
class ScoringResult:
    """Structure de données pour les résultats du scoring"""
    symbol: str                     # Symbole analysé
    total_score: int                # Score total (0-100)
    rsi_score: int                  # Score RSI (0-40)
    bb_score: int                   # Score Bollinger Bands (0-30)
    volume_score: int               # Score Volume (0-30)
    rsi_level: Optional[int]        # Niveau RSI déclenché (1-4 ou None)
    position_size: float            # Taille de position recommandée (0.0-1.0)
    timestamp: datetime             # Horodatage du calcul
    details: Dict[str, Any]         # Détails supplémentaires

class ScoringSystem:
    """Système de scoring pour les décisions de trading"""
    
    def __init__(self, rsi_analyzer: TrailingBuyRsi):
        """Initialise le système de scoring"""
        self.rsi_analyzer = rsi_analyzer
        self.last_scores: Dict[str, ScoringResult] = {}
        trading_logger.info("Système de scoring initialisé")
    
    def calculate_rsi_score(self, symbol: str, current_rsi: float) -> Tuple[int, Optional[int]]:
        """Calcule le score RSI et détermine le niveau déclenché"""
        # Obtenir le TrailingBuyRsi via opportunity_finder qui l'a initialisé
        trading_logger.info(f"Évaluation du score RSI pour {symbol}, RSI: {current_rsi:.2f}")
        
        # Vérifier si le trailing buy RSI est en cours d'analyse
        from market_analyzer.analyzer import MarketAnalyzer
        market_data = MarketAnalyzer().market_data.get(symbol)
        
        if market_data and hasattr(market_data, 'trailing_buy_rsi') and market_data.trailing_buy_rsi:
            trailing_buy = market_data.trailing_buy_rsi
            
            # Utiliser le RSI le plus bas enregistré par le trailing buy
            lowest_rsi = trailing_buy.lowest_rsi
            trading_logger.info(f"RSI le plus bas pour {symbol}: {lowest_rsi:.2f} (actuel: {current_rsi:.2f})")
            
            # Déterminer le niveau RSI déclenché basé sur le RSI le plus bas
            rsi_level = None
            for i, level in enumerate(Config.TRAILING_BUY_RSI_LEVELS):
                if lowest_rsi <= level['trigger']:
                    rsi_level = i + 1  # Niveau 1, 2, 3 ou 4
                    trading_logger.info(f"Niveau RSI {rsi_level} déclenché (trigger: {level['trigger']})")
                    break  # On prend le premier niveau déclenché (le plus haut)
        else:
            # Utiliser la méthode d'origine si le trailing buy n'est pas disponible
            rsi_level = None
            for i, level in enumerate(Config.TRAILING_BUY_RSI_LEVELS):
                if current_rsi <= level['trigger']:
                    rsi_level = i + 1  # Niveau 1, 2, 3 ou 4
        
        if rsi_level is None:
            trading_logger.info(f"Aucun niveau RSI déclenché pour {symbol}")
            return 0, None
        
        # Attribuer le score en fonction du niveau
        score_key = f'level_{rsi_level}'
        rsi_score = Config.RSI_SCORES.get(score_key, 0)
        
        trading_logger.info(f"Score RSI pour {symbol}: {rsi_score} (niveau {rsi_level})")
        return rsi_score, rsi_level
    
    def calculate_score(self, symbol: str, current_price: float, current_rsi: float) -> ScoringResult:
        """Calcule le score total pour une opportunité de trading"""
        # Calculer le score RSI
        rsi_score, rsi_level = self.calculate_rsi_score(symbol, current_rsi)
        
        # Ignorer les scores des Bollinger Bands et du Volume
        bb_score = 0
        volume_score = 0
        
        # Le score total est maintenant uniquement basé sur le RSI
        total_score = rsi_score
        
        # Déterminer la taille de position recommandée (toujours 100%)
        position_size = self._determine_position_size(total_score)
        
        # Collecter les détails pour le logging et le débogage
        details = {
            'price': current_price,
            'rsi': current_rsi,
            'rsi_level': rsi_level,
            'bb_position': 'Désactivé',
            'volume_status': 'Désactivé'
        }
        
        # Créer le résultat
        result = ScoringResult(
            symbol=symbol,
            total_score=total_score,
            rsi_score=rsi_score,
            bb_score=bb_score,
            volume_score=volume_score,
            rsi_level=rsi_level,
            position_size=position_size,
            timestamp=datetime.now(),
            details=details
        )
        
        # Stocker le dernier score
        self.last_scores[symbol] = result
        
        return result
    
    def _determine_position_size(self, total_score: int) -> float:
        """Détermine la taille de position recommandée en fonction du score total"""
        # Toujours retourner 100% de la position planifiée, indépendamment du score
        return 1.0
    
    def should_open_position(self, symbol: str) -> Tuple[bool, float]:
        """Détermine si une position doit être ouverte et avec quelle taille"""
        if symbol not in self.last_scores:
            return False, 0.0
        
        score_result = self.last_scores[symbol]
        
        # Une position doit être ouverte si un niveau RSI est déclenché
        should_open = score_result.rsi_level is not None
        
        # Toujours retourner 100% de la position
        return should_open, 1.0
    
    def format_score_details(self, symbol: str) -> str:
        """Formate les détails du score pour le logging"""
        if symbol not in self.last_scores:
            return "Aucun score disponible"
        
        score = self.last_scores[symbol]
        
        # Formater les détails du score (simplifié, uniquement RSI)
        details = f"""
=== DÉTAILS DU TRADING POUR {symbol} ===
RSI: {score.details['rsi']:.2f} (Niveau {score.rsi_level if score.rsi_level else 'N/A'})
Prix actuel: {score.details['price']:.8f} USDC
Taille de position: 100%

Autres indicateurs: Désactivés
"""
        
        return details
