"""Module pour l'export des logs vers des fichiers Excel

Ce module fournit des classes pour exporter les transactions, les logs de sécurité
et les données de simulation vers des fichiers Excel pour un suivi et une analyse faciles.
"""
import os
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional
from logger import trading_logger, error_logger

class ExcelLogger:
    """Classe de base pour les loggers Excel"""
    
    def __init__(self, file_path: str, sheet_name: str = "Sheet1"):
        """Initialise le logger Excel
        
        Args:
            file_path: Chemin vers le fichier Excel
            sheet_name: Nom de la feuille Excel
        """
        self.file_path = file_path
        self.sheet_name = sheet_name
        
        # Créer le répertoire parent si nécessaire
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Vérifier si le fichier existe déjà
        self.file_exists = os.path.exists(file_path)
        
        # Initialiser le DataFrame
        if self.file_exists:
            try:
                self.df = pd.read_excel(file_path, sheet_name=sheet_name)
            except Exception as e:
                error_logger.error(f"Erreur lors de la lecture du fichier Excel {file_path}: {str(e)}")
                self.df = pd.DataFrame()
        else:
            self.df = pd.DataFrame()
    
    def save(self) -> bool:
        """Sauvegarde le DataFrame dans le fichier Excel
        
        Returns:
            bool: True si la sauvegarde a réussi, False sinon
        """
        try:
            # Créer le répertoire parent si nécessaire
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            
            # Sauvegarder le DataFrame dans le fichier Excel
            self.df.to_excel(self.file_path, sheet_name=self.sheet_name, index=False)
            return True
        except Exception as e:
            error_logger.error(f"Erreur lors de la sauvegarde du fichier Excel {self.file_path}: {str(e)}")
            return False


class TradeLogger(ExcelLogger):
    """Logger pour les transactions de trading"""
    
    def __init__(self, file_path: str = "reports/trades_history.xlsx"):
        """Initialise le logger de transactions
        
        Args:
            file_path: Chemin vers le fichier Excel
        """
        super().__init__(file_path, "Trades")
        
        # Définir les colonnes si le DataFrame est vide
        if self.df.empty:
            self.df = pd.DataFrame(columns=[
                "Symbol", "Entry Price", "Exit Price", "Quantity", 
                "Gross Profit", "Fees", "Net Profit", "Profit Percentage",
                "Entry Date", "Entry Time", "Exit Date", "Exit Time",
                "Duration (min)"
            ])
    
    def log_trade(self, trade_data: Dict[str, Any]) -> bool:
        """Enregistre une transaction dans le fichier Excel
        
        Args:
            trade_data: Données de la transaction
            
        Returns:
            bool: True si l'enregistrement a réussi, False sinon
        """
        try:
            # Extraire les données de la transaction
            entry_time = trade_data.get("entry_time")
            exit_time = trade_data.get("exit_time")
            
            # Formater les dates et heures
            if isinstance(entry_time, datetime):
                entry_date = entry_time.strftime("%Y-%m-%d")
                entry_time_str = entry_time.strftime("%H:%M:%S")
            else:
                entry_date = "N/A"
                entry_time_str = "N/A"
            
            if isinstance(exit_time, datetime):
                exit_date = exit_time.strftime("%Y-%m-%d")
                exit_time_str = exit_time.strftime("%H:%M:%S")
            else:
                exit_date = "N/A"
                exit_time_str = "N/A"
            
            # Créer une nouvelle ligne pour le DataFrame
            new_row = pd.DataFrame([{
                "Symbol": trade_data.get("symbol", ""),
                "Entry Price": trade_data.get("entry_price", 0.0),
                "Exit Price": trade_data.get("exit_price", 0.0),
                "Quantity": trade_data.get("quantity", 0.0),
                "Gross Profit": trade_data.get("gross_profit", 0.0),
                "Fees": trade_data.get("fees", 0.0),
                "Net Profit": trade_data.get("profit", 0.0),
                "Profit Percentage": trade_data.get("profit_percentage", 0.0),
                "Entry Date": entry_date,
                "Entry Time": entry_time_str,
                "Exit Date": exit_date,
                "Exit Time": exit_time_str,
                "Duration (min)": trade_data.get("duration", 0.0)
            }])
            
            # Ajouter la nouvelle ligne au DataFrame
            self.df = pd.concat([self.df, new_row], ignore_index=True)
            
            # Sauvegarder le DataFrame dans le fichier Excel
            return self.save()
        except Exception as e:
            error_logger.error(f"Erreur lors de l'enregistrement de la transaction: {str(e)}")
            return False


