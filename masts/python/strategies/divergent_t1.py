from python.common.logging_config import logger
from istrategy import IStrategy, SignalType, MarketTrend


class DivergentT1(IStrategy):

    def __init__(self, smart_trader, symbol, timeframe, max_risk_per_trade):
        super().__init__(smart_trader, symbol, timeframe, max_risk_per_trade)  # Call the constructor of the base class
        self._set_required_bars()
        self.name = "DivergentT1"
        self.id = f"{self.name}_{symbol}_{timeframe}"
        logger.info(f"DivergentT1({symbol}, {timeframe}, {max_risk_per_trade})")

    def _set_required_bars(self):
        self.required_data = None
        self.required_data[f"{self.symbol}_{self.timeframe}"] = 240
        if self.timeframe == 'H4':
            self.required_data[f"{self.symbol}_{'H1'}"] = 240

    def _get_signal(self, market_trend):
        result = SignalType.NONE

        logger.debug(f"_get_signal() -> {result}")
        return result

    def _get_market_trend(self):
        result = MarketTrend.UNDEFINED

        result = MarketTrend.BULL
        logger.debug(f"_get_market_trend() -> {result}")
        return result

    def _is_ongoing(self):
        result = False

    def _open_orders(self, signal):
        dummy = 1

    ##############################################################################
    # Interface methods
    ##############################################################################
    def required_data(self):
        return self.required_data

    def execute(self):
        # Manage current open orders
        if self._is_ongoing():
            self.manage_orders()

        # Open orders only if there isn't any open trade for the strategy
        if not self._is_ongoing():
            marketTrend = self._get_market_trend()
            if marketTrend != MarketTrend.UNDEFINED and marketTrend != MarketTrend.SIDEWAYS:
                signal = self._get_signal(marketTrend)
                self._open_orders(signal)



    def manage_orders(self):
        dummy = 1
