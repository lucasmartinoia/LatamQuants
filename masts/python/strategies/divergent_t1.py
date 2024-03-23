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
import math

class DivergentT1(IStrategy):
    _market_trend = MarketTrend.UNDEFINED
    _box_high_limit = 0.0
    _box_low_limit = 0.0

    def __init__(self, smart_trader, magic_no, symbol, timeframe, high_timeframe1, high_timeframe2, signal_timeframe, max_risk_perc_trade, max_consecutive_losses, symbol_spec=None):
        super().__init__(smart_trader, magic_no, symbol, timeframe, high_timeframe1, high_timeframe2, signal_timeframe, max_risk_perc_trade, max_consecutive_losses, symbol_spec)  # Call the constructor of the base class
        self._set_required_bars()
        self.historic_data = {}
        logger.info(f"DivergentT1({symbol}, {timeframe}, {max_risk_perc_trade}, {max_consecutive_losses})")

    def _set_required_bars(self):
        self.required_data = {}
        self.required_data[f"{self.symbol}_{self.high_timeframe1}"] = 100
        self.required_data[f"{self.symbol}_{self.high_timeframe2}"] = 100
        self.required_data[f"{self.symbol}_{self.timeframe}"] = 100  # Main timeframe to evaluate trend.
        self.required_data[f"{self.symbol}_{self.signal_timeframe}"] = 5 # Used only for backtesting to avoid tick data level and improve the process speed.

    def _get_signal(self, market_trend):
        result = SignalType.NONE
        signal_periods = 10
        if market_trend == MarketTrend.BULL or market_trend == MarketTrend.BEAR:
            highest_price, lowest_price = self._get_box_higher_lower("M15", signal_periods)
            current_ask = self.smart_trader.dma.market_data[self.symbol]['ask']
            current_bid = self.smart_trader.dma.market_data[self.symbol]['bid']
            if market_trend == MarketTrend.BULL and current_ask >= highest_price:
                result = SignalType.BUY
            elif market_trend == MarketTrend.BEAR and current_bid <= lowest_price:
                result = SignalType.SELL

        logger.debug(f"_get_signal() -> {result}")
        return result

    def _get_box_higher_lower(self, time_frame, periods):
        symbol_tf = f"{self.symbol}_{time_frame}"
        data = self.historic_data[symbol_tf]['data'].copy()
        keys = list(data.keys())[-periods:]
        data = {key: data[key] for key in keys}
        df = convert_historic_bars_to_dataframe(data)
        highest_price = df['high'].max()
        lowest_price = df['low'].min()
        return highest_price, lowest_price

    def _get_trend_from_timeframe(self, time_frame, energy_minim=None):
        result = MarketTrend.UNDEFINED
        trend_ema = self._get_trend_ema(time_frame)

        if trend_ema != MarketTrend.UNDEFINED and trend_ema != MarketTrend.SIDEWAYS:
            energy_chopp, energy_value = self._get_energy_choppiness_index(time_frame)
            if (energy_minim is None and (energy_chopp == MarketEnergy.VERY_HIGH or energy_chopp == MarketEnergy.HIGH)) or (energy_value >= energy_minim):
                result = trend_ema
        return result

    def _get_trend_ema(self, time_frame):
        periods = 10
        timeperiod = 50
        min_slope = 30.0
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
        max_value = ema_values.max()
        min_value = ema_values.min()

        # Check if EMA_values has a positive slope.
        logger.debug(f'time_frame = {time_frame}, ema_50_last_value = {ema_values[last_candle]}, ema_50_oldest_value = {ema_values[oldest_candle]}, periods = {periods}')
        slope = (ema_values[last_candle] - ema_values[oldest_candle]) / periods
        slope = (slope - min_value) / (max_value - min_value)   # normalization
        angle_radians = math.atan(slope)
        slope_angle = math.degrees(angle_radians)
        logger.debug(f'slope_angle = {slope_angle}, Bull trend = {slope_angle > 0.0 and slope_angle > min_slope}, Bear trend = {slope_angle < 0.0 and slope_angle < (min_slope * (-1))}')
        if slope_angle > 0.0 and slope_angle > min_slope:
            result = MarketTrend.BULL
        elif slope_angle < 0.0 and slope_angle < (min_slope * (-1)):
            result = MarketTrend.BEAR
        logger.debug(f'result = {result}')
        return result

    def _get_energy_choppiness_index(self, time_frame):
        timeperiod = 14
        periods = 5
        result = MarketEnergy.NOT_SIGNIFICANT
        symbol_tf = f"{self.symbol}_{time_frame}"
        data = self.historic_data[symbol_tf]['data'].copy()
        df = convert_historic_bars_to_dataframe(data)
        close_prices = df['close']
        chopp_values = choppiness_index.calculate(df['high'], df['low'], df['close'], timeperiod)
        chopp_values = chopp_values[-periods:]
        last_candle = periods-1
        last_value = chopp_values[last_candle]
        logger.debug(f'time_frame = {time_frame}, choppiness index last value = {last_value}')

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

        logger.debug(f'result = {result}, last_value = {last_value}')
        return result, last_value

    def _get_market_trend(self):
        anchor_minim_energy_level = 40.0
        middle_minim_energy_level = 45.0
        logger.info("_get_market_trend() -> Starts")
        result = MarketTrend.UNDEFINED
        anchor_trend = self._get_trend_from_timeframe(self.timeframe, anchor_minim_energy_level)
        if anchor_trend != MarketTrend.UNDEFINED:
            middle_trend = self._get_trend_from_timeframe("H1", middle_minim_energy_level)
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

    def calculate_trend(self, historic_data):
        logger.info(f"DivergentT1 -> calculate_trend()")
        self._market_trend = MarketTrend.UNDEFINED
        self._box_high_limit = 0.0
        self._box_low_limit = 0.0
        self.historic_data = self._validate_historic_data(historic_data)

        # Manage current open orders
        if self._is_ongoing():
            self.manage_orders()
        elif self.historic_data is not None:
            # Open orders only if there isn't any open trade for the strategy
            self._market_trend = self._get_market_trend()

        box_periods = 10
        if self._market_trend == MarketTrend.BULL or self._market_trend == MarketTrend.BEAR:
            self._box_high_limit, self._box_low_limit = self._get_box_higher_lower("M15", box_periods)

    def check_signal_from_historic_bar(self, historic_data):
        data = historic_data[f'{self.symbol}_{self.signal_timeframe}']['data'].copy()
        df = convert_historic_bars_to_dataframe(data)
        ask = df['high'][-1]
        bid = df['low'][-1]
        self.check_signal(ask,bid)

    def check_signal(self, ask = None, bid = None):
        # Parameters are received only in case of backtesting.
        if ask is None and bid is None:
            ask = self.smart_trader.dma.market_data[self.symbol]['ask']
            bid = self.smart_trader.dma.market_data[self.symbol]['bid']

            if self._market_trend == MarketTrend.BULL and ask >= self._box_high_limit:
                self._open_orders(SignalType.BUY)
            elif self._market_trend == MarketTrend.BEAR and bid <= self._box_low_limit:
                self._open_orders(SignalType.SELL)
        else:
            # For backtesting (due the information ask and bid are high and low of signal_tf instead of tick data), we check that both limits where not riched.
            # It could reduce the number of signals but it's better for performance.
            if self._market_trend == MarketTrend.BULL and ask >= self._box_high_limit and not (bid <= self._box_low_limit):
                self._open_orders(SignalType.BUY)
            elif self._market_trend == MarketTrend.BEAR and bid <= self._box_low_limit and not (ask >= self._box_high_limit):
                self._open_orders(SignalType.SELL)

    def manage_orders(self):
        # TODO: implement manage_orders() -> trailing stoploss / hidden take profit or stop loss.
        dummy = 1
