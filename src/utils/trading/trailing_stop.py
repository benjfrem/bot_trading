"""Module de gestion du Trailing Stop Loss"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from logger import trading_logger
from config import Config

@dataclass
class TrailingStopLevel:
    """Représente un niveau de Trailing Stop"""
    trigger_level: float  # Niveau de déclenchement en pourcentage
    stop_level: float    # Niveau de stop en pourcentage
    is_immediate: bool   # Si True, vente immédiate au stop_level

class TrailingStopLoss:
    """Gestion du Trailing Stop Loss avec plusieurs niveaux"""
    
    def __init__(self, entry_price: float, levels_config=None):
        self.entry_price = entry_price
        self.highest_price = entry_price
        self.current_level = None
        self.last_update = datetime.now()
        self.highest_profit_percentage = 0.0
        
        # Charger les niveaux depuis la configuration ou utiliser ceux fournis
        self.levels = self._load_levels_from_config(levels_config)
        
        trading_logger.info(f"""
=== INITIALISATION TRAILING STOP ===
Prix d'entrée: {entry_price:.8f}
Niveaux configurés:
{self._format_levels()}
""")
        
    def get_current_applicable_level(self) -> Optional[dict]:
        """Retourne le niveau de trailing stop applicable actuel au format dict
        
        Returns:
            Un dictionnaire contenant trigger et stop, ou None si aucun niveau applicable
        """
        if not self.current_level:
            return None
            
        return {
            'trigger': self.current_level.trigger_level,
            'stop': self.current_level.stop_level,
            'immediate': self.current_level.is_immediate
        }
    
    def _load_levels_from_config(self, levels_config=None) -> List[TrailingStopLevel]:
        """Charge les niveaux de trailing stop depuis la configuration ou depuis les niveaux fournis"""
        levels = []
        # Utiliser les niveaux fournis ou ceux de la configuration par défaut
        config_to_use = levels_config if levels_config is not None else Config.TRAILING_STOP_LEVELS
        
        for level_config in config_to_use:
            levels.append(TrailingStopLevel(
                trigger_level=level_config['trigger'],
                stop_level=level_config['stop'],
                is_immediate=level_config['immediate']
            ))
        return levels
    
    def _format_levels(self) -> str:
        """Formate les niveaux de trailing stop pour l'affichage"""
        return "\n".join([
            f"- Niveau {i+1}: Déclenchement +{level.trigger_level:.2f}% → Stop +{level.stop_level:.2f}% ({'Immédiat' if level.is_immediate else 'Différé'})"
            for i, level in enumerate(self.levels)
        ])
    
    def _calculate_price_change(self, current_price: float) -> float:
        """Calcule la variation de prix en pourcentage"""
        return ((current_price - self.entry_price) / self.entry_price) * 100
    
    def _get_applicable_level(self, price_change: float) -> Optional[TrailingStopLevel]:
        """Détermine le niveau de trailing stop applicable
        
        Un niveau est applicable si le profit est compris entre le stop et le trigger du niveau :
        stop_level <= price_change < trigger_level
        
        Si le profit est supérieur au trigger du niveau le plus élevé, on utilise ce niveau.
        """
        # Si on a déjà un niveau et que le prix actuel est en baisse,
        # on conserve le niveau actuel (pas de downgrade)
        if self.current_level and price_change < self.highest_profit_percentage:
            return self.current_level
            
        # Si le profit dépasse le trigger du niveau le plus élevé, utiliser ce niveau
        if price_change >= self.levels[-1].trigger_level:
            applicable_level = self.levels[-1]
            trading_logger.info(f"""
Niveau de trailing stop le plus élevé atteint:
   Profit actuel: +{price_change:.2f}%
   Niveau trigger: +{applicable_level.trigger_level:.2f}%
   Niveau stop: +{applicable_level.stop_level:.2f}%
""")
            return applicable_level
            
        # Parcourir tous les niveaux pour trouver celui où stop_level <= price_change < trigger_level
        applicable_level = None
        
        for i, level in enumerate(self.levels):
            # Vérifier si c'est le dernier niveau
            is_last_level = (i == len(self.levels) - 1)
            
            # Déterminer le seuil supérieur (trigger du niveau actuel)
            upper_bound = level.trigger_level
            
            # Déterminer le seuil inférieur (stop du niveau actuel)
            lower_bound = level.stop_level
            
            # Vérifier si le profit est dans la plage de ce niveau
            if lower_bound <= price_change < upper_bound:
                applicable_level = level
                break
        
        # Afficher des logs détaillés pour le débogage
        if applicable_level:
            trading_logger.info(f"""
Niveau de trailing stop applicable trouvé:
   Profit actuel: +{price_change:.2f}%
   Niveau trigger: +{applicable_level.trigger_level:.2f}%
   Niveau stop: +{applicable_level.stop_level:.2f}%
""")
        else:
            # Si aucun niveau n'est trouvé, vérifier si on est en dessous du premier seuil
            if price_change < self.levels[0].stop_level:
                trading_logger.info(f"""
Aucun niveau de trailing stop applicable:
   Profit actuel: +{price_change:.2f}%
   Premier niveau stop: +{self.levels[0].stop_level:.2f}% (non atteint)
""")
            else:
                trading_logger.info(f"""
Aucun niveau de trailing stop applicable:
   Profit actuel: +{price_change:.2f}%
   Raison: Profit ne correspond à aucune plage de niveaux configurée
""")
                
        return applicable_level
    
    def update(self, current_price: float) -> Optional[float]:
        """Met à jour le trailing stop et retourne le prix de vente si le stop est déclenché"""
        # Initialisation des ticks de confirmation de vente
        if not hasattr(self, 'exit_confirm_counter'):
            self.exit_confirm_counter = 0
            self.exit_first_tick_price = None
        if current_price <= 0:
            trading_logger.info(f"Prix actuel invalide: {current_price}")
            return None
        
        # Calculer le profit actuel
        price_change = self._calculate_price_change(current_price)
        
        # Mettre à jour le profit le plus élevé et le prix le plus haut
        price_updated = False
        if price_change > self.highest_profit_percentage:
            old_profit = self.highest_profit_percentage
            self.highest_profit_percentage = price_change
            trading_logger.info(f"Nouveau profit maximum: +{self.highest_profit_percentage:.2f}% (ancien: +{old_profit:.2f}%)")
            price_updated = True
            
        if current_price > self.highest_price:
            old_highest = self.highest_price
            self.highest_price = current_price
            trading_logger.info(f"Nouveau prix le plus haut: {self.highest_price:.8f} (ancien: {old_highest:.8f})")
            price_updated = True
        
        # Déterminer le niveau applicable basé sur le profit maximum atteint (pas le profit actuel)
        applicable_level = self._get_applicable_level(self.highest_profit_percentage)
        
        # Log détaillé de l'état actuel
        if applicable_level:
            trading_logger.info(f"""
=== ÉTAT TRAILING STOP ===
Prix d'entrée: {self.entry_price:.8f}
Prix actuel: {current_price:.8f}
Prix le plus haut: {self.highest_price:.8f}
Profit actuel: +{price_change:.2f}%
Profit maximum: +{self.highest_profit_percentage:.2f}%
Niveau applicable: {applicable_level.stop_level:.2f}% / {applicable_level.trigger_level:.2f}% (profit entre ces valeurs)
""")
        else:
            trading_logger.info(f"""
=== ÉTAT TRAILING STOP ===
Prix d'entrée: {self.entry_price:.8f}
Prix actuel: {current_price:.8f}
Prix le plus haut: {self.highest_price:.8f}
Profit actuel: +{price_change:.2f}%
Profit maximum: +{self.highest_profit_percentage:.2f}%
Niveau applicable: Aucun
""")
        
        if not applicable_level:
            return None
        
        # Si le niveau a changé, logger l'information
        if self.current_level != applicable_level:
            old_level = "Aucun" if not self.current_level else f"+{self.current_level.trigger_level:.2f}%"
            self.current_level = applicable_level
            trading_logger.info(f"""
Changement de niveau de trailing stop:
   Ancien niveau: {old_level}
   Nouveau niveau: +{applicable_level.trigger_level:.2f}%
   Déclenchement: +{applicable_level.trigger_level:.2f}%
   Stop: +{applicable_level.stop_level:.2f}%
   Vente immédiate: {'Oui' if applicable_level.is_immediate else 'Non'}
""")
        
        # Calculer le prix de stop basé sur le prix le plus haut atteint
        # Pour un vrai trailing stop, on utilise le prix le plus haut comme référence
        # et on calcule le prix qui correspond au niveau de stop en pourcentage
        
        # Calculer la différence entre le niveau de déclenchement et le niveau de stop
        trigger_to_stop_diff = applicable_level.trigger_level - applicable_level.stop_level
        
        # Calculer le pourcentage de trailing par rapport au prix le plus haut
        # Si le prix a monté de 0.5% et que le stop est à 0.3%, alors on veut maintenir
        # un écart de 0.2% par rapport au prix le plus haut
        trailing_percentage = trigger_to_stop_diff / 100
        
        # Calculer le prix de stop en fonction du prix le plus haut
        trailing_stop_price = self.highest_price * (1 - trailing_percentage)
        
        # Assurer que le stop price est au moins au niveau du prix d'entrée + stop_level
        min_stop_price = self.entry_price * (1 + applicable_level.stop_level / 100)
        
        # Utiliser le prix de stop le plus élevé des deux
        stop_price = max(trailing_stop_price, min_stop_price)
        
        # Si le prix vient d'être mis à jour (nouveau maximum), ne pas déclencher de vente
        # Cela permet de suivre la tendance haussière et de ne vendre qu'en cas de renversement
        if price_updated:
            trading_logger.info(f"""
Prix en hausse, mise à jour du trailing stop:
   Nouveau prix de stop: {stop_price:.8f}
   Vente différée pour suivre la tendance haussière
""")
            return None
        
        trading_logger.info(f"""
Calcul du prix de stop:
   Prix le plus haut: {self.highest_price:.8f}
   Différence trigger-stop: {trigger_to_stop_diff:.2f}%
   Pourcentage de trailing: {trailing_percentage:.4f}
   Prix de stop calculé: {trailing_stop_price:.8f}
   Prix de stop minimum: {min_stop_price:.8f}
   Prix de stop final: {stop_price:.8f}
""")
        
        # Vente immédiate dès le premier tick en dessous du stop loss
        if current_price <= stop_price:
            # Premier et unique tick pour la sortie
            trading_logger.info(
                f"SORTIE IMMÉDIATE pour {current_price:.8f} (seuil stop = {stop_price:.8f})"
            )
            
            # Pour des raisons de compatibilité et pour les logs, on garde ces variables
            # mais elles ne sont plus utilisées pour la décision de sortie
            self.exit_confirm_counter = 0
            self.exit_first_tick_price = None
            
            # Exécution de la vente immédiatement
            return stop_price if applicable_level.is_immediate else current_price
        # reset si le prix repasse au-dessus du stop
        if self.exit_confirm_counter > 0 and current_price > stop_price:
            trading_logger.info(
                f"Réinitialisation ticks de sortie: prix repassé au-dessus du stop ({current_price:.8f} > {stop_price:.8f})"
            )
            self.exit_confirm_counter = 0
            self.exit_first_tick_price = None
        return None
