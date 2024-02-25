import talib
from python.common.logging_config import logger
from python.strategies.istrategy import IStrategy, SignalType, MarketTrend
from python.indicators.macd_platinum_v2 import macd_platinum_v2
from python.common.conversions import convert_historic_bars_to_dataframe
from python.api.dwx_client import dwx_client
from python.backtesting.backtesting import backtesting
from python.common.graphics import graph_trend_from_backtesting
from datetime import datetime
from python.common.calculus import get_pip_value
from python.common.risk_management import RiskManagement

class DivergentT1(IStrategy):

    def __init__(self, smart_trader, magic_no, symbol, timeframe, max_risk_perc_trade, max_consecutive_losses, symbol_spec=None):
        super().__init__(smart_trader, magic_no, symbol, timeframe, max_risk_perc_trade, max_consecutive_losses, symbol_spec)  # Call the constructor of the base class
        self._set_required_bars()
        self.historic_data = {}
        logger.info(f"DivergentT1({symbol}, {timeframe}, {max_risk_perc_trade}, {max_consecutive_losses})")

    def _set_required_bars(self):
        self.required_data = {}
        self.required_data[f"{self.symbol}_{self.timeframe}"] = 350
        self.required_data[f"{self.symbol}_M1"] = 120

    def _get_signal(self, market_trend):
        result = SignalType.NONE
        if market_trend == MarketTrend.BULL:
            result = SignalType.BUY
        elif market_trend == MarketTrend.BEAR:
            result = SignalType.SELL

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

        last_candle = periods-1
        oldest_candle = 0

        # Check if EMA_values_1 has a positive slope and is above the other two EMAs
        if ema_values_1[oldest_candle] < ema_values_1[last_candle] and ema_values_1[last_candle] > ema_values_2[last_candle] and ema_values_1[last_candle] > ema_values_3[last_candle]:
            # Check if EMA_values_2 is above EMA_values_3
            if ema_values_2[last_candle] > ema_values_3[last_candle]:
                return MarketTrend.BULL

        # Check if EMA_values_1 has a negative slope and is below the other two EMAs
        if ema_values_1[oldest_candle] > ema_values_1[last_candle] and ema_values_1[last_candle] < ema_values_2[last_candle] and ema_values_1[last_candle] < ema_values_3[last_candle]:
            # Check if EMA_values_2 is below EMA_values_3
            if ema_values_2[last_candle] < ema_values_3[last_candle]:
                return MarketTrend.BEAR

        return MarketTrend.UNDEFINED

    def _get_market_trend(self):
        logger.info("_get_market_trend() -> Starts")
        result = MarketTrend.UNDEFINED

        # Use 3 EMAs: 50, 100 and 240 in main timeframe
        symbol_tf = f"{self.symbol}_{self.timeframe}"
        data = self.historic_data[symbol_tf]['data'].copy()
        df = convert_historic_bars_to_dataframe(data)
        close_prices = df['close']
        ema_50_values = talib.EMA(close_prices, timeperiod=50)
        ema_100_values = talib.EMA(close_prices, timeperiod=100)
        ema_240_values = talib.EMA(close_prices, timeperiod=240)
        result = self._get_trend_from_emas(ema_50_values, ema_100_values, ema_240_values)
        max_datetime = max([datetime.strptime(key, '%Y.%m.%d %H:%M') for key in data.keys()])

        #if max_datetime >= datetime.strptime('2023.08.01 00:00', '%Y.%m.%d %H:%M'):
        #    logger.debug(f"_get_market_trend() -> data = {data}")
        #    logger.debug(f"_get_market_trend() -> df = {df}")
        #    graph_trend_from_backtesting(data, self.symbol, self.timeframe, ema_50_values, ema_100_values, ema_240_values)

        logger.info(f"ema50 [{ema_50_values[-3:]}], ema100 [{ema_100_values[-3:]}], ema240 [{ema_240_values[-3:]}]")
        logger.info(f"_get_market_trend() -> result [{result}]")
        return result

    def _is_ongoing(self):
        result = len(self.smart_trader.get_strategy_orders(self.magic_no)) > 0
        return result

    def _open_orders(self, signal):
        stop_loss_pips = 40
        tsl_margin_pips = 40
        stop_loss_points = self.symbol_spec['pip_value'] * stop_loss_pips
        tsl_margin_points = self.symbol_spec['pip_value'] * tsl_margin_pips
        comment = f'tsl={tsl_margin_points}'
        if signal == SignalType.BUY:
            price = self.smart_trader.dma.market_data[self.symbol]['ask']
            stop_loss = price - stop_loss_points
            take_profit = 0.0
            order_size = self.smart_trader.risk_management.get_new_order_size(self.id, self.symbol, price, stop_loss, self.smart_trader.get_current_datetime())
            self.smart_trader.dma.open_order(symbol=self.symbol, order_type='buy', lots=order_size, price=price,
                                             stop_loss=stop_loss, take_profit=take_profit, magic=self.magic_no,
                                             comment=comment)
        elif signal == SignalType.SELL:
            price = self.smart_trader.dma.market_data[self.symbol]['bid']
            stop_loss = price + stop_loss_points
            take_profit = 0.0
            order_size = self.smart_trader.risk_management.get_new_order_size(self.id, self.symbol, price, stop_loss, self.smart_trader.get_current_datetime())
            self.smart_trader.dma.open_order(symbol=self.symbol, order_type='sell', lots=order_size, price=price,
                                             stop_loss=stop_loss, take_profit=take_profit, magic=self.magic_no,
                                             comment=comment)

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
