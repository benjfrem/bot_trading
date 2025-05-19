"""Module de gestion du Trailing Buy basé sur RSI avec adaptation aux tendances"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from logger import trading_logger
from config import Config

@dataclass
class TrailingBuyRsiLevel:
    """Représente un niveau de Trailing Buy basé sur RSI"""
    trigger_level: float  # Niveau de déclenchement RSI (bas)
    buy_level: float      # Niveau d'achat RSI (plus haut)
    is_immediate: bool    # Si True, achat immédiat au buy_level
    weight: int = 0       # Poids pour le scoring (optionnel)

class TrailingBuyRsi:
    """Gestion du Trailing Buy avec plusieurs niveaux basés sur RSI"""
    
    def __init__(self):
        """Initialise le trailing buy basé sur RSI"""
        self.lowest_rsi = 100  # Valeur RSI la plus basse observée (commence à 100)
        self.current_level = None
        self.last_update = datetime.now()
        
        # Attribut requis par le système pour la compatibilité
        self.analyze_started = False
        
        # État de verrouillage pour empêcher la réinitialisation prématurée
        self._lock_state_for_buy = False
        
        # Nouvel attribut pour suivre si un signal a déjà été émis mais pas encore traité
        self._signal_emitted = False
        
        # Initialiser avec les niveaux
        self._update_levels()
    
    def _update_levels(self) -> None:
        """Met à jour les niveaux RSI (uniquement niveaux neutres)"""
        # Utiliser uniquement les niveaux neutres
        config_levels = Config.TRAILING_BUY_RSI_LEVELS_NEUTRAL
        trading_logger.info(f"""
=== CONFIGURATION RSI STANDARD ===
   Stratégie: Standard (niveaux RSI équilibrés)
   Nombre de niveaux: {len(Config.TRAILING_BUY_RSI_LEVELS_NEUTRAL)}
   Plage de niveaux: {min([level['trigger'] for level in Config.TRAILING_BUY_RSI_LEVELS_NEUTRAL])} - {max([level['trigger'] for level in Config.TRAILING_BUY_RSI_LEVELS_NEUTRAL])}
""")
        
        # Conversion des niveaux de configuration en objets TrailingBuyRsiLevel
        self.levels = [
            TrailingBuyRsiLevel(
                trigger_level=level['trigger'],
                buy_level=level['stop'],
                is_immediate=level['immediate'],
                weight=level.get('weight', 0)
            )
            for level in config_levels
        ]
        
        # Logger les niveaux pour débogage
        self._log_current_levels()
    
    def _log_current_levels(self) -> None:
        """Affiche les niveaux RSI actuels dans les logs"""
        levels_str = "\n".join([
            f"   - Niveau {i+1}: Trigger: {level.trigger_level}, Buy: {level.buy_level}, "
            f"Immediate: {'Oui' if level.is_immediate else 'Non'}, "
            f"Weight: {level.weight}"
            for i, level in enumerate(self.levels)
        ])
        
        trading_logger.info(f"""
=== NIVEAUX RSI CONFIGURÉS ===
{levels_str}
""")
    
    # Méthode set_market_trend supprimée (plus de logique de tendance)
    
    def _get_applicable_level(self, current_rsi: float) -> Optional[TrailingBuyRsiLevel]:
        """Détermine le niveau de trailing buy applicable basé sur le RSI le plus bas observé
        
        La logique est la suivante:
        1. Si RSI min est entre 27-29, on attend qu'il remonte à 29
        2. Si RSI min est entre 24-27, on attend qu'il remonte à 27
        3. Si RSI min est entre 21-24, on attend qu'il remonte à 24
        Et ainsi de suite...
        """
        applicable_level = None
        
        # VÉRIFICATION CRITIQUE: Ne pas sélectionner de niveau si le RSI n'est jamais descendu en zone de survente
        if self.lowest_rsi > 25:
            trading_logger.info(f"""
=== AUCUN NIVEAU RSI APPLICABLE ===
   RSI minimum: {self.lowest_rsi:.2f}
   Seuil maximum: 25
   Raison: Le RSI n'est jamais descendu en zone de survente (<= 25)
