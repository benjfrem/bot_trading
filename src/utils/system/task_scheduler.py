"""Gestionnaire des tâches planifiées"""
import asyncio
import time
from typing import Callable, Coroutine, Dict, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from logger import trading_logger, error_logger

class TaskScheduler:
    def __init__(self):
        """Initialise le planificateur de tâches"""
        # Configuration optimisée du scheduler
        self.scheduler = AsyncIOScheduler(
            job_defaults={
                'coalesce': True,       # Combine les exécutions manquées
                'max_instances': 1,     # Limite à une instance par tâche
                'misfire_grace_time': 60  # Délai de grâce pour les exécutions manquées (en secondes)
            }
        )
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.last_execution: Dict[str, float] = {}
        self.task_start_time: Dict[str, float] = {}  # Timestamp de démarrage de chaque tâche
        self.max_task_duration: float = 1.5  # Durée maximale d'une tâche en secondes
    
    def add_task(self, name: str, func: Callable[[], Coroutine], interval: int, 
                condition: Callable[[], Coroutine] = None) -> None:
        """
        Ajoute une nouvelle tâche planifiée
        
        Args:
            name: Nom de la tâche
            func: Fonction à exécuter (coroutine)
            interval: Intervalle d'exécution en secondes
            condition: Fonction facultative qui retourne un booléen indiquant si la tâche doit être exécutée
        """
        self.tasks[name] = {
            'function': func,
            'interval': interval,
            'running': False,
            'condition': condition
        }
        self.last_execution[name] = 0
        
        async def wrapper():
            """Wrapper pour exécuter la coroutine avec gestion d'erreurs et de chevauchement"""
            # Vérifier si la tâche est déjà en cours d'exécution
            is_running = self.tasks[name]['running']
            current_time = time.time()
            
            if is_running:
                # Vérifier si la tâche est bloquée depuis trop longtemps
                task_start = self.task_start_time.get(name, 0)
                if task_start > 0 and (current_time - task_start) > self.max_task_duration:
                    # La tâche est bloquée depuis trop longtemps, la considérer comme interrompue
                    trading_logger.info(f"⚠️ Tâche {name} bloquée depuis {current_time - task_start:.2f}s (> {self.max_task_duration}s), réinitialisation forcée")
                    self.tasks[name]['running'] = False
                    is_running = False
                else:
                    # Tâche en cours d'exécution mais pas bloquée, exécution ignorée
                    # Supprimer les logs pour éviter de spammer
                    # trading_logger.info(f"Tâche {name} déjà en cours d'exécution, exécution ignorée")
                    return
                
            # Vérifier la condition d'exécution si elle existe
            condition_func = self.tasks[name]['condition']
            if condition_func:
                should_run = await condition_func()
                if not should_run:
                    # Ne pas exécuter la tâche si la condition n'est pas remplie
                    return
                
            # Marquer la tâche comme en cours d'exécution et enregistrer le timestamp de démarrage
            self.tasks[name]['running'] = True
            self.task_start_time[name] = current_time
            
            # Enregistrer le temps de début
            start_time = time.time()
            time_since_last = start_time - self.last_execution[name]
            
            if self.last_execution[name] > 0 and name != 'short_term_trend_analysis':
                trading_logger.info(f"Exécution de {name} (dernier: il y a {time_since_last:.1f}s)")
            
            try:
                # Exécuter la fonction
                await func()
                
                # Mettre à jour le temps de dernière exécution
                self.last_execution[name] = time.time()
                
                # Calculer la durée d'exécution
                duration = time.time() - start_time
                
                # Avertir si l'exécution a pris plus de 80% de l'intervalle
                if duration > (interval * 0.8):
                    trading_logger.info(
                        f"⚠️ Tâche {name} a pris {duration:.2f}s (>80% de l'intervalle de {interval}s)"
                    )
                
            except Exception as e:
                error_logger.error(f"Erreur lors de l'exécution de la tâche {name}: {str(e)}")
            finally:
                # Marquer la tâche comme terminée et effacer le timestamp de démarrage
                self.tasks[name]['running'] = False
                self.task_start_time[name] = 0
        
        self.scheduler.add_job(
            func=wrapper,
            trigger=IntervalTrigger(seconds=interval),
            id=name,
            replace_existing=True
        )
        
        trading_logger.info(f"Tâche ajoutée: {name} (intervalle: {interval}s)")
    
    def start(self) -> None:
        """Démarre le planificateur"""
        if not self.scheduler.running:
            self.scheduler.start()
            trading_logger.info("Planificateur démarré")
    
    def stop(self) -> None:
        """Arrête le planificateur"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            trading_logger.info("Planificateur arrêté")