class SecurityLogger(ExcelLogger):
    """Logger pour les alertes de sécurité"""
    
    def __init__(self, file_path: str = "reports/security_logs.xlsx"):
        """Initialise le logger de sécurité
        
        Args:
            file_path: Chemin vers le fichier Excel
        """
        super().__init__(file_path, "Security Alerts")
        
        # Définir les colonnes si le DataFrame est vide
        if self.df.empty:
            self.df = pd.DataFrame(columns=[
                "Date", "Time", "Level", "Type", "Message", 
                "Value", "Threshold", "Actions"
            ])
    
    def log_alert(self, alert_data: Dict[str, Any]) -> bool:
        """Enregistre une alerte de sécurité dans le fichier Excel
        
        Args:
            alert_data: Données de l'alerte
            
        Returns:
            bool: True si l'enregistrement a réussi, False sinon
        """
        try:
            # Obtenir l'horodatage actuel
            now = datetime.now()
            date_str = now.strftime("%Y-%m-%d")
            time_str = now.strftime("%H:%M:%S")
            
            # Créer une nouvelle ligne pour le DataFrame
            new_row = pd.DataFrame([{
                "Date": date_str,
                "Time": time_str,
                "Level": alert_data.get("level", "info"),
                "Type": alert_data.get("type", "unknown"),
                "Message": alert_data.get("message", ""),
                "Value": alert_data.get("value", ""),
                "Threshold": alert_data.get("threshold", ""),
                "Actions": alert_data.get("actions", "")
            }])
            
            # Ajouter la nouvelle ligne au DataFrame
            self.df = pd.concat([self.df, new_row], ignore_index=True)
            
            # Sauvegarder le DataFrame dans le fichier Excel
            return self.save()
        except Exception as e:
            error_logger.error(f"Erreur lors de l'enregistrement de l'alerte: {str(e)}")
            return False


