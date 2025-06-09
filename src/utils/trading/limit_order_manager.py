"""Module de gestion des ordres limites avec timeout automatique"""
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List, Callable, Tuple, Union
from logger import trading_logger, error_logger

class LimitOrderManager:
    """Gestionnaire d'ordres limites avec annulation automatique après timeout"""
    
    def __init__(self, exchange):
        """Initialise le gestionnaire d'ordres limites
        
        Args:
            exchange: Instance de l'API d'échange pour exécuter les ordres
        """
        self.exchange = exchange
        self.active_orders: Dict[str, Dict[str, Any]] = {}  # {order_id: {timestamp, symbol, type, ...}}
        self.order_callbacks: Dict[str, Callable] = {}  # callbacks à exécuter après annulation
        self.fill_callbacks: Dict[str, Callable] = {}  # callbacks à exécuter quand l'ordre est rempli
        self.order_attempts: Dict[str, int] = {}  # compteur de tentatives par symbol pour les ordres d'achat
        self.sell_attempts: Dict[str, int] = {}  # compteur de tentatives par symbol pour les ordres de vente
        self.checking_task = None
        self.last_order_check = {}  # {order_id: timestamp} pour limiter les vérifications
    
    async def start_order_checker(self):
        """Démarre la tâche de vérification des ordres actifs"""
        if self.checking_task is None or self.checking_task.done():
            self.checking_task = asyncio.create_task(self._check_orders_loop())
            trading_logger.info("Vérification des ordres limites démarrée")
    
    async def stop_order_checker(self):
        """Arrête la tâche de vérification des ordres actifs"""
        if self.checking_task and not self.checking_task.done():
            self.checking_task.cancel()
            try:
                await self.checking_task
            except asyncio.CancelledError:
                pass
            self.checking_task = None
            trading_logger.info("Vérification des ordres limites arrêtée")
    
    async def _check_orders_loop(self):
        """Boucle de vérification périodique des ordres actifs"""
        try:
            while True:
                await self._check_orders()
                await self._check_filled_orders()  # Vérifier aussi les ordres remplis
                await asyncio.sleep(1)  # Vérifier toutes les secondes
        except asyncio.CancelledError:
            trading_logger.info("Boucle de vérification des ordres annulée")
            raise
        except Exception as e:
            error_logger.error(f"Erreur dans la boucle de vérification des ordres: {str(e)}")
    
    async def _check_filled_orders(self):
        """Vérifie si des ordres actifs ont été remplis et exécute les callbacks appropriés"""
        current_time = time.time()
        orders_to_check = []
        
        # Ne pas vérifier trop souvent le même ordre pour éviter de surcharger l'API
        for order_id in list(self.active_orders.keys()):
            # Vérifier au maximum une fois toutes les 2 secondes
            last_check = self.last_order_check.get(order_id, 0)
            if current_time - last_check >= 2:
                orders_to_check.append(order_id)
                self.last_order_check[order_id] = current_time
        
        # Si aucun ordre à vérifier, sortir
        if not orders_to_check:
            return
        
        # Ordres à traiter et à supprimer
        filled_orders = []
        
        # Vérifier chaque ordre
        for order_id in orders_to_check:
            if order_id not in self.active_orders:
                continue
                
            order_info = self.active_orders[order_id]
            symbol = order_info['symbol']
            
            try:
                # Récupérer le statut de l'ordre depuis l'exchange
                order_status = await self.exchange.fetch_order(order_id, symbol)
                
                # Vérifier si l'ordre est rempli
                if order_status.get('status') == 'closed' or order_status.get('filled') == order_status.get('amount'):
                    trading_logger.info(f"✅ Ordre {order_id} pour {symbol} rempli avec succès")
                    filled_orders.append((order_id, order_status))
            except Exception as e:
                error_logger.error(f"Erreur lors de la vérification de l'ordre {order_id}: {str(e)}")
        
        # Traiter les ordres remplis
        for order_id, order_status in filled_orders:
            try:
                # Supprimer l'ordre des ordres actifs
                if order_id in self.active_orders:
                    del self.active_orders[order_id]
                    
                # Exécuter le callback si présent
                if order_id in self.fill_callbacks:
                    callback = self.fill_callbacks[order_id]
                    await callback(order_status)
                    del self.fill_callbacks[order_id]
                    
                # Supprimer le timestamp de dernier check
                if order_id in self.last_order_check:
                    del self.last_order_check[order_id]
                    
            except Exception as e:
                error_logger.error(f"Erreur lors du traitement de l'ordre rempli {order_id}: {str(e)}")
    
    async def _check_orders(self):
        """Vérifie les ordres actifs et annule ceux qui ont dépassé leur timeout"""
        current_time = time.time()
        orders_to_remove = []
        callbacks_to_execute = []

        for order_id, order_info in list(self.active_orders.items()):
            if current_time - order_info['timestamp'] > order_info['timeout']:
                try:
                    order_status = await self.exchange.fetch_order(order_id, order_info['symbol'])
                    status = order_status.get('status')
                    # Si l'ordre est déjà rempli
                    if status == 'closed' or order_status.get('filled') == order_status.get('amount'):
                        trading_logger.info(f"✅ Ordre {order_id} pour {order_info['symbol']} rempli avec succès")
                        orders_to_remove.append(order_id)
                        if order_id in self.fill_callbacks:
                            await self.fill_callbacks[order_id](order_status)
                            del self.fill_callbacks[order_id]
                        continue
                    # Si l'ordre est déjà annulé
                    if status == 'canceled':
                        trading_logger.info(f"⏰ Ordre {order_id} pour {order_info['symbol']} déjà annulé, exécution du callback timeout")
                        orders_to_remove.append(order_id)
                        if order_id in self.order_callbacks:
                            await self.order_callbacks[order_id]()
                            del self.order_callbacks[order_id]
                        continue
                    # Sinon, annulation automatique en timeout
                    trading_logger.info(f"""
=== TIMEOUT ORDRE LIMITE ===
   ID: {order_id}
   Symbole: {order_info['symbol']}
   Type: {order_info['type']}
   Prix: {order_info['price']:.8f}
   Durée: {current_time - order_info['timestamp']:.1f}s > {order_info['timeout']}s
   Action: Annulation automatique
""")
                    await self.exchange.cancel_order(order_id, order_info['symbol'])
                    orders_to_remove.append(order_id)
                    if order_id in self.order_callbacks:
                        callbacks_to_execute.append((order_id, self.order_callbacks[order_id]))
                except Exception as e:
                    error_message = str(e)
                    if "code\":-2011" in error_message:
                        trading_logger.info(f"Ordre {order_id} pour {order_info['symbol']} annulé (code -2011) => timeout")
                        if order_id in self.order_callbacks:
                            callbacks_to_execute.append((order_id, self.order_callbacks[order_id]))
                    else:
                        error_logger.error(f"Erreur lors de l'annulation de l'ordre {order_id} pour {order_info['symbol']}: {error_message}")
                        if order_id in self.order_callbacks:
                            callbacks_to_execute.append((order_id, self.order_callbacks[order_id]))
                    orders_to_remove.append(order_id)

        # Supprimer les ordres du suivi
        for oid in orders_to_remove:
            if oid in self.active_orders:
                del self.active_orders[oid]
        # Exécuter les callbacks timeout pour notifier l’annulation
        for order_id, callback in callbacks_to_execute:
            try:
                result = callback()
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                error_logger.error(f"Erreur callback timeout dans _check_orders pour {order_id}: {e}")
    
    async def create_limit_buy_order(self, symbol: str, amount: float, price: float, timeout: int = 7,
                                    on_timeout_callback: Optional[Callable] = None,
                                    on_fill_callback: Optional[Callable] = None,
                                    attempt: int = 1, max_attempts: int = 3) -> Optional[Dict[str, Any]]:
        """Crée un ordre limite d'achat avec timeout automatique
        
        Args:
            symbol: Symbole à acheter (ex: 'BTC/USDC')
            amount: Quantité de l'actif de base (BTC) à acheter
            price: Prix limite
            timeout: Délai avant annulation automatique (en secondes)
            on_timeout_callback: Fonction à appeler si l'ordre est annulé par timeout
            on_fill_callback: Fonction à appeler si l'ordre est rempli
            attempt: Numéro de la tentative actuelle
            max_attempts: Nombre maximal de tentatives
            
        Returns:
            L'ordre créé ou None si échec
        """
        try:
            trading_logger.info(f"""
=== CRÉATION ORDRE LIMITE ACHAT (TENTATIVE {attempt}/{max_attempts}) ===
   Symbole: {symbol}
   Montant: {amount:.2f} USDC
   Prix limite: {price:.8f}
   Timeout: {timeout}s
""")
            
            # Créer l'ordre limite
            # Dans ccxt_mexc_api.py, la signature est:
            # create_limit_buy_order(symbol: str, price: float, amount: Optional[float] = None, 
            #                        cost: Optional[float] = None, params: Dict[str, Any] = None)
            # Nous voulons passer amount=None et cost=amount pour payer un montant fixe en USDC
            order = await self.exchange.create_limit_buy_order(
                symbol=symbol,
                price=price,
                amount=amount    # Quantité fixe en ETH
            )
            
            if not order or 'id' not in order:
                trading_logger.info(f"❌ Échec création ordre limite achat: {order}")
                return None
                
            order_id = order['id']
            
            # Enregistrer l'ordre actif
            self.active_orders[order_id] = {
                'symbol': symbol,
                'type': 'buy',
                'amount': amount,
                'price': price,
                'timestamp': time.time(),
                'timeout': timeout,
                'attempt': attempt,
                'max_attempts': max_attempts
            }
            
            # Mettre à jour le compteur de tentatives
            self.order_attempts[symbol] = attempt
            
            # Enregistrer les callbacks si fournis
            if on_timeout_callback:
                self.order_callbacks[order_id] = on_timeout_callback
                
            if on_fill_callback:
                self.fill_callbacks[order_id] = on_fill_callback
            
            # S'assurer que la vérification des ordres est active
            await self.start_order_checker()
            
            trading_logger.info(f"✅ Ordre limite achat créé: {order_id}")
            return order
            
        except Exception as e:
            error_logger.error(f"Erreur lors de la création de l'ordre limite achat: {str(e)}")
            return None
    
    async def create_limit_sell_order(self, symbol: str, quantity: float, price: float, timeout: int = 7,
                                     on_timeout_callback: Optional[Callable] = None,
                                     on_fill_callback: Optional[Callable] = None,
                                     attempt: int = 1) -> Optional[Dict[str, Any]]:
        """Crée un ordre limite de vente avec timeout automatique
        
        Args:
            symbol: Symbole à vendre (ex: 'BTC/USDC')
            quantity: Quantité à vendre
            price: Prix limite
            timeout: Délai avant annulation automatique (en secondes)
            on_timeout_callback: Fonction à appeler si l'ordre est annulé par timeout
            on_fill_callback: Fonction à appeler si l'ordre est rempli
            attempt: Numéro de la tentative actuelle
            
        Returns:
            L'ordre créé ou None si échec
        """
        try:
            trading_logger.info(f"""
=== CRÉATION ORDRE LIMITE VENTE (TENTATIVE {attempt}) ===
   Symbole: {symbol}
   Quantité: {quantity:.8f}
   Prix limite: {price:.8f}
   Timeout: {timeout}s
""")
            
            try:
                # Créer l'ordre limite
                order = await self.exchange.create_limit_sell_order(symbol, quantity, price)
            except Exception as order_error:
                # Vérifier si l'erreur est "Oversold" (code 30005)
                error_str = str(order_error)
                if "Oversold" in error_str or "code\":30005" in error_str:
                    # Réduire la quantité de 5% supplémentaires et réessayer
                    reduced_quantity = quantity * 0.95
                    trading_logger.info(f"""
=== ERREUR OVERSOLD DÉTECTÉE ===
   Quantité initiale: {quantity:.8f}
   Réduction de 5% supplémentaire
   Nouvelle quantité: {reduced_quantity:.8f}
   Action: Réessai automatique
""")
                    # Nouvelle tentative avec la quantité réduite
                    order = await self.exchange.create_limit_sell_order(symbol, reduced_quantity, price)
                else:
                    # Pour les autres types d'erreurs, les propager
                    raise
            
            if not order or 'id' not in order:
                trading_logger.info(f"❌ Échec création ordre limite vente: {order}")
                return None
                
            order_id = order['id']
            
            # Récupérer la quantité réelle utilisée (qui peut avoir été réduite)
            actual_quantity = float(order.get('amount', quantity))
            
            # Enregistrer l'ordre actif
            self.active_orders[order_id] = {
                'symbol': symbol,
                'type': 'sell',
                'quantity': actual_quantity,
                'price': price,
                'timestamp': time.time(),
                'timeout': timeout,
                'attempt': attempt
            }
            
            # Mettre à jour le compteur de tentatives pour les ventes
            self.sell_attempts[symbol] = attempt
            
            # Enregistrer les callbacks
            if on_timeout_callback:
                self.order_callbacks[order_id] = on_timeout_callback
                
            if on_fill_callback:
                self.fill_callbacks[order_id] = on_fill_callback
            
            # S'assurer que la vérification des ordres est active
            await self.start_order_checker()
            
            trading_logger.info(f"✅ Ordre limite vente créé: {order_id}")
            # Démarrage du watcher de timeout (timeout={timeout}s)
            asyncio.create_task(self._sell_order_timeout_watcher(order_id, symbol, timeout, on_timeout_callback))
            return order
            
        except Exception as e:
            error_logger.error(f"Erreur lors de la création de l'ordre limite de vente: {str(e)}")
            return None
    
    async def cancel_all_orders(self, symbol: Optional[str] = None) -> int:
        """Annule tous les ordres actifs
        
        Args:
            symbol: Symbole spécifique (optionnel) ou tous les symboles si None
            
        Returns:
            Nombre d'ordres annulés
        """
        count = 0
        orders_to_remove: List[str] = []
        callbacks_to_execute: List[Tuple[str, Callable]] = []
        
        for order_id, order_info in list(self.active_orders.items()):
            if symbol is None or order_info['symbol'] == symbol:
                try:
                    # Vérifier le statut de l'ordre
                    order_status = await self.exchange.fetch_order(order_id, order_info['symbol'])
                    if order_status.get('status') == 'closed' or order_status.get('filled') == order_status.get('amount'):
                        trading_logger.info(f"Ordre {order_id} déjà rempli, annulation ignorée")
                        orders_to_remove.append(order_id)
                        if order_id in self.fill_callbacks:
                            await self.fill_callbacks[order_id](order_status)
                            del self.fill_callbacks[order_id]
                        continue
                    # Tenter l'annulation
                    await self.exchange.cancel_order(order_id, order_info['symbol'])
                    trading_logger.info(f"Ordre {order_id} annulé avec succès")
                    count += 1
                    orders_to_remove.append(order_id)
                    if order_id in self.order_callbacks:
                        callbacks_to_execute.append((order_id, self.order_callbacks[order_id]))
                except Exception as e:
                    error_message = str(e)
                    if "code\":-2011" in error_message:
                        trading_logger.info(f"Ordre {order_id} annulé (code -2011) => timeout")
                        if order_id in self.order_callbacks:
                            callbacks_to_execute.append((order_id, self.order_callbacks[order_id]))
                    else:
                        error_logger.error(f"Erreur annulation ordre {order_id}: {error_message}")
                        if order_id in self.order_callbacks:
                            callbacks_to_execute.append((order_id, self.order_callbacks[order_id]))
                    orders_to_remove.append(order_id)

        # Supprimer les ordres annulés de notre suivi
        for oid in orders_to_remove:
            if oid in self.active_orders:
                del self.active_orders[oid]
            if oid in self.order_callbacks:
                del self.order_callbacks[oid]

        # Exécuter les callbacks timeout
        for oid, callback in callbacks_to_execute:
            try:
                result = callback()
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                error_logger.error(f"Erreur callback cancel_all_orders pour {oid}: {e}")

        trading_logger.info(f"Annulation de {count} ordres limites{' pour ' + symbol if symbol else ''}")
        return count
    
    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Retourne le statut d'un ordre actif
        
        Args:
            order_id: ID de l'ordre
            
        Returns:
            Infos de l'ordre ou None si non trouvé
        """
        return self.active_orders.get(order_id)
    
    def get_active_orders_count(self, symbol: Optional[str] = None) -> int:
        """Retourne le nombre d'ordres actifs
        
        Args:
            symbol: Symbole spécifique (optionnel) ou tous les symboles si None
            
        Returns:
            Nombre d'ordres actifs
        """
        if symbol is None:
            return len(self.active_orders)
        else:
            return len([o for o in self.active_orders.values() if o['symbol'] == symbol])
    
    def get_buy_attempt_count(self, symbol: str) -> int:
        """Retourne le nombre de tentatives d'achat pour un symbole
        
        Args:
            symbol: Symbole concerné
            
        Returns:
            Nombre de tentatives
        """
        return self.order_attempts.get(symbol, 0)
    
    def get_sell_attempt_count(self, symbol: str) -> int:
        """Retourne le nombre de tentatives de vente pour un symbole
        
        Args:
            symbol: Symbole concerné
            
        Returns:
            Nombre de tentatives
        """
        return self.sell_attempts.get(symbol, 0)
    
    def reset_buy_attempts(self, symbol: str) -> None:
        """Réinitialise le compteur de tentatives d'achat pour un symbole
        
        Args:
            symbol: Symbole concerné
        """
        if symbol in self.order_attempts:
            del self.order_attempts[symbol]
    
    def reset_sell_attempts(self, symbol: str) -> None:
        """Réinitialise le compteur de tentatives de vente pour un symbole
        
        Args:
            symbol: Symbole concerné
        """
        if symbol in self.sell_attempts:
            del self.sell_attempts[symbol]

    async def _sell_order_timeout_watcher(self, order_id: str, symbol: str, timeout: int, on_timeout_callback: Optional[Callable]) -> None:
        """Surveille le timeout d'un ordre de vente et annule si non rempli."""
        try:
            await asyncio.sleep(timeout)
            if order_id in self.active_orders:
                trading_logger.info(f"⏰ Timeout ordre vente {order_id} atteint, annulation automatique")
                await self.cancel_order(order_id, symbol)
                self.active_orders.pop(order_id, None)
                if on_timeout_callback:
                    await on_timeout_callback()
        except Exception as e:
            error_logger.error(f"Erreur watcher timeout vente: {str(e)}")