""")
            return None
            
        # Trier les niveaux par trigger_level (du plus bas au plus haut)
        sorted_levels = sorted(self.levels, key=lambda x: x.trigger_level)
        
        # Cas spécial pour la zone RSI 27-29
        # Vérifier si le RSI minimum est entre 27 et 29
        if self.lowest_rsi <= 30 and self.lowest_rsi >= 25:
            # Créer un niveau spécial pour la zone 27-29
            applicable_level = TrailingBuyRsiLevel(
                trigger_level=25,  # Explicitement 27
                buy_level=30,      # Remontée à 29 pour achat
                is_immediate=True,
                weight=0
            )
            
            trading_logger.info(f"""
=== NIVEAU SPÉCIAL ZONE 25-30 ===
   RSI minimum: {self.lowest_rsi:.2f}
   Niveau de déclenchement: 25
   Niveau d'achat: 30
   Logique: Attendre que le RSI remonte à 30 après être descendu entre 25 et 30
""")
        else:
            # Pour les autres zones, appliquer la logique standard
            
            # On va trier les niveaux RSI du plus BAS au plus HAUT par trigger_level
            sorted_levels_asc = sorted(sorted_levels, key=lambda x: x.trigger_level)
                
            # Trouver le niveau spécifique où le RSI se trouve
            # Pour chaque niveau, on vérifie si le RSI minimum est descendu dans sa zone
            for i in range(len(sorted_levels_asc)):
                current_level = sorted_levels_asc[i]
                
                # Déterminer la borne supérieure de la zone
                upper_bound = 100.0  # Par défaut, le max possible pour RSI
                if i < len(sorted_levels_asc) - 1:
                    next_level = sorted_levels_asc[i + 1]
                    upper_bound = next_level.trigger_level
                
                # Vérifier si le RSI min est dans cette zone spécifique:
                # - Supérieur ou égal au trigger du niveau actuel
                # - Strictement inférieur au trigger du niveau suivant
                if self.lowest_rsi >= current_level.trigger_level and self.lowest_rsi < upper_bound:
                    applicable_level = current_level
                    trading_logger.info(f"""
=== SÉLECTION NIVEAU RSI CORRECT ===
   RSI minimum: {self.lowest_rsi:.2f}
   Niveau sélectionné: trigger={current_level.trigger_level}, buy={current_level.buy_level}
   Zone: [{current_level.trigger_level} - {upper_bound})
   Vérification: {current_level.trigger_level} <= {self.lowest_rsi:.2f} < {upper_bound}
""")
                    break
            
            # Si aucun niveau n'a été trouvé mais le RSI est <= au niveau le plus bas, utiliser le niveau le plus bas
            if applicable_level is None and sorted_levels_asc and self.lowest_rsi <= sorted_levels_asc[0].trigger_level:
                applicable_level = sorted_levels_asc[0]
                trading_logger.info(f"""
=== SÉLECTION NIVEAU RSI LE PLUS BAS ===
   RSI minimum: {self.lowest_rsi:.2f}
   Niveau sélectionné: trigger={applicable_level.trigger_level}, buy={applicable_level.buy_level}
   Raison: RSI descendu en-dessous du niveau le plus bas
""")
        
        # Log supplémentaire pour débogage
        if applicable_level:
            # Cas du niveau spécial 27-29 qui n'est pas dans sorted_levels
            if applicable_level.trigger_level == 25 and applicable_level.buy_level == 30:
                trading_logger.info(f"""
=== NIVEAU RSI APPLICABLE ===
   RSI le plus bas: {self.lowest_rsi:.2f}
   Niveau sélectionné: trigger={applicable_level.trigger_level}, buy={applicable_level.buy_level}
   Explication: {self.lowest_rsi:.2f} est entre 27.5 et 30 (cas spécial)
""")
            else:
                # Pour les niveaux standard qui sont dans la liste
                try:
                    level_index = sorted_levels.index(applicable_level)
                    
                    # Trouver le niveau supérieur pour l'explication
                    upper_bound = 100.0
                    for level in sorted_levels:
                        if level.trigger_level > applicable_level.trigger_level:
                            upper_bound = level.trigger_level
                            break
                    
                    trading_logger.info(f"""
