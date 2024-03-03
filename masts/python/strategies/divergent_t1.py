import talib
from python.common.logging_config import logger
from python.strategies.istrategy import IStrategy, SignalType, MarketTrend, MarketEnergy
from python.indicators.choppiness_index import choppiness_index
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
        self.required_data[f"{self.symbol}_{self.timeframe}"] = 100
        self.required_data[f"{self.symbol}_H1"] = 100
        self.required_data[f"{self.symbol}_M15"] = 100

    def _get_signal(self, market_trend):
        result = SignalType.NONE
        if market_trend == MarketTrend.BULL:
            result = SignalType.BUY
        elif market_trend == MarketTrend.BEAR:
            result = SignalType.SELL

        logger.debug(f"_get_signal() -> {result}")
        return result

    def _get_trend_from_timeframe(self, time_frame):
        result = MarketTrend.UNDEFINED
        trend_ema = self._get_trend_ema(time_frame)
        energy_chopp = self._get_energy_choppiness_index(time_frame)
        if trend_ema == MarketTrend.BULL and (energy_chopp == MarketEnergy.VERY_HIGH or energy_chopp == MarketEnergy.HIGH):
            result = MarketTrend.BULL
        elif trend_ema == MarketTrend.BEAR and (energy_chopp == MarketEnergy.VERY_LOW or energy_chopp == MarketEnergy.LOW):
            result = MarketTrend.BEAR
        return result

    def _get_trend_ema(self, time_frame):
        periods = 10.0
        timeperiod = 50
        min_slope = 0.30
        result = MarketTrend.UNDEFINED
        symbol_tf = f"{self.symbol}_{time_frame}"
        data = self.historic_data[symbol_tf]['data'].copy()
        df = convert_historic_bars_to_dataframe(data)
        close_prices = df['close']
        ema_values = talib.EMA(close_prices, timeperiod=timeperiod)

        # Get the last 3 values of each EMA series
        ema_values = ema_values[-periods:]
        last_candle = periods-1
        oldest_candle = 0

        # Check if EMA_values has a positive slope.
        slope = (ema_values[last_candle] - ema_values[oldest_candle]) / periods
        if slope > 0.0 and slope > min_slope:
            result = MarketTrend.BULL
        elif slope < 0.0 and slope < (min_slope * (-1)):
            result = MarketTrend.BEAR

        return result

    def _get_energy_choppiness_index(self, time_frame):
        timeperiod = 14
        periods = 5
        result = MarketEnergy.NOT_SIGNIFICANT
        symbol_tf = f"{self.symbol}_{time_frame}"
        data = self.historic_data[symbol_tf]['data'].copy()
        df = convert_historic_bars_to_dataframe(data)
        close_prices = df['close']
        chopp_values = choppiness_index.calculate(close_prices, timeperiod)
        chopp_values = chopp_values[-periods:]
        last_candle = periods-1
        last_value = chopp_values[last_candle]

        # Determine energy.
        if last_value >= 61.8:
            result = MarketEnergy.VERY_HIGH
        elif 61.8 > last_value >= 55.0:
            result = MarketEnergy.HIGH
        elif 25.0 < last_value <= 38.2:
            result = MarketEnergy.LOW
        elif last_value <= 25.0:
            result = MarketEnergy.VERY_LOW
        else:
            result = MarketEnergy.NOT_SIGNIFICANT

        return result

    def _get_market_trend(self):
        logger.info("_get_market_trend() -> Starts")
        result = MarketTrend.UNDEFINED
        anchor_trend = self._get_trend_from_timeframe(self.timeframe)
        if anchor_trend != MarketTrend.UNDEFINED:
            middle_trend = self._get_trend_from_timeframe("H1")
            if anchor_trend == middle_trend:
                result = anchor_trend

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
