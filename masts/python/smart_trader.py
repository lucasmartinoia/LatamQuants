from time import sleep
from random import random
from datetime import datetime, timedelta
from api.dwx_client import dwx_client
from indicators.macd_platinum_v2 import macd_platinum_v2
from python.common.conversions import convert_periods_to_datetime_range, \
    get_lasts_from_dictionary
from python.common.logging_config import setup_logging, logger
from backtesting.backtesting import backtesting
import json
from python.strategies.divergent_t1 import DivergentT1
from python.strategies.istrategy import IStrategy, SignalType, MarketTrend
from python.common.output import add_trade_to_file
from python.common.graphics import graph_trading_results
from python.common.calculus import calculate_trailing_stop, get_pip_value
from python.common.risk_management import RiskManagement

"""

Example dwxconnect client in python


This example client will subscribe to tick data and bar data. It will also request historic data. 

!!! ----- IMPORTANT ----- !!!

If open_test_trades=True, it will open many trades. 
Please only run this on a demo account!

!!! ----- IMPORTANT ----- !!!

"""

""" =====================================================================================================
    DWX - CLASS AND EVENTS
    =====================================================================================================
"""


class tick_processor():

    def __init__(self, mode,
                 back_test_start=None,
                 back_test_end=None,
                 back_test_directory_path=None,
                 back_test_balance=None,
                 back_test_currency=None,
                 back_test_leverage=None,
                 back_test_execution_commission_rate=0.005,
                 back_test_spread_pips=1.0,
                 MT4_directory_path=None,
                 time_delta_hours=5,
                 sleep_delay=0.005,  # 5 ms for time.sleep()
                 max_retry_command_seconds=10,  # retry to send the command for 10 seconds if not successful.
                 verbose=True,
                 balance_initial_amount=0.0,
                 balance_currency="EUR",
                 max_risk_perc=5.0,
                 max_drawdown_perc=20.0,
                 strategies=None
                 ):
        self.validate_parameters(mode, back_test_start, back_test_end, back_test_directory_path, MT4_directory_path)

        # store params
        self.mode = mode
        self.back_test_start = datetime.strptime(back_test_start, '%Y-%m-%d %H:%M:%S')
        self.back_test_end = datetime.strptime(back_test_end, '%Y-%m-%d %H:%M:%S')
        self.back_test_directory_path = back_test_directory_path
        self.back_test_execution_commission_rate = back_test_execution_commission_rate
        self.back_test_spread_pips = back_test_spread_pips
        self.MT4_directory_path = MT4_directory_path
        self.sleep_delay = sleep_delay
        self.max_retry_command_seconds = max_retry_command_seconds
        self.verbose = verbose
        self.time_delta_hours = time_delta_hours
        self.strategies_info = strategies
        self.balance_initial_amount = balance_initial_amount
        self.balance_currency = balance_currency
        self.max_risk_perc = max_risk_perc
        self.max_drawdown_perc = max_drawdown_perc

        # private info
        self.last_open_time = datetime.utcnow()
        self.last_modification_time = datetime.utcnow()

        # private variables
        self.stop_trading = False
        self.minute_counter = 0
        self.historic_request_last_timestamp = {}  # Used to control when all historic requests for a symbol were completed to inform the strategies related.
        self.historic_data = {}  # {'EURUSD_H4': {'timestamp': 97779788, 'data': data}, 'GBPUSD': {'timestamp': 97779788, 'data': data}}
        self.required_suscriptions = {}  # {'EURUSD_H4': ['strategy_id1', 'strategy_id2',..., 'strategy_idn'], 'GBPUSD_M5': ['strategy_idx1', 'strategy_idx2',..., 'strategy_idn']}
        self.required_historic_bars = {}  # {'EURUSD_H4': {'max_bars': 240, 'strategies': {'strategy_id1': bars. 'strategy_id2': bars2}}}
        self.strategies_instances = {}  # {strategy.id: {'instance': instance, 'params': params}}
        self.orders = {}
        self.output_filename = f'../output/trades_{datetime.now().strftime("%Y%m%d_%H%M%S")}_{self.mode}.txt'
        self.output_next_trade_index = 0

        # set DMA depending the mode.
        if self.mode == "live":
            self.dma = dwx_client(self, MT4_directory_path, sleep_delay,
                                  max_retry_command_seconds, verbose=verbose)
            sleep(1)
        elif self.mode == "backtest":
            self.dma = backtesting(self.back_test_start,
                                   self.back_test_end,
                                   self,
                                   back_test_directory_path,
                                   back_test_balance,
                                   back_test_currency,
                                   back_test_leverage)

        # set Risk Management Module.
        self.risk_management = RiskManagement(self.dma, self.balance_initial_amount, self.balance_currency, self.max_risk_perc, self.max_drawdown_perc)

        logger.info(f"Account info: {self.dma.account_info}")
        self.init_strategies()
        self.request_suscriptions()
        # For backtesting - Load historic data
        if self.mode == 'backtest':
            self.dma.load_historic_bars(self.required_historic_bars)
            self.dma.output_filename = self.output_filename
        self.dma.start()
        logger.info("Smart Trader has finished!")

    def get_strategy_instance(self, strategy_name, strategy_params):
        result = None
        if strategy_name == 'DivergentT1':
            result = DivergentT1(self, **strategy_params)
        return result

    def init_strategies(self):
        main_strategy_symbol_tfs = []
        symbol_specs = {}
        for strategy_name, strategy_params in self.strategies_info.items():
            # Add pip_value to the symbol_spec
            strategy_params['symbol_spec']['pip_value'] = get_pip_value(strategy_params['symbol_spec']['digits'])

            # Create strategy instance
            instance = self.get_strategy_instance(strategy_name, strategy_params)
            self.strategies_instances[instance.id] = {'instance': instance, 'params': strategy_params}

            # Add to subscriptions
            symbol_tf = f"{strategy_params['symbol']}_TICK"
            self.add_strategy_required_suscription(symbol_tf, instance.id)
            symbol_tf = f"{strategy_params['symbol']}_{strategy_params['timeframe']}"
            self.add_strategy_required_suscription(symbol_tf, instance.id)
            main_strategy_symbol_tfs.append(symbol_tf)

            # Add to required historic data
            strategy_required_hist_data = instance.required_data
            for hist_symbol_tf, hist_bars in strategy_required_hist_data.items():
                if hist_symbol_tf in self.required_historic_bars:
                    self.required_historic_bars[hist_symbol_tf] = self.required_historic_bars[hist_symbol_tf][
                        'strategies'].append(instance.id)
                    if self.required_historic_bars[hist_symbol_tf]['max_bars'] < hist_bars:
                        self.required_historic_bars[hist_symbol_tf]['max_bars'] = hist_bars
                else:
                    self.required_historic_bars[hist_symbol_tf] = {'max_bars': hist_bars,
                                                                   'strategies': {instance.id: hist_bars}}
            symbol_specs[strategy_params['symbol']] = strategy_params['symbol_spec']

        self.dma.symbol_specs = symbol_specs
        if self.mode == "backtest":
            self.dma.main_symbol_tfs = main_strategy_symbol_tfs

    def add_strategy_required_suscription(self, symbol_tf, strategy_id):
        if symbol_tf in self.required_suscriptions:
            self.required_suscriptions[symbol_tf] = self.required_suscriptions[symbol_tf].append(strategy_id)
        else:
            self.required_suscriptions[symbol_tf] = [strategy_id]

    def request_suscriptions(self):
        symbols_tick = []
        symbols_bar = []
        for symbol_tf, strategy_id in self.required_suscriptions.items():
            symbol, timeframe = symbol_tf.split('_')
            if timeframe == 'TICK':
                symbols_tick.append(symbol)
            else:
                symbols_bar.append([symbol, timeframe])
        # subscribe to tick data:
        self.dma.subscribe_symbols(symbols_tick)
        # subscribe to bar data:
        self.dma.subscribe_symbols_bar_data(symbols_bar)

    def get_historic_bars(self, symbol, timeframe, periods, current_datetime=None):
        delta_fix = 2
        if self.mode != 'live':
            delta_fix = 0
        if current_datetime == None:
            current_datetime = self.get_current_datetime()
        start_datetime, end_datetime = convert_periods_to_datetime_range(periods, timeframe, current_datetime)
        end_datetime = end_datetime + timedelta(hours=delta_fix)
        # logger.debug(f'get_historic_bars() -> {symbol} {timeframe} {periods}')
        # logger.debug(f"call -> get_historic_data({symbol}, {timeframe}, {start_datetime}, {end_datetime})")
        symbol_tf = f"{symbol}_{timeframe}"
        self.dma.get_historic_data(symbol, timeframe, start_datetime.timestamp(), end_datetime.timestamp())

    def get_current_datetime(self):
        result = None
        if self.mode == "live":
            result = datetime.utcnow() + timedelta(hours=self.time_delta_hours)
        else:
            result = self.dma.GetCurrentTime()
        return result

    def validate_parameters(self, mode,
                            back_test_start,
                            back_test_end,
                            back_test_directory_path,
                            MT4_directory_path):

        if mode == "backtest":
            if back_test_start == None:
                raise Exception("back_test_start is required")
            elif back_test_end == None:
                raise Exception("back_test_end is required")
            elif back_test_end <= back_test_start:
                raise Exception("back_test_end cannot be lower or equal to back_test_start")
            elif back_test_directory_path == None:
                raise Exception("back_test_directory_path is required")
        elif mode == "live":
            if MT4_directory_path == None:
                raise Exception("MT4_directory_path is required")
        else:
            raise Exception("mode parameter is not 'backtest' neither 'live'")

    def on_tick(self, symbol, bid, ask):
        now = datetime.utcnow()
        keys = [key for key, value in self.strategies_instances.items() if
                value['params']['symbol'] == symbol]
        for strategy_key in keys:
            self.strategies_instances[strategy_key]['instance'].manage_orders()

        # to test trading. 
        # this will randomly try to open and close orders every few seconds. 
        # if self.open_test_trades:
        #     if now > self.last_open_time + timedelta(seconds=3):
        #
        #         self.last_open_time = now
        #
        #         order_type = 'buy'
        #         price = ask
        #         if random() > 0.5:
        #             order_type = 'sell'
        #             price = bid
        #
        #         self.dma.open_order(symbol=symbol, order_type=order_type,
        #                             price=price, lots=0.5)
        #
        #     if now > self.last_modification_time + timedelta(seconds=10):
        #
        #         self.last_modification_time = now
        #
        #         for ticket in self.dma.open_orders.keys():
        #             self.dma.close_order(ticket, lots=0.1)
        #
        #     if len(self.dma.open_orders) >= 10:
        #         self.dma.close_all_orders()
        #         # self.dwx.close_orders_by_symbol('GBPUSD')
        #         # self.dwx.close_orders_by_magic(0)

    def on_bar_data(self, symbol, time_frame, time, open_price, high, low, close_price, tick_volume):
        # logger.debug(f'current_datetime -> {self.get_current_datetime(symbol)}')
        logger.debug(
            f'on_bar_data() => {symbol}, {time_frame}, time:{time}, open:{open_price}, high:{high}, low:{low}, close:{close_price}, vol:{tick_volume}')
        # logger.debug(f'bar_data: {self.dma.bar_data}')
        # logger.debug(f'market_data: {self.dma.market_data}')

        # Manage trailing stop loss orders
        self.process_trailing_stop_loss()

        self.request_historic_data(symbol, time_frame)

        # if self.minute_counter == 1:
        #     self.dma.open_order(symbol='EURUSD', order_type='buylimit', lots=0.2, price=1.11270)
        # elif self.minute_counter == 2:
        #     ticket_no, order_data = self.dma.open_orders.popitem()
        #     self.dma.modify_order(ticket_no, 0.01, 1.11260, 1.10000, 1.40000)
        # elif self.minute_counter == 3:
        #     ticket_no, order_data = self.dma.open_orders.popitem()
        #     self.dma.close_order(ticket_no)
        # elif self.minute_counter == 4:
        #     self.dma.get_historic_trades(30)

        # if not self.stop_trading:
        #     self.dma.open_order(symbol='EURUSD', order_type='buylimit',
        #                         price=1.108933, lots=0.1)
        #     self.dma.open_order(symbol='EURUSD', order_type='sell', lots=0.3)
        #     self.dma.open_order(symbol='EURUSD', order_type='selllimit',
        #                         price=1.108933, lots=0.4)
        #     self.stop_trading = True

    def request_historic_data(self, symbol, time_frame):
        self.historic_request_last_timestamp[symbol] = self.get_current_datetime().timestamp()
        keys_symbol_tf = [key for key, value in self.required_historic_bars.items() if key.startswith(symbol)]
        for key_symbol_tf in keys_symbol_tf:
            key_symbol, key_tf = key_symbol_tf.split('_')
            bars = self.required_historic_bars[key_symbol_tf]['max_bars']
            self.get_historic_bars(key_symbol, key_tf, bars)

    def send_historic_data_to_strategies(self, symbol):
        updated_symbol_tfs = [key for key, value in self.historic_data.items() if
                              key.startswith(symbol) and value['timestamp'] == self.historic_request_last_timestamp[
                                  symbol]]
        all_symbol_tfs = [key for key, value in self.historic_data.items() if key.startswith(symbol)]
        if len(updated_symbol_tfs) == len(all_symbol_tfs):  # all historic requests for the symbol were completed.
            historic_data_to_send = dict(filter(lambda item: item[0] in all_symbol_tfs, self.historic_data.items()))
            keys = [key for key, value in self.strategies_instances.items() if
                    value['params']['symbol'] == symbol]
            for strategy_key in keys:
                self.strategies_instances[strategy_key]['instance'].execute(historic_data_to_send)

    def on_historic_data(self, symbol, time_frame, data):
        symbol_tf = f"{symbol}_{time_frame}"
        # Cut bars to only required ones. DISABLED BECAUSE EMA_240 ISSUE!!!
        # data = get_lasts_from_dictionary(data, self.required_historic_bars[symbol_tf]['max_bars'])
        # Store data.
        self.historic_data[f'{symbol}_{time_frame}'] = {'timestamp': self.historic_request_last_timestamp[symbol],
                                                        'data': data}
        logger.debug(
            f'on_historic_data() => {symbol}, {time_frame}, {len(data)} bars, last bar datetime -> {list(data.keys())[-1]}, current datetime -> {self.get_current_datetime()}')
        self.send_historic_data_to_strategies(symbol)

        # # Example about how to call an indicator.
        # close_prices = convert_historic_bars_element_to_array('close', data)
        # volumes = convert_historic_bars_element_to_array('tick_volume', data)
        # self.macd_plat = macd_platinum_v2(close_prices, volumes)
        # blueMACD, orgMACD, hist = self.macd_plat.calculate_macd()
        # logger.debug(f'blueMACD: {blueMACD}')
        # logger.debug(f'orgMACD: {orgMACD}')
        # logger.debug(f'hist: {hist}')

    def on_historic_trades(self):
        logger.debug(f'historic_trades: {len(self.dma.historic_trades)}')
        logger.debug(self.dma.historic_trades)
        self.inform_historic_trades()

    def inform_historic_trades(self):
        max_len = len(self.dma.historic_trades)
        while self.output_next_trade_index < max_len:
            add_trade_to_file(self.output_filename, self.dma.historic_trades[self.output_next_trade_index][1])
            self.output_next_trade_index = self.output_next_trade_index + 1

    def on_message(self, message):
        if message['type'] == 'ERROR':
            logger.debug(f"{message['type']}|{message['error_type']}|{message['description']}")
        elif message['type'] == 'INFO':
            logger.debug(f"{message['type']}|{message['message']}")
            # Log closed or canceled order.
            if 'closed' in message['message']:
                self.dma.get_historic_trades(100000)

    # triggers when an order is added or removed, not when only modified.
    def on_order_event(self):
        logger.debug(f'on_order_event. open_orders: {len(self.dma.open_orders)} open orders')
        logger.debug(self.dma.open_orders)

    def get_strategy_orders(self, magic_no):
        strategy_orders = [(ticket_no, trade_data) for ticket_no, trade_data in self.dma.open_orders.items() if
                           trade_data.get('magic') == magic_no]
        return strategy_orders

    def process_trailing_stop_loss(self):
        tsl_orders = [(ticket_no, trade_data) for ticket_no, trade_data in self.dma.open_orders.items() if
                      trade_data.get('comment').find('tsl=') > -1]

        for ticket_no, trade_data in tsl_orders:
            margin_points = float(trade_data['comment'].replace('tsl=', ""))
            new_sl = calculate_trailing_stop(trade_data, self.dma.market_data[trade_data['symbol']], margin_points)
            if new_sl is not None:
                self.dma.modify_order(ticket=ticket_no, take_profit=trade_data['TP'], stop_loss=new_sl)