=== NIVEAU RSI APPLICABLE ===
   RSI le plus bas: {self.lowest_rsi:.2f}
   Niveau sélectionné: trigger={applicable_level.trigger_level}, buy={applicable_level.buy_level}
   Explication: RSI minimum est dans la zone [{applicable_level.trigger_level} - {upper_bound})
""")
                except ValueError:
                    # Si le niveau n'est pas dans la liste pour une raison quelconque
                    trading_logger.info(f"""
=== NIVEAU RSI APPLICABLE ===
   RSI le plus bas: {self.lowest_rsi:.2f}
   Niveau sélectionné: trigger={applicable_level.trigger_level}, buy={applicable_level.buy_level}
   Explication: Niveau personnalisé
""")
        
        return applicable_level
    
    # Méthode stop_trend_analysis supprimée (plus de logique de tendance)
        
    # Méthode get_short_term_trend supprimée
        
    def start_trend_analysis(self):
        """Démarre l'analyse de tendance"""
        self.analyze_started = True
        trading_logger.info("Analyse de tendance RSI démarrée")
        
    def update_short_term_trend(self, current_price: float, current_time: datetime):
        """Mise à jour de la tendance à court terme (stub pour compatibilité)"""
        # Cette méthode est maintenue pour la compatibilité mais n'a plus de fonctionnalité active
        pass
    
    def update(self, current_rsi: float, current_price: float, log_enabled: bool = True) -> Optional[float]:
        """Met à jour le trailing buy RSI et retourne le prix d'achat si les conditions sont remplies"""
        # Si un signal a déjà été émis mais pas encore traité, ne pas générer de nouveau signal
            
        if current_rsi is None or current_price <= 0:
            if log_enabled:
                trading_logger.info(f"""
=== MISE À JOUR RSI IMPOSSIBLE ===
   RSI actuel: {current_rsi}
   Prix actuel: {current_price}
   Raison: Valeurs invalides
""")
            return None
        
        # Le paramètre trend est ignoré, on utilise toujours la tendance neutre
        
        # Le RSI atteint 27 ou descend en dessous, démarrer le suivi
        if current_rsi <= 27:
            trading_logger.info(f"""
=== DÉMARRAGE SUIVI TRAILING BUY RSI ===
   RSI actuel: {current_rsi:.2f}
   Seuil de démarrage: 25
   Action: Activation du suivi des niveaux RSI
""")
            
        # La mise à jour du RSI le plus bas se fait juste après
        
        # Mettre à jour le RSI le plus bas si nécessaire
        if current_rsi < self.lowest_rsi:
            old_lowest = self.lowest_rsi
            self.lowest_rsi = current_rsi
            if log_enabled:
                trading_logger.info(f"""
=== NOUVEAU RSI MINIMUM ===
   Ancien minimum: {old_lowest:.2f}
   Nouveau minimum: {self.lowest_rsi:.2f}
   Prix actuel: {current_price:.8f}
""")
        
        # Vérifier si les niveaux sont disponibles
        if not self.levels:
            if log_enabled:
                trading_logger.info("=== ERREUR: AUCUN NIVEAU RSI CONFIGURÉ ===")
            return None
        
        # Si on arrive ici, on continue avec la logique originale
        applicable_level = self._get_applicable_level(current_rsi)
        
        if not applicable_level:
            if log_enabled:
                trading_logger.info(f"""
=== AUCUN NIVEAU RSI APPLICABLE ===
   RSI actuel: {current_rsi:.2f}
   RSI le plus bas: {self.lowest_rsi:.2f}
   Raison: Le RSI minimum n'a pas atteint les seuils de déclenchement
""")
            return None
        
        # Si le niveau a changé, logger l'information
        if self.current_level != applicable_level:
            old_level = self.current_level
            self.current_level = applicable_level
            if log_enabled:
                trading_logger.info(f"""
=== CHANGEMENT NIVEAU RSI ===
   Ancien niveau: {old_level.trigger_level if old_level else 'Aucun'}
   Nouveau niveau: {applicable_level.trigger_level}
   Déclenchement: {applicable_level.trigger_level:.2f}
   Achat: {applicable_level.buy_level:.2f}
   Achat immédiat: {'Oui' if applicable_level.is_immediate else 'Non'}
   Poids: {applicable_level.weight}
""")
        
        # Si le RSI actuel est inférieur au RSI le plus bas, mettre à jour le RSI le plus bas
        # mais ne pas déclencher d'achat (comparaison stricte pour permettre l'achat si égal)
        if current_rsi < self.lowest_rsi:
            if log_enabled:
                trading_logger.info(f"""
=== RSI ENCORE EN BAISSE ===
   RSI actuel: {current_rsi:.2f}
   RSI le plus bas précédent: {self.lowest_rsi:.2f}
   Action: Mise à jour du RSI minimum, pas d'achat
""")
            return None
        elif current_rsi == self.lowest_rsi:
            if log_enabled:
                trading_logger.info(f"""
=== RSI STABLE AU MINIMUM ===
   RSI actuel: {current_rsi:.2f}
   RSI minimum: {self.lowest_rsi:.2f}
   Action: Continuer l'analyse (possible achat)
""")
            
        # Si le RSI remonte, vérifier s'il a dépassé le niveau d'achat
        if current_rsi >= applicable_level.buy_level:
            old_lowest = self.lowest_rsi
            
            # IMPORTANT: Ne pas réinitialiser immédiatement le RSI minimum
            # car cela pourrait interférer avec l'exécution de l'ordre
            # La réinitialisation sera effectuée par reset() après confirmation de l'achat
            
            if applicable_level.is_immediate:
                # Ne plus afficher les logs ici, laissons opportunity_finder s'en charger
                
                # Protéger les niveaux actuels pour empêcher leur réinitialisation
                # avant que l'ordre ne soit traité
                self._lock_state_for_buy = True
                # Marquer qu'un signal a été émis pour éviter sa répétition
                self._signal_emitted = True
                
                # Log réduit et discret
                trading_logger.info(f"Signal de prix détecté pour {current_price:.8f}")
                return current_price
            else:
                # Ne plus afficher les logs ici, laissons opportunity_finder s'en charger
                
                # Protéger les niveaux actuels pour empêcher leur réinitialisation
                # avant que l'ordre ne soit traité
                self._lock_state_for_buy = True
                # Marquer qu'un signal a été émis pour éviter sa répétition
                self._signal_emitted = True
                
                # Log réduit et discret
                trading_logger.info(f"Signal de prix détecté pour {current_price:.8f}")
                return current_price
        elif log_enabled:
            trading_logger.info(f"""
=== RSI REMONTANT MAIS INSUFFISANT ===
   RSI actuel: {current_rsi:.2f}
   RSI le plus bas: {self.lowest_rsi:.2f}
   Niveau d'achat requis: {applicable_level.buy_level:.2f}
   Écart: {applicable_level.buy_level - current_rsi:.2f}
   Action: Attente de remontée supplémentaire
""")
        
        return None
    
    def reset(self):
        """Réinitialise complètement le trailing buy RSI"""
        # Vérifier si l'état est verrouillé pour un achat en cours
        if hasattr(self, '_lock_state_for_buy') and self._lock_state_for_buy:
            trading_logger.info("""
=== RÉINITIALISATION DIFFÉRÉE ===
   Raison: Achat en cours de traitement
   Action: Verrouillage maintenu pour protéger les niveaux RSI actuels
""")
            # Simplement déverrouiller l'état pour permettre une future réinitialisation
            # après que l'ordre actuel soit traité
            self._lock_state_for_buy = False
            return
            
        # Réinitialiser les valeurs RSI
        self.lowest_rsi = 100
        self.current_level = None
        self.last_update = datetime.now()
        # Réinitialiser le flag de signal émis pour permettre de nouveaux signaux
        self._signal_emitted = False
        
        trading_logger.info("""
=== RÉINITIALISATION COMPLÈTE TRAILING BUY RSI ===
   RSI minimum réinitialisé à 100
   Niveau applicable effacé
""")
