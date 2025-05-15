"""Module de surveillance des activités pour détecter les comportements anormaux"""
import time
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from logger import trading_logger, error_logger
from .excel_logger import security_logger

class ActivityMonitor:
    """Classe pour surveiller et alerter sur les activités suspectes"""
    
    def __init__(self, config_path: str = "security/activity_monitor.json"):
        """Initialise le moniteur d'activité
        
        Args:
            config_path: Chemin vers le fichier de configuration
        """
        self.config_path = config_path
        self.activity_log_path = "security/activity_log.json"
        self.alert_log_path = "security/alerts.log"
        
        # Créer les répertoires si nécessaires
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.activity_log_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.alert_log_path), exist_ok=True)
        
        # Charger ou créer la configuration
        self.config = self._load_or_create_config()
        
        # Charger ou créer le journal d'activité
        self.activity_log = self._load_or_create_activity_log()
        
        # Initialiser les compteurs d'activité pour la session actuelle
        self.session_activity = {
            "trades": 0,
            "orders": 0,
            "api_calls": 0,
            "errors": 0,
            "start_time": datetime.now().isoformat()
        }
        
        trading_logger.info("Moniteur d'activité initialisé")
    
    def _load_or_create_config(self) -> Dict[str, Any]:
        """Charge ou crée le fichier de configuration
        
        Returns:
            Dict[str, Any]: Configuration du moniteur
        """
        default_config = {
            "thresholds": {
                "max_trades_per_hour": 10,
                "max_orders_per_hour": 20,
                "max_api_calls_per_minute": 60,
                "max_errors_per_hour": 5,
                "unusual_trade_size_multiplier": 3.0,
                "unusual_price_deviation_percent": 5.0
            },
            "monitoring": {
                "enabled": True,
                "log_all_activities": True,
                "alert_on_threshold_breach": True
            },
            "last_updated": datetime.now().isoformat()
        }
        
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    return config
            else:
                # Créer le fichier de configuration par défaut
                with open(self.config_path, 'w') as f:
                    json.dump(default_config, f, indent=2)
                return default_config
        except Exception as e:
            error_logger.error(f"Erreur lors du chargement de la configuration du moniteur: {str(e)}")
            return default_config
    
    def _load_or_create_activity_log(self) -> Dict[str, Any]:
        """Charge ou crée le journal d'activité
        
        Returns:
            Dict[str, Any]: Journal d'activité
        """
        default_log = {
            "daily_summary": {},
            "hourly_counts": {},
            "recent_trades": [],
            "recent_orders": [],
            "recent_errors": [],
            "last_updated": datetime.now().isoformat()
        }
        
        try:
            if os.path.exists(self.activity_log_path):
                with open(self.activity_log_path, 'r') as f:
                    log = json.load(f)
                    return log
            else:
                # Créer le journal d'activité par défaut
                with open(self.activity_log_path, 'w') as f:
                    json.dump(default_log, f, indent=2)
                return default_log
        except Exception as e:
            error_logger.error(f"Erreur lors du chargement du journal d'activité: {str(e)}")
            return default_log
    
    def _save_activity_log(self) -> None:
        """Sauvegarde le journal d'activité"""
        try:
            self.activity_log["last_updated"] = datetime.now().isoformat()
            with open(self.activity_log_path, 'w') as f:
                json.dump(self.activity_log, f, indent=2)
        except Exception as e:
            error_logger.error(f"Erreur lors de la sauvegarde du journal d'activité: {str(e)}")
    
    def _log_alert(self, message: str, level: str = "warning") -> None:
        """Enregistre une alerte dans le journal d'alertes
        
        Args:
            message: Message d'alerte
            level: Niveau d'alerte (info, warning, error, critical)
        """
        try:
            timestamp = datetime.now().isoformat()
            with open(self.alert_log_path, 'a') as f:
                f.write(f"[{timestamp}] [{level.upper()}] {message}\n")
            
            # Journaliser également dans les logs du bot
            if level == "info":
                trading_logger.info(f"ALERTE: {message}")
            else:
                error_logger.error(f"ALERTE {level.upper()}: {message}")
            
            # Enregistrer l'alerte dans le fichier Excel
            alert_data = {
                "level": level,
                "type": "security_alert",
                "message": message,
                "value": "",
                "threshold": "",
                "actions": ""
            }
            security_logger.log_alert(alert_data)
        except Exception as e:
            error_logger.error(f"Erreur lors de l'enregistrement de l'alerte: {str(e)}")
    
    def log_api_call(self, endpoint: str, method: str, params: Dict[str, Any]) -> None:
        """Enregistre un appel API
        
        Args:
            endpoint: Endpoint API appelé
            method: Méthode HTTP (GET, POST, etc.)
            params: Paramètres de la requête (sensibles masqués)
        """
        if not self.config["monitoring"]["enabled"]:
            return
        
        # Incrémenter le compteur d'appels API
        self.session_activity["api_calls"] += 1
        
        # Vérifier le seuil d'appels API par minute
        current_hour = datetime.now().strftime("%Y-%m-%d %H:00")
        current_minute = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # Initialiser les compteurs si nécessaire
        if current_hour not in self.activity_log["hourly_counts"]:
            self.activity_log["hourly_counts"][current_hour] = {
                "api_calls": 0,
                "trades": 0,
                "orders": 0,
                "errors": 0,
                "minutes": {}
            }
        
        if current_minute not in self.activity_log["hourly_counts"][current_hour]["minutes"]:
            self.activity_log["hourly_counts"][current_hour]["minutes"][current_minute] = {
                "api_calls": 0
            }
        
        # Incrémenter les compteurs
        self.activity_log["hourly_counts"][current_hour]["api_calls"] += 1
        self.activity_log["hourly_counts"][current_hour]["minutes"][current_minute]["api_calls"] += 1
        
        # Vérifier le seuil d'appels API par minute
        minute_calls = self.activity_log["hourly_counts"][current_hour]["minutes"][current_minute]["api_calls"]
        if minute_calls > self.config["thresholds"]["max_api_calls_per_minute"]:
            self._log_alert(
                f"Seuil d'appels API dépassé: {minute_calls} appels dans la dernière minute " +
                f"(seuil: {self.config['thresholds']['max_api_calls_per_minute']})",
                "warning"
            )
        
        # Enregistrer l'activité si la journalisation complète est activée
        if self.config["monitoring"]["log_all_activities"]:
            # Masquer les informations sensibles
            safe_params = self._sanitize_params(params)
            
            # Enregistrer l'appel API (mais ne pas stocker tous les appels pour économiser de l'espace)
            # Nous pourrions implémenter une rotation des logs si nécessaire
            pass
        
        # Sauvegarder le journal d'activité périodiquement (pas à chaque appel pour des raisons de performance)
        if self.session_activity["api_calls"] % 100 == 0:
            self._save_activity_log()
    
    def _sanitize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Masque les informations sensibles dans les paramètres
        
        Args:
            params: Paramètres de la requête
            
        Returns:
            Dict[str, Any]: Paramètres avec les informations sensibles masquées
        """
        if not params:
            return {}
        
        # Créer une copie pour ne pas modifier l'original
        safe_params = params.copy()
        
        # Liste des clés sensibles à masquer
        sensitive_keys = ["signature", "apiKey", "secret", "key", "password", "token"]
        
        # Masquer les valeurs des clés sensibles
        for key in safe_params:
            if key.lower() in [k.lower() for k in sensitive_keys]:
                safe_params[key] = "********"
        
        return safe_params
    
    def log_order(self, order_data: Dict[str, Any]) -> None:
        """Enregistre un ordre
        
        Args:
            order_data: Données de l'ordre
        """
        if not self.config["monitoring"]["enabled"]:
            return
        
        # Incrémenter le compteur d'ordres
        self.session_activity["orders"] += 1
        
        # Vérifier le seuil d'ordres par heure
        current_hour = datetime.now().strftime("%Y-%m-%d %H:00")
        
        # Initialiser les compteurs si nécessaire
        if current_hour not in self.activity_log["hourly_counts"]:
            self.activity_log["hourly_counts"][current_hour] = {
                "api_calls": 0,
                "trades": 0,
                "orders": 0,
                "errors": 0,
                "minutes": {}
            }
        
        # Incrémenter le compteur d'ordres
        self.activity_log["hourly_counts"][current_hour]["orders"] += 1
        
        # Vérifier le seuil d'ordres par heure
        hour_orders = self.activity_log["hourly_counts"][current_hour]["orders"]
        if hour_orders > self.config["thresholds"]["max_orders_per_hour"]:
            self._log_alert(
                f"Seuil d'ordres dépassé: {hour_orders} ordres dans la dernière heure " +
                f"(seuil: {self.config['thresholds']['max_orders_per_hour']})",
                "warning"
            )
        
        # Enregistrer l'ordre dans les ordres récents
        safe_order = self._sanitize_order(order_data)
        self.activity_log["recent_orders"].append({
            "timestamp": datetime.now().isoformat(),
            "order": safe_order
        })
        
        # Limiter la taille de la liste des ordres récents
        if len(self.activity_log["recent_orders"]) > 100:
            self.activity_log["recent_orders"] = self.activity_log["recent_orders"][-100:]
        
        # Sauvegarder le journal d'activité
        self._save_activity_log()
    
    def _sanitize_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Masque les informations sensibles dans les données d'ordre
        
        Args:
            order_data: Données de l'ordre
            
        Returns:
            Dict[str, Any]: Données d'ordre avec les informations sensibles masquées
        """
        if not order_data:
            return {}
        
        # Créer une copie pour ne pas modifier l'original
        safe_order = order_data.copy()
        
        # Masquer les informations sensibles dans l'objet info
        if "info" in safe_order:
            safe_order["info"] = self._sanitize_params(safe_order["info"])
        
        return safe_order
    
    def log_trade(self, trade_data: Dict[str, Any]) -> None:
        """Enregistre un trade
        
        Args:
            trade_data: Données du trade
        """
        if not self.config["monitoring"]["enabled"]:
            return
        
        # Incrémenter le compteur de trades
        self.session_activity["trades"] += 1
        
        # Vérifier le seuil de trades par heure
        current_hour = datetime.now().strftime("%Y-%m-%d %H:00")
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # Initialiser les compteurs si nécessaire
        if current_hour not in self.activity_log["hourly_counts"]:
            self.activity_log["hourly_counts"][current_hour] = {
                "api_calls": 0,
                "trades": 0,
                "orders": 0,
                "errors": 0,
                "minutes": {}
            }
        
        if current_date not in self.activity_log["daily_summary"]:
            self.activity_log["daily_summary"][current_date] = {
                "trades": 0,
                "volume": 0.0,
                "profit": 0.0
            }
        
        # Incrémenter les compteurs
        self.activity_log["hourly_counts"][current_hour]["trades"] += 1
        self.activity_log["daily_summary"][current_date]["trades"] += 1
        
        # Mettre à jour les statistiques quotidiennes
        if "cost" in trade_data:
            self.activity_log["daily_summary"][current_date]["volume"] += float(trade_data["cost"])
        
        if "profit" in trade_data:
            self.activity_log["daily_summary"][current_date]["profit"] += float(trade_data["profit"])
        
        # Vérifier le seuil de trades par heure
        hour_trades = self.activity_log["hourly_counts"][current_hour]["trades"]
        if hour_trades > self.config["thresholds"]["max_trades_per_hour"]:
            self._log_alert(
                f"Seuil de trades dépassé: {hour_trades} trades dans la dernière heure " +
                f"(seuil: {self.config['thresholds']['max_trades_per_hour']})",
                "warning"
            )
        
        # Vérifier les anomalies de taille de trade
        if "cost" in trade_data and "symbol" in trade_data:
            # Calculer la taille moyenne des trades pour ce symbole
            symbol_trades = [
                t["trade"] for t in self.activity_log["recent_trades"]
                if t["trade"].get("symbol") == trade_data["symbol"] and "cost" in t["trade"]
            ]
            
            if symbol_trades:
                avg_cost = sum(float(t["cost"]) for t in symbol_trades) / len(symbol_trades)
                
                # Vérifier si la taille du trade est anormalement grande
                if float(trade_data["cost"]) > avg_cost * self.config["thresholds"]["unusual_trade_size_multiplier"]:
                    self._log_alert(
                        f"Taille de trade anormale pour {trade_data['symbol']}: " +
                        f"{float(trade_data['cost']):.2f} (moyenne: {avg_cost:.2f}, " +
                        f"multiplicateur: {self.config['thresholds']['unusual_trade_size_multiplier']})",
                        "warning"
                    )
        
        # Enregistrer le trade dans les trades récents
        safe_trade = self._sanitize_trade(trade_data)
        self.activity_log["recent_trades"].append({
            "timestamp": datetime.now().isoformat(),
            "trade": safe_trade
        })
        
        # Limiter la taille de la liste des trades récents
        if len(self.activity_log["recent_trades"]) > 100:
            self.activity_log["recent_trades"] = self.activity_log["recent_trades"][-100:]
        
        # Sauvegarder le journal d'activité
        self._save_activity_log()
    
    def _sanitize_trade(self, trade_data: Dict[str, Any]) -> Dict[str, Any]:
        """Masque les informations sensibles dans les données de trade
        
        Args:
            trade_data: Données du trade
            
        Returns:
            Dict[str, Any]: Données de trade avec les informations sensibles masquées
        """
        if not trade_data:
            return {}
        
        # Créer une copie pour ne pas modifier l'original
        safe_trade = trade_data.copy()
        
        # Masquer les informations sensibles dans l'objet info
        if "info" in safe_trade:
            safe_trade["info"] = self._sanitize_params(safe_trade["info"])
        
        return safe_trade
    
    def log_error(self, error_message: str, error_type: str = "general") -> None:
        """Enregistre une erreur
        
        Args:
            error_message: Message d'erreur
            error_type: Type d'erreur (api, network, validation, etc.)
        """
        if not self.config["monitoring"]["enabled"]:
            return
        
        # Incrémenter le compteur d'erreurs
        self.session_activity["errors"] += 1
        
        # Vérifier le seuil d'erreurs par heure
        current_hour = datetime.now().strftime("%Y-%m-%d %H:00")
        
        # Initialiser les compteurs si nécessaire
        if current_hour not in self.activity_log["hourly_counts"]:
            self.activity_log["hourly_counts"][current_hour] = {
                "api_calls": 0,
                "trades": 0,
                "orders": 0,
                "errors": 0,
                "minutes": {}
            }
        
        # Incrémenter le compteur d'erreurs
        self.activity_log["hourly_counts"][current_hour]["errors"] += 1
        
        # Vérifier le seuil d'erreurs par heure
        hour_errors = self.activity_log["hourly_counts"][current_hour]["errors"]
        if hour_errors > self.config["thresholds"]["max_errors_per_hour"]:
            self._log_alert(
                f"Seuil d'erreurs dépassé: {hour_errors} erreurs dans la dernière heure " +
                f"(seuil: {self.config['thresholds']['max_errors_per_hour']})",
                "warning"
            )
        
        # Enregistrer l'erreur dans les erreurs récentes
        self.activity_log["recent_errors"].append({
            "timestamp": datetime.now().isoformat(),
            "type": error_type,
            "message": error_message
        })
        
        # Limiter la taille de la liste des erreurs récentes
        if len(self.activity_log["recent_errors"]) > 100:
            self.activity_log["recent_errors"] = self.activity_log["recent_errors"][-100:]
        
        # Sauvegarder le journal d'activité
        self._save_activity_log()
    
    def get_activity_summary(self) -> Dict[str, Any]:
        """Obtient un résumé de l'activité
        
        Returns:
            Dict[str, Any]: Résumé de l'activité
        """
        # Calculer la durée de la session
        start_time = datetime.fromisoformat(self.session_activity["start_time"])
        duration = datetime.now() - start_time
        
        # Obtenir les statistiques de la journée
        current_date = datetime.now().strftime("%Y-%m-%d")
        daily_stats = self.activity_log["daily_summary"].get(current_date, {
            "trades": 0,
            "volume": 0.0,
            "profit": 0.0
        })
        
        # Obtenir les statistiques de l'heure
        current_hour = datetime.now().strftime("%Y-%m-%d %H:00")
        hourly_stats = self.activity_log["hourly_counts"].get(current_hour, {
            "api_calls": 0,
            "trades": 0,
            "orders": 0,
            "errors": 0
        })
        
        # Créer le résumé
        summary = {
            "session": {
                "duration": str(duration),
                "api_calls": self.session_activity["api_calls"],
                "trades": self.session_activity["trades"],
                "orders": self.session_activity["orders"],
                "errors": self.session_activity["errors"]
            },
            "hourly": {
                "api_calls": hourly_stats.get("api_calls", 0),
                "trades": hourly_stats.get("trades", 0),
                "orders": hourly_stats.get("orders", 0),
                "errors": hourly_stats.get("errors", 0)
            },
            "daily": {
                "trades": daily_stats.get("trades", 0),
                "volume": daily_stats.get("volume", 0.0),
                "profit": daily_stats.get("profit", 0.0)
            },
            "recent_errors": self.activity_log["recent_errors"][-5:] if self.activity_log["recent_errors"] else []
        }
        
        return summary
    
    def check_for_anomalies(self) -> List[Dict[str, Any]]:
        """Vérifie les anomalies dans l'activité
        
        Returns:
            List[Dict[str, Any]]: Liste des anomalies détectées
        """
        anomalies = []
        
        # Vérifier les anomalies de volume de trades
        current_hour = datetime.now().strftime("%Y-%m-%d %H:00")
        hourly_stats = self.activity_log["hourly_counts"].get(current_hour, {})
        
        # Vérifier le nombre de trades par heure
        hour_trades = hourly_stats.get("trades", 0)
        if hour_trades > self.config["thresholds"]["max_trades_per_hour"]:
            anomaly = {
                "type": "high_trade_volume",
                "message": f"Volume de trades élevé: {hour_trades} trades dans la dernière heure",
                "threshold": self.config["thresholds"]["max_trades_per_hour"],
                "value": hour_trades
            }
            anomalies.append(anomaly)
            
            # Enregistrer l'anomalie dans le fichier Excel
            alert_data = {
                "level": "warning",
                "type": anomaly["type"],
                "message": anomaly["message"],
                "value": str(anomaly["value"]),
                "threshold": str(anomaly["threshold"]),
                "actions": ""
            }
            security_logger.log_alert(alert_data)
        
        # Vérifier le nombre d'ordres par heure
        hour_orders = hourly_stats.get("orders", 0)
        if hour_orders > self.config["thresholds"]["max_orders_per_hour"]:
            anomaly = {
                "type": "high_order_volume",
                "message": f"Volume d'ordres élevé: {hour_orders} ordres dans la dernière heure",
                "threshold": self.config["thresholds"]["max_orders_per_hour"],
                "value": hour_orders
            }
            anomalies.append(anomaly)
            
            # Enregistrer l'anomalie dans le fichier Excel
            alert_data = {
                "level": "warning",
                "type": anomaly["type"],
                "message": anomaly["message"],
                "value": str(anomaly["value"]),
                "threshold": str(anomaly["threshold"]),
                "actions": ""
            }
            security_logger.log_alert(alert_data)
        
        # Vérifier le nombre d'erreurs par heure
        hour_errors = hourly_stats.get("errors", 0)
        if hour_errors > self.config["thresholds"]["max_errors_per_hour"]:
            anomaly = {
                "type": "high_error_rate",
                "message": f"Taux d'erreurs élevé: {hour_errors} erreurs dans la dernière heure",
                "threshold": self.config["thresholds"]["max_errors_per_hour"],
                "value": hour_errors
            }
            anomalies.append(anomaly)
            
            # Enregistrer l'anomalie dans le fichier Excel
            alert_data = {
                "level": "warning",
                "type": anomaly["type"],
                "message": anomaly["message"],
                "value": str(anomaly["value"]),
                "threshold": str(anomaly["threshold"]),
                "actions": ""
            }
            security_logger.log_alert(alert_data)
        
        # Vérifier les anomalies de taille de trade
        if self.activity_log["recent_trades"]:
            # Regrouper les trades par symbole
            trades_by_symbol = {}
            for trade_entry in self.activity_log["recent_trades"]:
                trade = trade_entry["trade"]
                symbol = trade.get("symbol")
                if symbol and "cost" in trade:
                    if symbol not in trades_by_symbol:
                        trades_by_symbol[symbol] = []
                    trades_by_symbol[symbol].append(float(trade["cost"]))
            
            # Vérifier les anomalies pour chaque symbole
            for symbol, costs in trades_by_symbol.items():
                if len(costs) >= 3:  # Au moins 3 trades pour calculer une moyenne significative
                    avg_cost = sum(costs) / len(costs)
                    for cost in costs:
                        if cost > avg_cost * self.config["thresholds"]["unusual_trade_size_multiplier"]:
                            anomaly = {
                                "type": "unusual_trade_size",
                                "message": f"Taille de trade anormale pour {symbol}: {cost:.2f} (moyenne: {avg_cost:.2f})",
                                "threshold": avg_cost * self.config["thresholds"]["unusual_trade_size_multiplier"],
                                "value": cost,
                                "symbol": symbol
                            }
                            anomalies.append(anomaly)
                            
                            # Enregistrer l'anomalie dans le fichier Excel
                            alert_data = {
                                "level": "warning",
                                "type": anomaly["type"],
                                "message": anomaly["message"],
                                "value": str(anomaly["value"]),
                                "threshold": str(anomaly["threshold"]),
                                "actions": ""
                            }
                            security_logger.log_alert(alert_data)
        
        return anomalies