""" =====================================================================================================
    PROCESS EVENTS FOR DWX AND BACKTESTING
    =====================================================================================================
"""


class smart_trader():

    def __init__(self, dma):
        self.dma = dma

    def on_tick(self, symbol, bid, ask):
        now = datetime.utcnow()
        logger.debug(f'on_tick: {symbol} {bid} {ask}')

        # to test trading.
        # this will randomly try to open and close orders every few seconds.
        if self.open_test_trades:
            if now > self.last_open_time + timedelta(seconds=3):

                self.last_open_time = now

                order_type = 'buy'
                price = ask
                if random() > 0.5:
                    order_type = 'sell'
                    price = bid

                self.dwx.open_order(symbol=symbol, order_type=order_type,
                                    price=price, lots=0.5)

            if now > self.last_modification_time + timedelta(seconds=10):

                self.last_modification_time = now

                for ticket in self.dwx.open_orders.keys():
                    self.dwx.close_order(ticket, lots=0.1)

            if len(self.dwx.open_orders) >= 10:
                self.dwx.close_all_orders()
                # self.dwx.close_orders_by_symbol('GBPUSD')
                # self.dwx.close_orders_by_magic(0)


""" =====================================================================================================
    SMART TRADER - MAIN
    =====================================================================================================
"""
setup_logging()
logger.info('STARTED')

# # FXOpen Demo Account
# config_file_path = "smart_trader_fxopen_demo.config"
# sleep_seconds = 1

# Backtesting
config_file_path = "smart_trader_backtesting.config"
sleep_seconds = 0

# Read the configuration file and parse its contents into a dictionary
with open(config_file_path, "r") as file:
    config_data = json.load(file)
parameters = config_data['tick_processor_params']
processor = tick_processor(**parameters)

while processor.dma.ACTIVE:
    sleep(sleep_seconds)
