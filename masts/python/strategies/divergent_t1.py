import talib
from python.common.logging_config import logger
from python.strategies.istrategy import IStrategy, SignalType, MarketTrend
from python.indicators.macd_platinum_v2 import macd_platinum_v2
from python.common.conversions import convert_historic_bars_element_to_array, convert_periods_to_datetime_range, \
    get_lasts_from_dictionary
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
        self.required_data[f"{self.symbol}_{self.timeframe}"] = 245
        self.required_data[f"{self.symbol}_M1"] = 120

    def _get_signal(self, market_trend):
        result = SignalType.NONE
        # TODO: implements _get_signal
        logger.debug(f"_get_signal() -> {result}")
        return result

    def _get_trend_from_emas(self, ema_values_1, ema_values_2, ema_values_3, periods=3):
        # Ensure we have at least 3 values in each EMA series
        if len(ema_values_1) < periods or len(ema_values_2) < periods or len(ema_values_3) < periods:
            raise ValueError("Each EMA series should have at least 3 values.")

        # Get the last 3 values of each EMA series
        ema_values_1 = ema_values_1[-periods:]
        ema_values_2 = ema_values_2[-periods:]
        ema_values_3 = ema_values_3[-periods:]

        # Check if EMA_values_1 has a positive slope and is above the other two EMAs
        if ema_values_1[periods-1] > ema_values_1[0] and ema_values_1[periods-1] > ema_values_2[periods-1] and ema_values_1[periods-1] > ema_values_3[
            periods-1]:
            # Check if EMA_values_2 is above EMA_values_3
            if ema_values_2[periods-1] > ema_values_3[periods-1]:
                return MarketTrend.BULL

        # Check if EMA_values_1 has a negative slope and is below the other two EMAs
        if ema_values_1[periods-1] < ema_values_1[0] and ema_values_1[periods-1] < ema_values_2[periods-1] and ema_values_1[periods-1] < ema_values_3[
            periods-1]:
            # Check if EMA_values_2 is below EMA_values_3
            if ema_values_2[periods-1] < ema_values_3[periods-1]:
                return MarketTrend.BEAR

        return MarketTrend.UNDEFINED

    def _get_market_trend(self):
        logger.info("_get_market_trend() -> Starts")
        result = MarketTrend.UNDEFINED

        # Use 3 EMAs: 50, 100 and 240 in main timeframe
        symbol_tf = f"{self.symbol}_{self.timeframe}"
        data = self.historic_data[symbol_tf]['data']
        close_prices = convert_historic_bars_element_to_array('close', data)
        ema_50_values = talib.EMA(close_prices, timeperiod=50)
        ema_100_values = talib.EMA(close_prices, timeperiod=100)
        ema_240_values = talib.EMA(close_prices, timeperiod=240)
        result = self._get_trend_from_emas(ema_50_values, ema_100_values, ema_240_values)
        logger.info(f"ema50 [{ema_50_values[-3:]}], ema100 [{ema_100_values[-3:]}], ema240 [{ema_240_values[-3:]}]")
        logger.info(f"_get_market_trend() -> result [{result}]")
        return result

    def _is_ongoing(self):
        result = len(self.smart_trader.get_strategy_orders(self.magic_no)) > 0
        return result

    def _open_orders(self, signal):
        # TODO: implements _open_orders -> create orders for the strategy.
        dummy = 1

    def _validate_historic_data(self, historic_data):
        # TODO: validate historic data
        result = historic_data
        return result

    ##############################################################################
    # Interface methods
    ##############################################################################
    def required_data(self):
        return self.required_data

    def execute(self, historic_data):
        logger.info(f"DivergentT1 -> execute()")
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