class SimulationLogger(ExcelLogger):
    """Logger pour les données de simulation"""
    
    def __init__(self, file_path: str = "reports/simulation_results.xlsx"):
        """Initialise le logger de simulation
        
        Args:
            file_path: Chemin vers le fichier Excel
        """
        super().__init__(file_path, "Report")
        
        # Créer les DataFrames pour chaque feuille
        self.historical_data_df = pd.DataFrame()
        self.transactions_df = pd.DataFrame(columns=[
            "timestamp", "type", "price", "amount", "fee", "score", "trend"
        ])
        self.report_df = pd.DataFrame()
    
    def log_historical_data(self, data: pd.DataFrame) -> bool:
        """Enregistre les données historiques utilisées pour la simulation
        
        Args:
            data: DataFrame contenant les données historiques
            
        Returns:
            bool: True si l'enregistrement a réussi, False sinon
        """
        try:
            self.historical_data_df = data.copy()
            return True
        except Exception as e:
            error_logger.error(f"Erreur lors de l'enregistrement des données historiques: {str(e)}")
            return False
    
    def log_transaction(self, transaction: Dict[str, Any]) -> bool:
        """Enregistre une transaction effectuée pendant la simulation
        
        Args:
            transaction: Dictionnaire contenant les détails de la transaction
            
        Returns:
            bool: True si l'enregistrement a réussi, False sinon
        """
        try:
            # Créer une nouvelle ligne pour le DataFrame
            new_row = pd.DataFrame([transaction])
            
            # Ajouter la nouvelle ligne au DataFrame
            self.transactions_df = pd.concat([self.transactions_df, new_row], ignore_index=True)
            return True
        except Exception as e:
            error_logger.error(f"Erreur lors de l'enregistrement de la transaction: {str(e)}")
            return False
    
    def log_report(self, report: Dict[str, Any]) -> bool:
        """Enregistre le rapport final de la simulation
        
        Args:
            report: Dictionnaire contenant le rapport de simulation
            
        Returns:
            bool: True si l'enregistrement a réussi, False sinon
        """
        try:
            # Convertir le rapport en DataFrame
            self.report_df = pd.DataFrame([report])
            return True
        except Exception as e:
            error_logger.error(f"Erreur lors de l'enregistrement du rapport: {str(e)}")
            return False
    
    def save_all(self) -> bool:
        """Sauvegarde toutes les données dans le fichier Excel ou CSV
        
        Returns:
            bool: True si la sauvegarde a réussi, False sinon
        """
        try:
            print(f"Tentative de sauvegarde des données dans {self.file_path}")
            
            # Créer le répertoire parent si nécessaire
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            print(f"Répertoire créé: {os.path.dirname(self.file_path)}")
            
            # Vérifier les données à sauvegarder
            print(f"Données historiques: {len(self.historical_data_df)} lignes")
            print(f"Transactions: {len(self.transactions_df)} lignes")
            print(f"Rapport: {len(self.report_df)} lignes")
            
            # Essayer de sauvegarder en Excel
            try:
                # Essayer d'utiliser l'installation système d'openpyxl
                import sys
                import subprocess
                
                # Vérifier si openpyxl est disponible dans l'installation système
                try:
                    # Exécuter une commande Python pour vérifier si openpyxl est installé
                    result = subprocess.run(
                        [sys.executable, "-c", "import openpyxl; print('openpyxl available')"],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    if "openpyxl available" not in result.stdout:
                        raise ImportError("Le module openpyxl n'est pas disponible dans l'installation système")
                    
                    # Créer un writer Excel
                    print("Création du writer Excel...")
                    with pd.ExcelWriter(self.file_path, engine='openpyxl') as writer:
                        # Sauvegarder chaque DataFrame dans une feuille différente
                        if not self.historical_data_df.empty:
                            print("Sauvegarde des données historiques...")
                            self.historical_data_df.to_excel(writer, sheet_name="Historical Data", index=True)
                        
                        if not self.transactions_df.empty:
                            print("Sauvegarde des transactions...")
                            self.transactions_df.to_excel(writer, sheet_name="Transactions", index=False)
                        
                        if not self.report_df.empty:
                            print("Sauvegarde du rapport...")
                            self.report_df.to_excel(writer, sheet_name="Report", index=False)
                    
                    print(f"Données de simulation sauvegardées dans {self.file_path}")
                    return True
                except Exception as e:
                    raise ImportError(f"Erreur lors de la vérification d'openpyxl: {str(e)}")
            except Exception as excel_error:
                print(f"Erreur lors de la sauvegarde Excel: {str(excel_error)}")
                print("Sauvegarde en CSV à la place...")
                
                # Sauvegarder en CSV si Excel échoue
                base_path = os.path.splitext(self.file_path)[0]
                
                if not self.historical_data_df.empty:
                    historical_csv = f"{base_path}_historical_data.csv"
                    self.historical_data_df.to_csv(historical_csv)
                    print(f"Données historiques sauvegardées dans {historical_csv}")
                
                if not self.transactions_df.empty:
                    transactions_csv = f"{base_path}_transactions.csv"
                    self.transactions_df.to_csv(transactions_csv)
                    print(f"Transactions sauvegardées dans {transactions_csv}")
                
                if not self.report_df.empty:
                    report_csv = f"{base_path}_report.csv"
                    self.report_df.to_csv(report_csv)
                    print(f"Rapport sauvegardé dans {report_csv}")
                
                print("Données sauvegardées en CSV avec succès")
                return True
        except Exception as e:
            print(f"ERREUR lors de la sauvegarde des données: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return False


# Instances globales pour un accès facile
trade_logger = TradeLogger()
security_logger = SecurityLogger()
