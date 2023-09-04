import os
import json
from time import sleep
from threading import Thread, Lock
from os.path import join, exists
from traceback import print_exc
from datetime import datetime, timedelta
from python.common.logging_config import logger
from python.common.conversions import convert_bar_dataframe_to_dict, get_timeframe_delta, get_bar_data_clean_date
from python.common.graphics import graph_trading_results
import pandas as pd
from enum import Enum
from collections import deque
from forex_python.converter import CurrencyRates
from decimal import Decimal
from python.common.files import get_bar_data_file_name, find_file


class OrderStatus(Enum):
    PENDING = 0
    OPEN = 1
    CLOSED = 2
    CANCELED = 3


"""
This class includes all of the functions needed backtesting. 
"""


class backtesting():
    def __init__(self, start_datetime,
                 end_datetime,
                 event_handler=None,
                 back_test_directory_path=None,
                 balance=100000.0,
                 currency='USD',
                 leverage=33,
                 execution_commission_rate=0.005,
                 back_test_spread_pips=1.0
                 ):

        logger.info("backtesting.__init__()")

        if not exists(back_test_directory_path):
            logger.error('back_test_directory_path does not exist!')
            raise Exception('back_test_directory_path does not exist!')
            exit()
        else:
            self.data_path = back_test_directory_path

        # Init variables
        self.dict_tickdata = {}
        self.dict_bardata = {}
        self.dict_bardata_index = {}
        self.dict_bardata_index_prev = {}
        self.dict_trades = {}
        self.open_orders = {}
        self.historic_trades = {}
        self.last_ticket_no = 0
        self.buy_order_types = ['buy', 'buystop', 'buylimit']
        self.sell_order_types = ['sell', 'sellstop', 'selllimit']
        self.sorted_tick_moment_list = deque()
        self.bar_data = {}
        self.market_data = {}
        self.bar_data_subscription_requests = None
        self.main_symbol_tfs = None
        self.symbol_specs = None
        self.current_datetime = start_datetime
        self.output_filename = None

        # Store parameters
        self.start_datetime = start_datetime
        self.end_datetime = end_datetime
        self.event_handler = event_handler
        self.account_info = {'name': 'backtesting_mode', 'number': 1111, 'currency': currency, 'leverage': leverage,
                             'free_margin': balance, 'balance': balance, 'equity': balance}
        self.execution_commission_rate = execution_commission_rate
        self.back_test_spread_pips = back_test_spread_pips

        # implements
        # self.open_orders # Current open orders, pending and opened. Order ticket is the key.
        # self.market_data # Symbol is the key.
        # self.bar_data # Contains the latest bar data. This is updated continually if subscribed to specific bar data.
        # self.historic_trades # Contains the requested trade history, which is only updated after a request for historic trades
        # self.historic_data # Lastest historic data required.

        self.ACTIVE = True
        self.START = False

    """START can be used to check if the client has been initialized.  
    """

    def start(self):
        self.START = True
        init = 1

        # Main backtesting loop - multi symbol in parallel
        while self.START:
            process = False

            if init == 1:
                # Set indexes for each bar_data the first time
                for symbol_tf in self.main_symbol_tfs:
                    symbol, timeframe = self.extract_symbol_and_timeframe(symbol_tf)
                    bar_data_index = self.get_bar_data_index_for_date(self.dict_bardata[symbol_tf], self.start_datetime,
                                                                      timeframe)
                    self.dict_bardata_index[symbol_tf] = bar_data_index
                    self.dict_bardata_index_prev[symbol_tf] = bar_data_index
                    if bar_data_index is not None and init == 1:
                        self.current_datetime = get_bar_data_clean_date(self.start_datetime, timeframe)
                        process = True
                        self.process_symbol_tf_main_bar(symbol_tf)
                    init = 0
            else:  # Increment indexes
                for symbol_tf in self.main_symbol_tfs:
                    symbol_index = self.dict_bardata_index[symbol_tf]
                    if symbol_index is not None and self.dict_bardata[symbol_tf].shape[0] > (symbol_index + 1):
                        self.dict_bardata_index_prev[symbol_tf] = symbol_index
                        symbol_index += 1
                        self.dict_bardata_index[symbol_tf] = symbol_index
                        self.current_datetime = self.dict_bardata[symbol_tf]['DateTime'][symbol_index]
                        process = True
                        self.process_symbol_tf_main_bar(symbol_tf)
                    elif symbol_index is not None:
                        # Close all open orders
                        self.close_all_orders()
                        self.dict_bardata_index[symbol_tf] = None
                        process = False
            self.START = process

        for symbol_tf in self.main_symbol_tfs:
            symbol, timeframe = self.extract_symbol_and_timeframe(symbol_tf)
            bar_data_file_name = get_bar_data_file_name(self.data_path, symbol, timeframe)
            graph_trading_results(bar_data_file_name, symbol, timeframe, self.start_datetime, self.end_datetime, self.output_filename)

        self.ACTIVE = False

    def process_symbol_tf_main_bar(self, symbol_tf):
        symbol, timeframe = self.extract_symbol_and_timeframe(symbol_tf)
        bar_data = self.dict_bardata[symbol_tf].iloc[[self.dict_bardata_index[symbol_tf]]]
        self.market_data[symbol] = {'bid': bar_data['Open'].iloc[0],
                                    'ask': bar_data['Open'].iloc[0],
                                    'tick_value': 1}
        # Update orders in the broker
        self.manage_orders(symbol, symbol_tf)
        # Trigger bar data events
        self.update_bar_datas(symbol, symbol_tf)

    def extract_symbol_and_timeframe(self, input_string):
        parts = input_string.split('_')
        if len(parts) != 2:
            raise ValueError("Invalid input format. The format should be <symbol>_<timeframe>.")

        symbol, timeframe = parts
        return symbol, timeframe

    def update_bar_datas(self, param_symbol, main_symbol_tf):
        # Get current main data bar info
        _, main_timeframe = self.extract_symbol_and_timeframe(main_symbol_tf)
        bar_data = self.dict_bardata[main_symbol_tf]
        bar_data_index = self.dict_bardata_index[main_symbol_tf]
        # Trigger on_bar_data event
        self.event_handler.on_bar_data(param_symbol, main_timeframe, bar_data['DateTime'][bar_data_index],
                                       bar_data['Open'][bar_data_index],
                                       bar_data['High'][bar_data_index], bar_data['Low'][bar_data_index],
                                       bar_data['Close'][bar_data_index],
                                       bar_data['Volume'][bar_data_index])
        # Process all data bars with same symbol but higher timeframe
        for symbol_tf in self.dict_bardata.keys():
            symbol, timeframe = self.extract_symbol_and_timeframe(symbol_tf)
            if symbol_tf != main_symbol_tf and timeframe < main_timeframe:  # Only set index for higher timeframes.
                if symbol == param_symbol:
                    prev_datetime = \
                        self.dict_bardata[main_symbol_tf].iloc[self.dict_bardata_index_prev[main_symbol_tf]][
                            'DateTime']
                    curr_datetime = self.dict_bardata[main_symbol_tf].iloc[self.dict_bardata_index[main_symbol_tf]][
                        'DateTime']

                    if self.has_bar_data_changed(prev_datetime, curr_datetime, timeframe):
                        bar_data_index = self.get_bar_data_index_for_date(self.dict_bardata[symbol_tf], curr_datetime,
                                                                          timeframe)
                        if bar_data_index is not None and bar_data_index > self.dict_bardata_index[symbol_tf]:
                            self.dict_bardata_index[symbol_tf] = bar_data_index
                            bar_data = self.dict_bardata[symbol_tf].iloc[self.dict_bardata_index[symbol_tf]]
                            self.bar_data[symbol_tf] = {'time': bar_data['DateTime'].strftime('%Y-%m-%d %H:%M:%S'),
                                                        'open': bar_data['Open'], 'high': bar_data['High'],
                                                        'low': bar_data['Low'], 'close': bar_data['Close'],
                                                        'tick_volume': bar_data['Volume']}
                            if symbol_tf in self.bar_data_subscription_requests:
                                self.event_handler.on_bar_data(symbol, timeframe, bar_data['DateTime'],
                                                               bar_data['Open'],
                                                               bar_data['High'], bar_data['Low'], bar_data['Close'],
                                                               bar_data['Volume'])

    def has_bar_data_changed(self, previous_datetime, current_datetime, timeframe):
        if previous_datetime is None or current_datetime is None:
            raise ValueError(
                f"Invalid previous_datetime {previous_datetime} and/or current_datetime {current_datetime}")

        if current_datetime < previous_datetime:
            logger.error(
                f"has_bar_data_changed() error: current_datetime {current_datetime} cannot be earlier than previous_datetime {previous_datetime}")
            raise ValueError(
                f"has_bar_data_changed() error: current_datetime {current_datetime} cannot be earlier than previous_datetime {previous_datetime}")

        timeframe_interval = get_timeframe_delta(timeframe)
        elapsed_time = current_datetime - previous_datetime
        # Check if the elapsed time is greater than or equal to the specified timeframe
        if elapsed_time >= timeframe_interval:
            return True
        else:
            # Check if the current_datetime indicates a new day, hour, half, or quarter new windows
            if timeframe == 'D1' and current_datetime.date() != previous_datetime.date():
                return True
            elif timeframe in [
                'H4'] and current_datetime.hour != previous_datetime.hour and current_datetime.hour % 4 == 0:
                return True
            elif timeframe in ['H1'] and current_datetime.hour != previous_datetime.hour:
                return True
            elif timeframe in [
                'M30'] and current_datetime.minute != previous_datetime.minute and current_datetime.minute % 30 == 0:
                return True
            elif timeframe in [
                'M15'] and current_datetime.minute != previous_datetime.minute and current_datetime.minute % 15 == 0:
                return True
            elif timeframe in [
                'M5'] and current_datetime.minute != previous_datetime.minute and current_datetime.minute % 5 == 0:
                return True
            elif timeframe in ['M1'] and current_datetime.minute != previous_datetime.minute:
                return True
            else:
                return False

    def get_tick_data_index_for_date(self, df, date_time):
        filtered_rows = df[df["DateTime"] >= date_time]
        if not filtered_rows.empty:
            return filtered_rows.index[0]

    def get_bar_data_index_for_date(self, dict, dt, timeframe):
        clean_date = get_bar_data_clean_date(dt, timeframe)
        filtered_rows = dict[dict["DateTime"] == clean_date]
        if not filtered_rows.empty:
            return filtered_rows.index[0]


    """Sends a SUBSCRIBE_SYMBOLS command to subscribe to market (tick) data.

    Args:
        symbols (list[str]): List of symbols to subscribe to.
    
    Returns:
        None

        The data will be stored in self.market_data. 
        On receiving the data the event_handler.on_tick() 
        function will be triggered. 
    
    """

    def subscribe_symbols(self, symbols):
        self.load_tickdata(symbols)

    def load_tickdata(self, symbols):
        for symbol in symbols:
            self.load_tickdata_file(symbol)

    def load_tickdata_file(self, symbol):
        search_for = f"{symbol}_TICK_UTCPlus03-TICK"
        file_name = find_file(search_for, self.data_path)
        if file_name == None:
            logger.error(f"Tickdata file for {search_for} not found!")
            raise Exception(f"Tickdata file for {search_for} not found!")
            exit()
        else:
            df = pd.read_csv(file_name)
            df['DateTime'] = pd.to_datetime(df['DateTime'], format='%Y%m%d %H:%M:%S.%f')
            if self.check_data_dates(df, self.start_datetime, self.end_datetime):
                self.dict_tickdata.setdefault(symbol, df)
                self.dict_tickdata.setdefault(symbol, 0)

    def set_main_symbol_tfs(self, symbol_tfs):
        self.main_symbol_tfs = symbol_tfs

    def check_data_dates(self, df, start_time, end_time):
        result = False
        first_row_datetime = df.iloc[0]['DateTime']
        last_row_datetime = df.iloc[-1]['DateTime']
        if start_time < first_row_datetime:
            logger.error(f"start_time ({start_time}) is lower than first row datetime ({first_row_datetime})")
            raise Exception(f"start_time ({start_time}) is lower than first row datetime ({first_row_datetime})")
            exit()
        elif end_time > last_row_datetime:
            logger.error(f"end_time ({end_time}) is higher than last row datetime ({last_row_datetime})")
            raise Exception(f"end_time ({end_time}) is higher than last row datetime ({last_row_datetime})")
            exit()
        else:
            result = True
        return result

    def subscribe_symbols_bar_data(self, symbolTimes):
        self.bar_data_subscription_requests = [f"{pair[0]}_{pair[1]}" for pair in symbolTimes]
        for st in symbolTimes:
            self.load_bardata_file(st)

    def load_bardata_file(self, symbolTime):
        file_name = get_bar_data_file_name(self.data_path, symbolTime[0], symbolTime[1])
        if file_name == None:
            logger.error(f"Bardata file for {search_for} not found!")
            raise Exception(f"Bardata file for {search_for} not found!")
            exit()
        else:
            df = pd.read_csv(file_name)
            df['DateTime'] = pd.to_datetime(df['Date'].astype(str) + ' ' + df['Time'])
            df = df.drop(['Date', 'Time'], axis=1)
            if self.check_data_dates(df, self.start_datetime, self.end_datetime):
                new_key = f'{symbolTime[0]}_{symbolTime[1]}'
                self.dict_bardata.setdefault(new_key, df)
                self.dict_bardata_index.setdefault(new_key, 0)

    def load_historic_bars(self, required_historic_bars):
        self.bar_data_historic_requests = required_historic_bars.keys()
        for symbol_tf in self.bar_data_historic_requests:
            if symbol_tf not in self.dict_bardata.keys():
                self.load_bardata_file(symbol_tf.split('_'))

    """Sends a GET_HISTORIC_DATA command to request historic data. 
    
    Kwargs:
        symbol (str): Symbol to get historic data.
        time_frame (str): Time frame for the requested data.
        start (int): Start timestamp (seconds since epoch) of the requested data.
        end (int): End timestamp of the requested data.
    
    Returns:
        None

        The data will be stored in self.historic_data. 
        On receiving the data the event_handler.on_historic_data()
        function will be triggered. 
    """

    def get_historic_data(self,
                          symbol='EURUSD',
                          time_frame='D1',
                          param_start=(datetime.utcnow() - timedelta(days=30)).timestamp(),
                          param_end=datetime.utcnow().timestamp()):
        start = datetime.fromtimestamp(param_start)
        end = datetime.fromtimestamp(param_end)
        # logger.debug(f"-> get_historic_data({symbol}, {time_frame}, {start}, {end})")
        symbol_tf = f"{symbol}_{time_frame}"
        if symbol_tf in self.dict_bardata:
            if self.check_data_dates(self.dict_bardata[symbol_tf], start, end):
                # logger.info(self.dict_bardata[symbol_tf])
                result = convert_bar_dataframe_to_dict(self.dict_bardata[symbol_tf], start, end)
                # logger.info(f"get_historic_data() -> {result}")
                self.event_handler.on_historic_data(symbol, time_frame, result)
        else:
            logger.error(f"No historic data for {symbol} {time_frame}!")
            raise Exception(f"No historic data for {symbol} {time_frame}!")
            exit()

    """Sends a GET_HISTORIC_TRADES command to request historic trades.
    
    Kwargs:
        lookback_days (int): Days to look back into the trade history. The history must also be visible in MT4. 
    
    Returns:
        None

        The data will be stored in self.historic_trades. 
        On receiving the data the event_handler.on_historic_trades() 
        function will be triggered. 
    """

    def get_historic_trades(self, lookback_days=30):
        self.historic_trades = [(ticket_no, trade_data) for ticket_no, trade_data in
                                self.dict_trades.items() if
                                (trade_data.get('status') == OrderStatus.CLOSED or trade_data.get(
                                    'status') == OrderStatus.CANCELED)]
        self.event_handler.on_historic_trades()

    """Sends an OPEN_ORDER command to open an order.

    Kwargs:
        symbol (str): Symbol for which an order should be opened. 
        order_type (str): Order type. Can be one of:
            'buy', 'sell', 'buylimit', 'selllimit', 'buystop', 'sellstop'
        lots (float): Volume in lots
        price (float): Price of the (pending) order. Can be zero 
            for market orders. 
        stop_loss (float): SL as absoute price. Can be zero 
            if the order should not have an SL. 
        take_profit (float): TP as absoute price. Can be zero 
            if the order should not have a TP.  
        magic (int): Magic number
        comment (str): Order comment
        expiration (int): Expiration time given as timestamp in seconds. 
            Can be zero if the order should not have an expiration time.  
    
    """

    def open_order(self, symbol='EURUSD',
                   order_type='buy',
                   lots=0.01,
                   price=0,
                   stop_loss=0,
                   take_profit=0,
                   magic=0,
                   comment='',
                   expiration=0):

        result = False

        # Define price for market orders
        if price == 0:
            if order_type == 'buy':
                price = self.market_data[symbol]['ask']
            elif order_type == 'sell':
                price = self.market_data[symbol]['bid']
            else:
                logger.error(f'open_order() -> price cannot be 0 for not {order_type} order type')
                raise Exception(f'open_order() -> price cannot be 0 for not {order_type} order type')
                exit()

        new_order_data = {'ticket_no': 0, 'symbol': symbol, 'type': order_type,
                          'lots': lots,
                          'price': price, 'SL': stop_loss, 'TP': take_profit, 'magic': magic,
                          'comment': comment, 'expiration': expiration, 'open_time': self.GetCurrentTime(),
                          'close_time': None, 'commission': 0.0, 'taxes': 0.0, 'swap': 0.0,
                          'pnl': 0.0, 'status': OrderStatus.PENDING, 'open_price': 0.0,
                          'close_price': 0.0}
        if self.validate_order(new_order_data):
            self.last_ticket_no = self.last_ticket_no + 1
            new_order_data['ticket_no'] = self.last_ticket_no
            self.dict_trades.setdefault(self.last_ticket_no, new_order_data)
            self.execute_order(self.last_ticket_no, new_order_data)
            result = True

        return result

    def execute_order(self, ticket_no, trade_data):
        order_type = trade_data.get('type')
        if order_type.endswith('limit') or order_type.endswith('stop'):
            self._execute_order(ticket_no, trade_data)
        else:  # Market orders input just now
            self.execute_order_on_tick(ticket_no, trade_data)

    def _get_main_tf(self, symbol):
        return next((string for string in self.main_symbol_tfs if string.startswith(symbol)), None)

    def _execute_order(self, ticket_no, trade_data, symbol_tf=None, bar_data=None):
        result = False
        if ticket_no == 34:
            dummy = 1
        main_symbol_tf = self._get_main_tf(trade_data['symbol'])
        if symbol_tf is None:
            bar_data = self.dict_bardata[main_symbol_tf].iloc[self.dict_bardata_index[main_symbol_tf]]
            self._execute_order(ticket_no, trade_data, main_symbol_tf, bar_data)
        else:
            affects = self._order_affected_by_bar(trade_data, bar_data)
            if 0 < affects < 2:
                if trade_data['status'] == OrderStatus.PENDING:
                    self._open_order(ticket_no, trade_data, bar_data['DateTime'], trade_data['price'],
                                     trade_data['price'])
                elif trade_data['status'] == OrderStatus.OPEN:
                    self._manage_order(ticket_no, trade_data, bar_data['DateTime'], bar_data['Low'], bar_data['High'])
                result = True
            elif 1 < affects:
                if main_symbol_tf == symbol_tf:
                    # Loops in M1 bars
                    symbol_tf_m1 = f'{trade_data["symbol"]}_M1'
                    init_datetime = bar_data['DateTime']
                    end_datetime = init_datetime + timedelta(minutes=self._get_minutes_from_symbol_tf(symbol_tf))

                    bars_1m = self.dict_bardata[symbol_tf_m1][
                        (self.dict_bardata[symbol_tf_m1]['DateTime'] >= init_datetime) & (
                                self.dict_bardata[symbol_tf_m1]['DateTime'] < end_datetime)]

                    pending_affects = affects
                    bar_1m_index = 0
                    while bar_1m_index < len(bars_1m) and not result:
                        bar_1m = bars_1m.iloc[bar_1m_index]
                        result1 = self._execute_order(ticket_no, trade_data, symbol_tf_m1, bar_1m)
                        if result1:
                            pending_affects -= 1
                            if pending_affects == 0:
                                result = True
                            else:
                                bar_1m_index += 1
                        else:
                            bar_1m_index += 1

                    if not result:
                        logger.error(
                            f'_execute_pending_order() -> Loop in M1 for {symbol_tf}, bar_data = {bar_data} continues with pending actions')
                        raise Exception(
                            f'_execute_pending_order() -> Loop in M1 for {symbol_tf} continues with pending actions')
                        exit()

                elif symbol_tf.endswith('M1'):
                    # TODO: implement tick exploration, in the meantime give an error and interrupts the process.
                    logger.error(
                        f'_execute_pending_order() -> Tick data analysis required for {symbol_tf}, bar_data = {bar_data}')
                    raise Exception('_execute_pending_order() -> Tick data analysis required for {symbol_tf}')
                    exit()
                else:
                    logger.error(f'_execute_pending_order() -> {symbol_tf} analysis not implemented')
                    raise Exception(f'_execute_pending_order() -> {symbol_tf} analysis not implemented')
                    exit()
        return result

    def _get_minutes_from_symbol_tf(self, symbol_tf):
        result = 0
        symbol, tf = symbol_tf.split('_')
        if tf == 'H4':
            result = 60 * 4
        elif tf == 'H1':
            result = 60
        elif tf == 'M30':
            result = 30
        elif tf == 'M5':
            result = 5
        elif tf == 'M1':
            result = 1
        return result

    def _order_affected_by_bar(self, trade_data, bar_data):
        affected_times = 0
        if trade_data['type'].endswith('limit') or trade_data['type'].endswith('stop'):
            if bar_data['Low'] <= trade_data['price'] <= bar_data['High']:
                affected_times += 1

        if affected_times == 1 or trade_data['type'] in ['buy', 'sell']:
            if bar_data['Low'] <= trade_data['SL'] <= bar_data['High']:
                affected_times += 1
            if bar_data['Low'] <= trade_data['TP'] <= bar_data['High']:
                affected_times += 1
        return affected_times

    def get_tick_data_for_date_range(self, symbol, init_datetime=None, end_datetime=None):
        if init_datetime is None:
            init_datetime = self.current_datetime
        # end_datetime:
        #   None -> means that only one tick data is required being tick_datetime >= init_datetime
        #   Any  -> means upper limit not included in the tick_data array to return.
        if end_datetime is None:
            result = self.dict_tickdata[symbol][(self.dict_tickdata[symbol]['DateTime'] >= init_datetime)].head(1)
        else:
            result = self.dict_tickdata[symbol][(self.dict_tickdata[symbol]['DateTime'] >= init_datetime) & (
                    self.dict_tickdata[symbol]['DateTime'] < end_datetime)]
        return result

    def execute_order_on_tick(self, ticket_no, trade_data):
        if trade_data['status'] == OrderStatus.PENDING:
            order_type = trade_data.get('type')
            order_symbol = trade_data['symbol']
            tick_data = self.get_tick_data_for_date_range(order_symbol, self.current_datetime)
            self._open_order(ticket_no, trade_data, tick_data['DateTime'].iloc[0], tick_data['Bid'].iloc[0],
                             tick_data['Ask'].iloc[0])

    def _open_order(self, ticket_no, trade_data, execution_datetime, market_bid_price, market_ask_price):
        order_type = trade_data.get('type')
        order_symbol = trade_data['symbol']
        if order_type.startswith('buy'):
            trade_data['type'] = 'buy'
            # not use market_ask_price because it is not having a real spread.
            trade_data['open_price'] = market_bid_price + self.symbol_specs[order_symbol]['pip_value']
        else:
            trade_data['type'] = 'sell'
            trade_data['open_price'] = market_bid_price

        trade_data['open_time'] = execution_datetime
        trade_data['status'] = OrderStatus.OPEN
        self.open_orders[ticket_no] = trade_data
        # Trigger events
        self.event_handler.on_message({'type': 'INFO',
                                       'message': f'Successfully sent order {ticket_no}: {order_symbol}, {trade_data["type"]}, {trade_data["lots"]}, {trade_data["open_price"]}'})
        self.event_handler.on_order_event()

    def manage_orders(self, symbol, symbol_tf):
        if len(self.dict_trades) > 0:
            orders = [(ticket_no, trade_data) for ticket_no, trade_data in self.dict_trades.items() if
                      trade_data.get('symbol') == symbol and
                      trade_data.get('status') in [OrderStatus.OPEN, OrderStatus.PENDING]]
            for ticket_no, trade_data in orders:
                self._execute_order(ticket_no, trade_data)

    def _manage_order(self, ticket_no, trade_data, execution_datetime, bar_low_price, bar_high_price):
        order_type = trade_data.get('type')
        order_symbol = trade_data.get('symbol')
        pip_value = self.symbol_specs[order_symbol]['pip_value']
        to_inform = False
        if order_type == 'buy':
            if trade_data.get('SL') > 0.0:
                if bar_low_price <= trade_data.get('SL'):
                    self._close_order(ticket_no, trade_data.get('SL'), execution_datetime)
                    to_inform = True
            if trade_data.get('TP') > 0.0:
                if bar_high_price >= trade_data.get('TP'):
                    self._close_order(ticket_no, trade_data.get('TP'), execution_datetime)
                    to_inform = True
        elif order_type == 'sell':
            if trade_data.get('SL') > 0.0:
                if bar_high_price >= trade_data.get('SL'):
                    self._close_order(ticket_no, trade_data.get('SL') + pip_value, execution_datetime)
                    to_inform = True
            if trade_data.get('TP') > 0.0:
                if bar_low_price <= trade_data.get('TP'):
                    self._close_order(ticket_no, trade_data.get('TP') + pip_value, execution_datetime)
                    to_inform = True

        if to_inform == True:
            self.open_orders.pop(ticket_no)
            self.event_handler.on_message({'type': 'INFO',
                                           'message': f'Successfully closed 1 orders with symbol {order_symbol}.'})
            self.event_handler.on_order_event()

    def get_left_n_elements(self, dataframe, start_index, n):
        keys = dataframe.index.tolist()
        start_index = keys.index(start_index)
        end_index = start_index + n
        return dataframe.iloc[start_index:end_index]

    # NOT USED BUT COULD BE USEFUL IN THE FUTURE
    def update_order_on_tick(self, ticket_no, trade_data):
        order_type = trade_data.get('type')
        order_symbol = trade_data.get('symbol')
        tick_data = self.get_tick_data_for_date_range(order_symbol)
        to_inform = False
        if order_type == 'buy':
            if trade_data.get('SL') > 0.0:
                if tick_data['Bid'] <= trade_data.get('SL'):
                    trade_data['close_price'] = tick_data['Bid']
                    trade_data['close_time'] = tick_data['DateTime']
                    trade_data['status'] = OrderStatus.CLOSED
                    to_inform = True
            if trade_data.get('TP') > 0.0:
                if tick_data['Bid'] >= trade_data.get('TP'):
                    trade_data['close_price'] = tick_data['Bid']
                    trade_data['close_time'] = tick_data['DateTime']
                    trade_data['status'] = OrderStatus.CLOSED
                    to_inform = True
        elif order_type == 'sell':
            if trade_data.get('SL') > 0.0:
                if tick_data['Ask'] >= trade_data.get('SL'):
                    trade_data['close_price'] = tick_data['Ask']
                    trade_data['close_time'] = tick_data['DateTime']
                    trade_data['status'] = OrderStatus.CLOSED
                    to_inform = True
            if trade_data.get('TP') > 0.0:
                if tick_data['Ask'] <= trade_data.get('TP'):
                    trade_data['close_price'] = tick_data['Ask']
                    trade_data['close_time'] = tick_data['DateTime']
                    trade_data['status'] = OrderStatus.CLOSED
                    to_inform = True
        if to_inform == True:
            self.open_orders.pop(ticket_no)
            self.event_handler.on_message({'type': 'INFO',
                                           'message': f'Successfully closed 1 orders with symbol {order_symbol}.'})
            self.event_handler.on_order_event()

    """Sends a MODIFY_ORDER command to modify an order.

    Args:
        ticket (int): Ticket of the order that should be modified.

    Kwargs:
        lots (float): Volume in lots
        price (float): Price of the (pending) order. Non-zero only 
            works for pending orders. 
        stop_loss (float): New stop loss price.
        take_profit (float): New take profit price. 
        expiration (int): New expiration time given as timestamp in seconds. 
            Can be zero if the order should not have an expiration time. 

    """

    def modify_order(self, ticket,
                     lots=0.01,
                     price=0,
                     stop_loss=0,
                     take_profit=0,
                     expiration=0):

        trade_data = self.dict_trades[ticket]
        order_status = trade_data.get('status')

        if order_status == OrderStatus.PENDING:
            trade_data['lots'] = lots
            trade_data['price'] = price
            trade_data['SL'] = stop_loss
            trade_data['TP'] = take_profit
            trade_data['expiration'] = expiration
            self.execute_order(ticket, trade_data)
        elif order_status == OrderStatus.OPEN:
            trade_data['SL'] = stop_loss
            trade_data['TP'] = take_profit
            trade_data['expiration'] = expiration
            self.update_order(ticket, trade_data)

    def validate_order(self, trade_data):
        result = False
        if trade_data['type'] in self.buy_order_types:
            if 0 < trade_data['TP'] <= trade_data['price']:
                logger.error(
                    f"Error in trade {trade_data['ticket_no']} {trade_data['type']}: TP {trade_data['TP']} <= Price {trade_data['TP']}")
            elif trade_data['SL'] > 0 and trade_data['SL'] >= trade_data['price']:
                logger.error(
                    f"Error in trade {trade_data['ticket_no']} {trade_data['type']}: SL {trade_data['TP']} >= Price {trade_data['TP']}")
            else:
                result = True
        if trade_data['type'] in self.sell_order_types:
            if trade_data['TP'] > 0 and trade_data['TP'] >= trade_data['price']:
                logger.error(
                    f"Error in trade {trade_data['ticket_no']} {trade_data['type']}: TP {trade_data['TP']} >= Price {trade_data['TP']}")
            elif 0 < trade_data['SL'] <= trade_data['price']:
                logger.error(
                    f"Error in trade {trade_data['ticket_no']} {trade_data['type']}: SL {trade_data['TP']} <= Price {trade_data['TP']}")
            else:
                result = True
        return result

    def duplicate_order(self, ticket_no):
        result = 0
        if self.dict_trades.get(ticket_no) is not None:
            new_trade_data = self.dict_trades[ticket_no].copy()
            self.last_ticket_no += 1
            new_trade_data['ticket_no'] = self.last_ticket_no
            self.dict_trades[self.last_ticket_no] = new_trade_data
            result = self.last_ticket_no
        else:
            logger.error(f"Error on duplicate_order: order {ticket_no} not exist in the dictionary")
        return result

    """Sends a CLOSE_ORDER command to close an order.

    Args:
        ticket (int): Ticket of the order that should be closed.
    
    Kwargs:
        lots (float): Volume in lots. If lots=0 it will try to 
            close the complete position. 
    
    """

    def close_order(self, ticket, lots=0):
        trade_data = self.dict_trades[ticket]
        symbol = trade_data['symbol']
        result = False
        to_close = False

        if trade_data['status'] == OrderStatus.OPEN:
            if 0 < lots < trade_data['lots']:
                new_ticket = self.duplicate_order(ticket)
                if new_ticket > 0:
                    self.dict_trades[new_ticket]['lots'] = (trade_data['lots'] - lots)
                    self.dict_trades[ticket]['lots'] = lots
                    to_close = True
            else:
                to_close = True

            if to_close:
                self._close_order(ticket)
                result = True
        elif trade_data['status'] == OrderStatus.PENDING:
            self.dict_trades[ticket]['status'] = OrderStatus.CANCELED
            self.dict_trades[ticket]['close_time'] = self.current_datetime
            result = True

        if result:
            self.open_orders.pop(ticket)
            self.event_handler.on_message({'type': 'INFO',
                                           'message': f'Successfully closed 1 orders with symbol {symbol}.'})
            self.event_handler.on_order_event()

        return result

    def _close_order(self, ticket, close_price=None, close_time=None):
        trade_data = self.dict_trades[ticket]
        symbol = trade_data['symbol']
        pip_value = self.symbol_specs[symbol]['pip_value']
        if close_time is None:
            close_time = self.current_datetime
        if close_price is None:
            tick_data = self.get_tick_data_for_date_range(symbol)
            close_price = tick_data['Bid'].iloc[0]
            if trade_data['type'] in self.sell_order_types:
                close_price = close_price + pip_value
        self.dict_trades[ticket]['close_price'] = close_price
        self.dict_trades[ticket]['close_time'] = close_time
        self.dict_trades[ticket]['commission'] = self._calculate_commission(trade_data['lots'],
                                                                            self.execution_commission_rate, symbol,
                                                                            close_time)
        self.dict_trades[ticket]['status'] = OrderStatus.CLOSED
        self.dict_trades[ticket]['pnl'] = self._calculate_profit(trade_data)

    def _calculate_profit(self, trade_data):
        base_currency = trade_data['symbol'][:3]
        quote_currency = self.account_info['currency']
        contract_size = self.symbol_specs[trade_data['symbol']]['contract_size']

        # Calculate profit.
        profit = 0.0
        if trade_data['type'] == 'buy':
            profit = (trade_data['close_price'] - trade_data['open_price']) * trade_data['lots'] * contract_size
        else:
            profit = (trade_data['open_price'] - trade_data['close_price']) * trade_data['lots'] * contract_size

        # If base currency is not quote currency then convert it.
        if base_currency != quote_currency:
            # Initialize CurrencyRates object
            c = CurrencyRates(force_decimal=True)
            # Get historic exchange rate
            exchange_rate = float(c.get_rate(base_currency, quote_currency, trade_data['close_time']))
            profit = round(profit * exchange_rate, 2)
        else:
            profit = round(profit, 2)
        profit = profit + trade_data['commission']
        return profit

    def _calculate_commission(self, order_lots, commission_rate, symbol, date=None):
        # Extract base currency from the symbol
        base_currency = symbol[:3]
        quote_currency = self.account_info['currency']
        contract_size = self.symbol_specs[symbol]['contract_size']

        # Calculate commission in base currency
        commission_base_currency = ((order_lots * contract_size) * commission_rate) / 100.0

        # If base currency is not quote currency then convert it.
        if base_currency != quote_currency:
            # Initialize CurrencyRates object
            c = CurrencyRates(force_decimal=True)
            if date is None:
                date = self.current_datetime

            # Get historic exchange rate
            exchange_rate = float(c.get_rate(base_currency, quote_currency, date))
            commission = round(commission_base_currency * exchange_rate, 2)
        else:
            commission = round(commission_base_currency, 2)
        commission = (commission * (-1)) * 2  # roundtrip
        return commission

    def GetCurrentTime(self):
        return self.current_datetime
        return result

    """Sends a CLOSE_ALL_ORDERS command to close all orders.
    """

    def close_all_orders(self):
        orders = [(ticket_no, trade_data) for ticket_no, trade_data in self.dict_trades.items() if
                  (trade_data.get('status') == OrderStatus.OPEN or trade_data.get('status') == OrderStatus.PENDING)]
        for ticket_no, trade_data in orders:
            self.close_order(ticket_no)

    """Sends a CLOSE_ORDERS_BY_SYMBOL command to close all orders
    with a given symbol.

    Args:
        symbol (str): Symbol for which all orders should be closed. 
    
    """

    def close_orders_by_symbol(self, symbol):
        orders = [(ticket_no, trade_data) for ticket_no, trade_data in self.dict_trades.items() if
                  trade_data.get('symbol') == symbol and
                  (trade_data.get('status') == OrderStatus.OPEN or trade_data.get('status') == OrderStatus.PENDING)]
        for ticket_no, trade_data in orders:
            self.close_order(ticket_no)

    """Sends a CLOSE_ORDERS_BY_MAGIC command to close all orders
    with a given magic number.

    Args:
        magic (str): Magic number for which all orders should 
            be closed. 
    
    """

    def close_orders_by_magic(self, magic):
        orders = [(ticket_no, trade_data) for ticket_no, trade_data in self.dict_trades.items() if
                  trade_data.get('magic') == magic and
                  (trade_data.get('status') == OrderStatus.OPEN or trade_data.get('status') == OrderStatus.PENDING)]
        for ticket_no, trade_data in orders:
            self.close_order(ticket_no)
