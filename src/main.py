"""Bot de trading principal"""
import signal
import sys
import asyncio
from datetime import datetime
from market_analyzer.analyzer import MarketAnalyzer
from portfolio_manager.__init__ import PortfolioManager
from utils.trading.trading_stats import TradingStats
from utils.system.task_scheduler import TaskScheduler
from utils.monitoring.activity_monitor import ActivityMonitor
from logger import trading_logger, error_logger
from config import Config
from utils.trading.trailing_buy import TrailingBuyRsi
from utils.trading.trailing_stop import TrailingStopLevel

class TradingBot:
    def __init__(self):
        """Initialise le bot de trading"""
        self.running = False
        self.opening_position_lock = asyncio.Lock()
        trading_logger.info("=== INITIALISATION DU BOT ===")
        
        try:
            self.market_analyzer = MarketAnalyzer()
            self.portfolio_manager = None
            self.scheduler = TaskScheduler()
            self.stats = TradingStats()
            self.activity_monitor = ActivityMonitor()
            
            signal.signal(signal.SIGINT, self._handle_sigint)
            signal.signal(signal.SIGTERM, self._handle_sigint)
            
            trading_logger.info("Bot initialisé avec succès")
            
        except Exception as e:
            error_logger.error(f"Erreur lors de l'initialisation: {str(e)}")
            raise
    
    async def start(self):
        """Démarre le bot de trading"""
        if self.running:
            trading_logger.info("Le bot est déjà en cours d'exécution")
            return
        
        try:
            trading_logger.info("=== DÉMARRAGE DU BOT ===")
            
            await self.market_analyzer.initialize_markets()
            
            
            
            if not self.portfolio_manager:
                self.portfolio_manager = PortfolioManager(
                    self.market_analyzer.exchange,
                    self.market_analyzer
                )
                self.market_analyzer.portfolio_manager = self.portfolio_manager
            
            # Configuration des tâches planifiées
            # Condition pour exécuter les tâches uniquement si aucune position n'est ouverte
            async def no_active_positions():
                return not (self.portfolio_manager and self.portfolio_manager.positions)
            
            self.scheduler.add_task('rsi_update', self._rsi_update_cycle, Config.ANALYSIS_INTERVAL)
            self.scheduler.add_task('short_term_trend_analysis', self._short_term_trend_cycle, Config.ANALYSIS_INTERVAL, condition=no_active_positions)
            self.scheduler.add_task('market_analysis', self._market_analysis_cycle, Config.ANALYSIS_INTERVAL, condition=no_active_positions)

            
            # Définition condition pour positions actives
            async def has_active_positions():
                return (
                    self.portfolio_manager is not None and 
                    hasattr(self.portfolio_manager, 'positions') and 
                    bool(self.portfolio_manager.positions)
                )
            
            self.scheduler.add_task(
                'position_check',
                self._check_positions_cycle,
                Config.CHECK_INTERVAL,
                condition=has_active_positions
            )
            
            
            self.scheduler.start()
            self.running = True

            # Watchdog temporairement désactivé pour alléger le trailing stop
            # asyncio.create_task(self._price_watchdog_loop())
            
            trading_logger.info("BOT DE TRADING DÉMARRÉ - Appuyez sur Ctrl+C pour arrêter")
            
            # Maintenir le bot en vie
            while self.running:
                await asyncio.sleep(1)
                
        except Exception as e:
            error_logger.error(f"Erreur critique lors du démarrage: {str(e)}")
            await self._handle_shutdown()
    
    async def _handle_shutdown(self):
        """Gère l'arrêt propre du bot"""
        if not self.running:
            return
            
        trading_logger.info("Arrêt du bot en cours...")
        self.running = False
        
        if hasattr(self, 'scheduler'):
            self.scheduler.stop()
        
        if hasattr(self, 'market_analyzer') and hasattr(self.market_analyzer, 'exchange'):
            try:
                await self.market_analyzer.exchange.close()
            except Exception as e:
                error_logger.error(f"Erreur lors de la fermeture de l'exchange: {str(e)}")
        
        if hasattr(self, 'stats'):
            trading_logger.info("=== STATISTIQUES FINALES ===")
            trading_logger.info(self.stats.format_stats())
        
        trading_logger.info("BOT ARRÊTÉ AVEC SUCCÈS")
    
    def _handle_sigint(self, signum, frame):
        """Gère l'interruption du programme"""
        trading_logger.info("Signal d'interruption reçu")
        
        if asyncio.get_event_loop().is_running():
            asyncio.create_task(self._handle_shutdown())
            asyncio.get_event_loop().call_later(2, sys.exit, 0)
        else:
            sys.exit(0)
    
    # Compteurs de mise à jour
    rsi_updates_counter = 0
    short_term_trend_updates_counter = 0
    last_counter_reset = datetime.now()

    async def _short_term_trend_cycle(self):
        """Cycle dédié à l'analyse de tendance à court terme"""
        if not self.running:
            return
            
        self.short_term_trend_updates_counter += 1
        symbols = Config.CRYPTO_LIST
        
        for symbol in symbols:
            try:
                current_price = await self.market_analyzer.get_current_price(symbol)
                if not current_price or current_price <= 0:
                    continue
                
                market_data = self.market_analyzer.market_data.get(symbol)
                if market_data and hasattr(market_data, 'trailing_buy_rsi') and market_data.trailing_buy_rsi:
                    trailing_buy = market_data.trailing_buy_rsi
                    
                    rsi_value = getattr(market_data, 'rsi_value', None)
                    if rsi_value is not None and rsi_value <= 25 and not trailing_buy.analyze_started:
                        trailing_buy.start_trend_analysis()
                        
                    if trailing_buy.analyze_started:
                        trailing_buy.update_short_term_trend(current_price, datetime.now())
            except Exception as e:
                error_logger.error(f"Erreur lors de l'analyse de tendance court terme pour {symbol}: {str(e)}")
                
        # Statistiques par minute
        current_time = datetime.now()
        if (current_time - self.last_counter_reset).total_seconds() >= 60:
            trading_logger.info(f"Statistiques minute: RSI: {self.rsi_updates_counter}, Tendance: {self.short_term_trend_updates_counter}")
            self.rsi_updates_counter = 0
            self.short_term_trend_updates_counter = 0
            self.last_counter_reset = current_time
    
    async def _rsi_update_cycle(self):
        """Cycle ultra-rapide dédié uniquement à l'actualisation du RSI"""
        if not self.running:
            return
        
        # Ne pas analyser le RSI si une position est active
        if self.portfolio_manager and self.portfolio_manager.positions:
            trading_logger.info("Position ouverte, analyse RSI suspendue")
            return
        
        self.rsi_updates_counter += 1
        symbols = Config.CRYPTO_LIST
        
        async def update_symbol_rsi(symbol):
            try:
                rsi = await self.market_analyzer.calculate_rsi(symbol)
                
                trading_logger.info(f"RSI actualisé: {symbol} = {rsi}")
                
                if rsi is not None and rsi <= 25:
                    trading_logger.info(f"⚠️ {symbol} en zone de survente (RSI: {rsi:.2f})")
                
                market_data = self.market_analyzer.market_data.get(symbol)
                if market_data and rsi is not None:
                    if not hasattr(market_data, 'trailing_buy_rsi') or market_data.trailing_buy_rsi is None:
                        market_data.trailing_buy_rsi = TrailingBuyRsi()
                    
                    trailing_buy = market_data.trailing_buy_rsi
                    
                    if rsi <= 25 and not trailing_buy.analyze_started:
                        trading_logger.info(f"Démarrage analyse RSI Trailing Buy: {symbol}, RSI: {rsi:.2f}")
                        trailing_buy.start_trend_analysis()
                        
                        current_price = await self.market_analyzer.get_current_price(symbol)
                        if current_price and current_price > 0:
                            trailing_buy.update_short_term_trend(current_price, datetime.now())
                            trailing_buy.update(rsi, current_price)
                    
                    elif trailing_buy.analyze_started:
                        current_price = await self.market_analyzer.get_current_price(symbol)
                        if current_price and current_price > 0:
                            signal_price = trailing_buy.update(rsi, current_price)
                            if signal_price:
                                # Signaler seulement la détection du signal, sans créer d'ordre
                                # Le traitement sera fait par opportunity_finder dans le cycle market_analysis
                                if not market_data.trailing_buy_rsi._signal_emitted:
                                    # Stocker le signal dans market_data pour que opportunity_finder puisse le traiter
                                    market_data.rsi_buy_signal_pending = True
                                    market_data.rsi_buy_signal_price = signal_price
                                    
                                    # Forcer l'exécution immédiate du cycle d'analyse de marché pour traiter ce signal
                                    trading_logger.info("Déclenchement manuel du cycle d'analyse de marché...")
                                    asyncio.create_task(self._market_analysis_cycle())
                                    
                                    trading_logger.info(f"""
=== SIGNAL RSI DÉTECTÉ ===
   Symbole: {symbol}
   RSI actuel: {rsi:.2f}
   RSI minimum: {trailing_buy.lowest_rsi:.2f}
   Prix signal: {signal_price:.8f}
   Action: Signal transmis au cycle d'analyse de marché
""")
                    
            except Exception as e:
                error_logger.error(f"Erreur lors de l'actualisation du RSI pour {symbol}: {str(e)}")
                
        await asyncio.gather(*[update_symbol_rsi(symbol) for symbol in symbols])
    
    async def _market_analysis_cycle(self):
        """Cycle d'analyse du marché avec le nouveau système de scoring"""
        if not self.running or not self.portfolio_manager:
            return
        
        # Vérifier si le verrou est déjà acquis (une ouverture de position est en cours)
        if self.opening_position_lock.locked():
            # Logs réduits - suppression du message de verrou
            # trading_logger.info("Une ouverture de position est déjà en cours, cycle d'analyse ignoré")
            return
        
        # Logs réduits - suppression des messages de cycle d'analyse
        # trading_logger.info("\n=== CYCLE D'ANALYSE DU MARCHÉ ===")
        # trading_logger.info("Recherche d'opportunités...")
        
        opportunities = await self.market_analyzer.analyze_market()
        
        if opportunities:
            trading_logger.info(f"✓ {len(opportunities)} opportunité(s) trouvée(s)")
            
            # Trier les opportunités par score (du plus élevé au plus bas)
            opportunities.sort(key=lambda x: x['score'], reverse=True)
            
            # Utiliser un verrou pour éviter les ouvertures multiples de positions
            async with self.opening_position_lock:
                # Ne traiter que la meilleure opportunité (la première après tri par score)
                if opportunities:
                    opportunity = opportunities[0]
                    symbol = opportunity['symbol']
                    score = opportunity['score']
                    position_size = opportunity['position_size']
                    
                    trading_logger.info(f"""
Opportunité détectée:
   Symbole: {symbol}
   Prix: {opportunity['current_price']:.8f} USDC
   Score: {score}/100 points
   Taille de position: {position_size * 100:.0f}%
   RSI: {opportunity['rsi']:.2f}
""")
                    
                    # Vérifier si l'opportunité a un signal de trailing buy
                    trailing_buy_triggered = opportunity.get('trailing_buy_triggered', False)
                    if not trailing_buy_triggered:
                        trading_logger.info(f"Pas de signal trailing buy pour {symbol}, achat ignoré")
                    else:
                        # Utiliser buy_price s'il est fourni par le trailing buy
                        buy_price = opportunity.get('buy_price', opportunity['current_price'])
                        
                        # Vérifier à nouveau si une position peut être ouverte pour ce symbole spécifique
                        # (au cas où une position aurait été ouverte entre-temps)
                        can_open = await self.portfolio_manager.can_open_position(symbol)
                        if can_open:
                            trading_logger.info(f"""
=== OUVERTURE POSITION SUITE À SIGNAL RSI ===
   Symbole: {symbol}
   Prix d'achat: {buy_price:.8f}
   RSI: {opportunity['rsi']:.2f}
   Score: {score}/100
   Signal trailing buy: {"OUI" if trailing_buy_triggered else "NON"}
""")
                            
                            # Ouvrir la position avec la taille calculée par le système de scoring
                            success = await self.portfolio_manager.open_position(
                                symbol,
                                buy_price,  # Utiliser le prix recommandé par le trailing buy
                                position_size
                            )
                            
                            if success:
                                trading_logger.info(f"Position ouverte avec succès pour {symbol}")
                                
                                # Appliquer configuration DMI− pour le trailing stop si nécessaire
                                if opportunity.get('dmi_zone') == 'warning':
                                    tsl = self.portfolio_manager.trailing_stop_paliers.get(symbol)
                                    if tsl:
                                        tsl.levels = [
                                            TrailingStopLevel(cfg['trigger'], cfg['stop'], cfg['immediate'])
                                            for cfg in Config.DMI_VIGILANCE_TRAILING_STOP_LEVELS
                                        ]
                                        trading_logger.info(f"Trailing stop renforcé appliqué pour {symbol} (zone vigilance DMI)")
                                
                                # Réinitialiser le trailing buy après un achat réussi
                                market_data = self.market_analyzer.market_data.get(symbol)
                                if market_data and hasattr(market_data, 'trailing_buy_rsi'):
                                    market_data.trailing_buy_rsi.reset()
                            else:
                                trading_logger.info(f"Échec de l'ouverture de position pour {symbol}")
        else:
            # Logs réduits - suppression du message d'aucune opportunité
            # trading_logger.info("✗ Aucune opportunité trouvée")
            pass
    
    async def _check_positions_cycle(self):
        """Cycle de vérification des positions"""
        if not self.running or not self.portfolio_manager:
            return
        
        # Vérifier s'il y a des positions actives avant de lancer le cycle
        active_positions = self.portfolio_manager.positions
        if not active_positions:
            # Aucune position active, pas besoin de vérification
            return
        
        trading_logger.info("\n=== VÉRIFICATION DES POSITIONS ===")
        trading_logger.info(f"Positions actives: {len(active_positions)}")
        
        trades = await self.portfolio_manager.check_positions()
        
        for trade in trades:
            # Journaliser le trade dans les statistiques
            self.stats.log_trade(trade.profit)
            
            # Journaliser le trade dans le moniteur d'activité
            trade_data = {
                "symbol": trade.symbol,
                "profit": trade.profit,
                "profit_percentage": trade.profit_percentage,
                "duration": trade.duration,
                "cost": trade.cost if hasattr(trade, 'cost') else None
            }
            self.activity_monitor.log_trade(trade_data)
            
            trading_logger.info(f"""
Trade complété:
   Symbole: {trade.symbol}
   Profit: {trade.profit:.2f} USDC ({trade.profit_percentage:.2f}%)
   Durée: {trade.duration:.1f} minutes
""")
    
    # La méthode _execute_buy_from_rsi_signal a été supprimée pour utiliser uniquement 
    # le mécanisme d'achat via le système d'opportunités dans opportunity_finder
    
    async def _price_watchdog_loop(self):
        """Boucle indépendante pour afficher le prix live toutes les secondes"""
        while self.running:
            # Si trailing stop actif (position ouverte), alléger la boucle
            if self.portfolio_manager and self.portfolio_manager.positions:
                await asyncio.sleep(1)
                continue
            # Boucle simplifiée pour préserver l’event loop
            for symbol in Config.CRYPTO_LIST:
                await self.market_analyzer.get_current_price(symbol)
            await asyncio.sleep(1)

# Point d'entrée principal
async def main():
    """Point d'entrée principal du bot"""
    try:
        bot = TradingBot()
        await bot.start()
    except Exception as e:
        error_logger.error(f"Erreur fatale: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        # Exécuter la boucle d'événements asyncio
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nArrêt du bot...")
    except Exception as e:
        error_logger.error(f"Erreur fatale: {str(e)}")
        sys.exit(1)
