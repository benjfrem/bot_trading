"""Module principal d'analyse du marché avec adaptation aux tendances"""
import asyncio
from typing import Dict, Optional, List, Tuple, Any
from datetime import datetime

from config import Config
from constants import MarketConstants as MC
from logger import trading_logger, error_logger
from utils.indicators.taapi_client import taapi_client
from utils.trading.trailing_buy import TrailingBuyRsi
from .market_data import MarketData
from .data_fetcher import DataFetcher
from .indicator_calculator import IndicatorCalculator
from .opportunity_finder import OpportunityFinder

class MarketAnalyzer:
    """Classe principale pour l'analyse du marché"""
    
    def __init__(self):
        """Initialise l'analyseur de marché avec la configuration MEXC"""
        self._validate_trailing_buy_levels()
        self.market_data: Dict[str, MarketData] = {}
        self.portfolio_manager = None
        
        # Initialiser les composants
        self.data_fetcher = DataFetcher(log_callback=self._log)
        self.indicator_calculator = IndicatorCalculator(log_callback=self._log)
        self.opportunity_finder = OpportunityFinder(log_callback=self._log)

        
        # Log d'initialisation
        self._log("Analyseurs d'indicateurs techniques initialisés")
        
    @property
    def exchange(self):
        """Renvoie l'objet exchange de data_fetcher pour maintenir la compatibilité"""
        return self.data_fetcher.exchange if hasattr(self.data_fetcher, 'exchange') else None
    
    def _log(self, message: str, level: str = "info") -> None:
        """Centralise la gestion des logs"""
        if level == "info":
            trading_logger.info(message)
        elif level == "error":
            error_logger.error(message)
        print(message)
    
    def _validate_trailing_buy_levels(self) -> None:
        """Valide les niveaux de trailing buy RSI configurés"""
        if not Config.TRAILING_BUY_RSI_LEVELS:
            raise ValueError("Les niveaux de trailing buy RSI ne sont pas configurés")
            
        for level in Config.TRAILING_BUY_RSI_LEVELS:
            if not all(key in level for key in ['trigger', 'stop', 'immediate']):
                raise ValueError("Configuration de trailing buy RSI invalide: champs manquants")
            if level['trigger'] > level['stop']:
                raise ValueError(f"Configuration de trailing buy RSI invalide: le niveau de déclenchement ({level['trigger']}) est supérieur au niveau de stop ({level['stop']})")
    
    async def verify_symbols(self) -> None:
        """Vérifie la validité des symboles configurés"""
        await self.data_fetcher.verify_symbols()
    
    async def initialize_markets(self) -> None:
        """Initialise l'exchange et les données de marché pour tous les symboles"""
        self._log("Initialisation des marchés...")
        
        # Initialiser l'exchange
        await self.data_fetcher.init_exchange()
        
        # Initialiser les données de marché pour chaque symbole
        for symbol in Config.CRYPTO_LIST:
            price = await self.data_fetcher.fetch_data_for_symbol(symbol, "initialize")
            if price and price > 0:
                self.market_data[symbol] = MarketData(
                    reference_price=price,
                    last_update=datetime.now(),
                    consecutive_increases=0,
                    last_price=price,
                    price_history=[],
                    volume_history=[],
                    market_trend="neutral",
                    trend_variation=0.0
                )
                self._log(f"✓ Prix initial pour {symbol}: {price:.8f} USDC")
                
        
        # Charger les données historiques pour les indicateurs
        await self.data_fetcher.load_historical_data(self.market_data)
        
        # Initialiser le système de scoring - version simplifiée sans bb_analyzer et volume_analyzer
        self.opportunity_finder.init_scoring_system(
            rsi_analyzer=TrailingBuyRsi()
        )
    
    async def calculate_rsi(self, symbol: str, period: int = Config.RSI_PERIOD) -> Optional[float]:
        """Calcule le RSI pour un symbole en utilisant taapi.io"""
        try:
            market_data = self.market_data.get(symbol)
            
            # Désactiver complètement le cache pour obtenir une valeur RSI fraîche à chaque fois
            # Pour éviter le problème de blocage du RSI à une valeur fixe
            
            # Utiliser le client taapi.io pour récupérer le RSI
            # Cette requête est effectuée une fois par seconde pour obtenir une valeur RSI extrêmement précise
            rsi = await taapi_client.get_rsi(symbol, period)
            
            # Mettre à jour les informations RSI dans les données de marché
            if market_data and rsi is not None:
                market_data.rsi_value = rsi
                market_data.rsi_timestamp = datetime.now()
                market_data.rsi_state = None  # Le nouveau calcul RSI n'utilise pas d'état
            
            return rsi
            
        except Exception as e:
            self._log(f"Erreur de calcul RSI pour {symbol}: {str(e)}", "error")
            return None
    
    async def check_consecutive_increases(self, symbol: str, current_price: float) -> bool:
        """Vérifie les hausses consécutives de prix"""
        market_data = self.market_data.get(symbol)
        if not market_data:
            self.market_data[symbol] = MarketData(
                reference_price=current_price,
                last_update=datetime.now(),
                consecutive_increases=0,
                last_price=current_price
            )
            return False
        
        if current_price > market_data.last_price:
            market_data.consecutive_increases += 1
            self._log(f"{symbol}: Hausse détectée ({market_data.consecutive_increases} consécutive(s))")
        else:
            market_data.consecutive_increases = 0
            self._log(f"{symbol}: Réinitialisation du compteur de hausses")
        
        market_data.last_price = current_price
        return market_data.consecutive_increases >= 3
    
    def should_update_reference(self, symbol: str) -> bool:
        """Détermine si le prix de référence doit être mis à jour"""
        # On ne met plus à jour automatiquement le prix de référence
        return False
    
    async def update_reference_price(self, symbol: str, current_price: float, force: bool = False) -> None:
        """Met à jour le prix de référence d'un symbole"""
        if current_price and current_price > 0:
            if force or self.should_update_reference(symbol):
                market_data = self.market_data.get(symbol)
                if not market_data:
                    market_data = MarketData(
                        reference_price=current_price,
                        last_update=datetime.now(),
                        consecutive_increases=0,
                        last_price=current_price
                    )
                    self.market_data[symbol] = market_data
                else:
                    market_data.reference_price = current_price
                    market_data.last_update = datetime.now()
                    market_data.consecutive_increases = 0
                self._log(f"Prix de référence mis à jour pour {symbol}: {current_price:.8f} USDC")
    
    async def get_current_price(self, symbol: str) -> Optional[float]:
        """Récupère le prix actuel d'un symbole (délégué à data_fetcher)"""
        return await self.data_fetcher.get_current_price(symbol)

    async def get_market_info(self, symbol: str) -> Optional[dict]:
        """Récupère les informations du marché pour un symbole (délégué à data_fetcher)"""
        return await self.data_fetcher.get_market_info(symbol)
        
    async def analyze_market(self) -> List[Dict[str, Any]]:
        """Analyse le marché pour identifier les opportunités de trading (tendance neutre uniquement)"""
        # Logs réduits - suppression du message d'analyse du marché
        # self._log("\n=== ANALYSE DU MARCHÉ ===")
        
        # Filtrer les symboles qui ont déjà une position ouverte
        active_positions = set()
        if hasattr(self, 'portfolio_manager') and self.portfolio_manager:
            active_positions = set(self.portfolio_manager.positions.keys())
        
        # Symboles à analyser (exclure ceux qui ont déjà une position)
        symbols_to_analyze = [s for s in Config.CRYPTO_LIST if s not in active_positions]
        
        if not symbols_to_analyze:
            # self._log("Aucun symbole à analyser (toutes les positions sont occupées)")
            return []
            
        # Logs réduits - suppression du message d'analyse des symboles
        # self._log(f"Analyse de {len(symbols_to_analyze)} symboles...")
        
        # Période maximale nécessaire pour les indicateurs (uniquement RSI maintenant)
        max_period = Config.RSI_PERIOD * 2
        
        # Récupérer les données OHLCV pour tous les symboles en une seule fois
        ohlcv_data = await self.data_fetcher.fetch_ohlcv_batch(symbols_to_analyze, max_period)
        
        # Mettre à jour les indicateurs techniques pour tous les symboles
        indicators_results = await self.indicator_calculator.update_indicators_batch(
            symbols_to_analyze, self.market_data, ohlcv_data, self.data_fetcher
        )
        
        # Récupérer les informations de marché pour tous les symboles avec indicateurs valides
        market_info_symbols = [symbol for symbol, vals in indicators_results.items() if isinstance(vals, (tuple, list)) and len(vals) >= 2 and vals[0] and vals[1]]
        
        # Récupérer les informations de marché en parallèle
        market_infos = {}
        if market_info_symbols:
            semaphore = asyncio.Semaphore(3)  # Limite à 3 requêtes simultanées
            
            async def get_market_info_with_semaphore(symbol):
                async with semaphore:
                    info = await self.data_fetcher.get_market_info(symbol)
                    return symbol, info
            
            market_info_results = await asyncio.gather(
                *[get_market_info_with_semaphore(symbol) for symbol in market_info_symbols],
                return_exceptions=False
            )
            
            for symbol, info in market_info_results:
                if info:
                    market_infos[symbol] = info
        
        # Trouver les opportunités de trading
        opportunities = await self.opportunity_finder.find_opportunities(
            symbols_to_analyze, self.market_data, indicators_results, market_infos, active_positions=active_positions
        )
        
        return opportunities
