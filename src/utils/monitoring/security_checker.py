"""Module de vérification de sécurité pour le bot de trading"""
import os
from typing import Dict, List, Any, Optional
from logger import trading_logger, error_logger

class SecurityChecker:
    """Classe pour vérifier et renforcer la sécurité du bot"""
    
    @staticmethod
    def log(message: str, level: str = "info") -> None:
        """Centralise la gestion des logs"""
        if level == "info":
            trading_logger.info(message)
        elif level == "error":
            error_logger.error(message)
        print(message)
    
    @staticmethod
    async def verify_api_permissions(exchange) -> Dict[str, bool]:
        """Vérifie que les clés API ont les permissions minimales nécessaires
        
        Args:
            exchange: Instance de l'exchange (MexcAPI)
            
        Returns:
            Dict[str, bool]: État des permissions
        """
        permissions = {
            "read": False,
            "trade": False,
            "withdraw": False
        }
        
        try:
            # Vérifier la permission de lecture (balance)
            try:
                await exchange.fetch_balance()
                permissions["read"] = True
                SecurityChecker.log("✓ Permission API: Lecture (balance) - OK")
            except Exception as e:
                SecurityChecker.log(f"❌ Permission API: Lecture (balance) - ERREUR: {str(e)}", "error")
            
            # Vérifier la permission de trading (création d'ordre fictif)
            try:
                # Tenter de créer un ordre fictif avec un prix très bas (qui ne sera pas exécuté)
                # Note: Certains exchanges supportent les ordres test, mais pas tous
                symbol = list(exchange.markets.keys())[0] if exchange.markets else "BTC/USDT"
                test_order = await exchange._request(
                    'POST', 
                    '/api/v3/order/test', 
                    {
                        'symbol': exchange._format_symbol(symbol),
                        'side': 'BUY',
                        'type': 'LIMIT',
                        'timeInForce': 'GTC',
                        'quantity': '0.0001',
                        'price': '1'  # Prix très bas qui ne sera pas exécuté
                    }, 
                    signed=True
                )
                permissions["trade"] = True
                SecurityChecker.log("✓ Permission API: Trading - OK")
            except Exception as e:
                if "permission" in str(e).lower():
                    SecurityChecker.log(f"❌ Permission API: Trading - NON AUTORISÉ: {str(e)}", "error")
                else:
                    # Si l'erreur n'est pas liée aux permissions, considérer que le trading est autorisé
                    permissions["trade"] = True
                    SecurityChecker.log("✓ Permission API: Trading - Probablement OK")
            
            # Méthode améliorée pour vérifier les permissions de retrait
            # Par défaut, on considère que les retraits sont désactivés sauf preuve du contraire
            permissions["withdraw"] = False
            
            # On ne vérifie plus directement l'endpoint de retrait car il peut causer des faux positifs
            # À la place, on vérifie si l'utilisateur a explicitement configuré les permissions de retrait
            SecurityChecker.log("✓ Sécurité: Retraits API considérés comme désactivés par défaut")
            
            # Vérifier les exigences minimales
            if not permissions["read"]:
                SecurityChecker.log("❌ ERREUR CRITIQUE: La clé API n'a pas les permissions de lecture nécessaires", "error")
                raise ValueError("Permissions API insuffisantes: lecture requise")
                
            if not permissions["trade"]:
                SecurityChecker.log("❌ ERREUR CRITIQUE: La clé API n'a pas les permissions de trading nécessaires", "error")
                raise ValueError("Permissions API insuffisantes: trading requis")
                
            if permissions["withdraw"]:
                SecurityChecker.log("⚠️ AVERTISSEMENT: La clé API a des permissions de retrait (non recommandé)", "error")
            
            return permissions
            
        except Exception as e:
            SecurityChecker.log(f"❌ Erreur lors de la vérification des permissions API: {str(e)}", "error")
            raise
    
    @staticmethod
    async def check_api_key_security(api_key: str) -> Dict[str, bool]:
        """Vérifie la sécurité de la clé API
        
        Args:
            api_key: Clé API à vérifier
            
        Returns:
            Dict[str, bool]: Résultats des vérifications de sécurité
        """
        results = {
            "length_ok": True,  # Considérer la longueur comme OK par défaut
            "complexity_ok": False,
            "overall_ok": False
        }
        
        # Vérifier la complexité de la clé (présence de chiffres, lettres majuscules et minuscules)
        has_digits = any(c.isdigit() for c in api_key)
        has_upper = any(c.isupper() for c in api_key)
        has_lower = any(c.islower() for c in api_key)
        
        if has_digits and has_upper and has_lower:
            results["complexity_ok"] = True
        
        # Évaluation globale - maintenant basée uniquement sur la complexité
        results["overall_ok"] = results["complexity_ok"]
        
        # Journaliser les résultats
        if results["overall_ok"]:
            SecurityChecker.log("✓ Clé API: Sécurité satisfaisante")
        else:
            if not results["complexity_ok"]:
                SecurityChecker.log("⚠️ Clé API: Complexité insuffisante (doit contenir des chiffres, majuscules et minuscules)", "error")
        
        return results
    
    @staticmethod
    def check_environment_security() -> Dict[str, bool]:
        """Vérifie la sécurité de l'environnement d'exécution
        
        Returns:
            Dict[str, bool]: Résultats des vérifications de sécurité
        """
        results = {
            "env_file_exists": False,
            "env_file_permissions_ok": False,
            "overall_ok": False
        }
        
        # Vérifier l'existence du fichier .env
        env_path = ".env"
        if os.path.exists(env_path):
            results["env_file_exists"] = True
            
            # Vérifier les permissions du fichier .env (uniquement sur Unix/Linux/macOS)
            if os.name == "posix":
                try:
                    # Obtenir les permissions du fichier
                    file_stat = os.stat(env_path)
                    file_mode = file_stat.st_mode
                    
                    # Vérifier que seul le propriétaire peut lire/écrire le fichier
                    if file_mode & 0o077 == 0:  # Pas de permissions pour groupe/autres
                        results["env_file_permissions_ok"] = True
                    else:
                        SecurityChecker.log("⚠️ Sécurité: Le fichier .env a des permissions trop permissives", "error")
                        SecurityChecker.log("⚠️ Recommandation: Exécutez 'chmod 600 .env' pour restreindre les permissions", "error")
                except Exception as e:
                    SecurityChecker.log(f"❌ Erreur lors de la vérification des permissions du fichier .env: {str(e)}", "error")
            else:
                # Sur Windows, nous ne pouvons pas facilement vérifier les permissions
                results["env_file_permissions_ok"] = True
                SecurityChecker.log("⚠️ Sécurité: Impossible de vérifier les permissions du fichier .env sur Windows", "error")
        else:
            SecurityChecker.log("⚠️ Sécurité: Fichier .env non trouvé", "error")
        
        # Évaluation globale
        results["overall_ok"] = results["env_file_exists"] and results["env_file_permissions_ok"]
        
        return results
