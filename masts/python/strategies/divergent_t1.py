import talib
from python.common.logging_config import logger
from python.strategies.istrategy import IStrategy, SignalType, MarketTrend
from python.indicators.macd_platinum_v2 import macd_platinum_v2

class DivergentT1(IStrategy):
    MAGIC_NO = 1

    def __init__(self, smart_trader, symbol, timeframe, max_risk_per_trade):
        super().__init__(smart_trader, symbol, timeframe, max_risk_per_trade)  # Call the constructor of the base class
        self._set_required_bars()
        self.name = "DivergentT1"
        self.id = f"{self.name}_{symbol}_{timeframe}"
        self.magic_no = self.MAGIC_NO  # identify orders in MT4 for this strategy.
        self.historic_data = {}
        logger.info(f"DivergentT1({symbol}, {timeframe}, {max_risk_per_trade})")

    def _set_required_bars(self):
        self.required_data = {}
        self.required_data[f"{self.symbol}_{self.timeframe}"] = 240
        self.required_data[f"{self.symbol}_M1"] = 120

    def _get_signal(self, market_trend):
        result = SignalType.NONE
        # TODO: implements _get_signal
        logger.debug(f"_get_signal() -> {result}")
        return result

    def _get_market_trend(self):
        result = MarketTrend.UNDEFINED

        # TODO: implements _get_market_trend checking EMAS.



        result = MarketTrend.BULL
        logger.debug(f"_get_market_trend() -> {result}")
        return result

    def _is_ongoing(self):
        result = len(self.smart_trader.get_strategy_orders(self.magic_no)) > 0
        return result

    def _open_orders(self, signal):
        # TODO: implements _open_orders -> create orders for the strategy.
        dummy = 1

    def _validate_historic_data(self, historic_data):
        result = None

        



        return result

    ##############################################################################
    # Interface methods
    ##############################################################################
    def required_data(self):
        return self.required_data

    def execute(self, historic_data):
        self.historic_data = self._validate_historic_data(historic_data)

        # Manage current open orders
        if self._is_ongoing():
            self.manage_orders()
        elif self.historic_data is not None:
            # Open orders only if there isn't any open trade for the strategy
            marketTrend = self._get_market_trend()
            if marketTrend != MarketTrend.UNDEFINED and marketTrend != MarketTrend.SIDEWAYS:
                signal = self._get_signal(marketTrend)
                self._open_orders(signal)

    def manage_orders(self):
        # TODO: implement manage_orders() -> trailing stoploss / hidden take profit or stop loss.
        dummy = 1
