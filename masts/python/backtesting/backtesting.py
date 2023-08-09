import os
import json
from time import sleep
from threading import Thread, Lock
from os.path import join, exists
from traceback import print_exc
from datetime import datetime, timedelta
from python.common.logging_config import logger
from python.common.conversions import convert_bar_dataframe_to_dict, get_timeframe_delta, get_bar_data_clean_date
import pandas as pd
from enum import Enum
from collections import deque
import bisect


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
                 leverage=33):

        logger.info("backtesting.__init__()")

        if not exists(back_test_directory_path):
            logger.error('back_test_directory_path does not exist!')
            raise Exception('back_test_directory_path does not exist!')
            exit()
        else:
            self.data_path = back_test_directory_path

        # Init variables
        self.dict_tickdata = {}
        self.dict_tickdata_index = {}
        self.dict_tickdata_index_prev = {}
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

        # Store parameters
        self.start_datetime = start_datetime
        self.end_datetime = end_datetime
        self.event_handler = event_handler
        self.account_info = {'name': 'backtesting_mode', 'number': 1111, 'currency': currency, 'leverage': leverage,
                             'free_margin': balance, 'balance': balance, 'equity': balance}

        # implements
        # self.open_orders # Current open orders, pending and opened. Order ticket is the key.
        # self.market_data # Symbol is the key.
        # self.bar_data # Contains the latest bar data. This is updated continually if subscribed to specific bar data.
        # self.historic_trades # Contains the requested trade history, which is only updated after a request for historic trades
        # self.historic_data # Lastest historic data required.

        self.ACTIVE = True
        self.START = False

    # Function to insert new row into the deque maintaining sorted order
    def insert_moment_tick_in_list(self, row):
        index = bisect.bisect_left(self.sorted_tick_moment_list, row)
        self.sorted_tick_moment_list.insert(index, row)

    """START can be used to check if the client has been initialized.  
    """

    def start(self):
        self.START = True
        init = 1
        symbols = self.dict_tickdata.keys()

        # Main backtesting loop - multi symbol in parallel
        while self.START:
            self.sorted_tick_moment_list.clear()

            if init == 1:
                # Set indexes for each tick_data the first time
                for symbol in symbols:
                    symbol_index = self.get_tick_data_index_for_date(self.dict_tickdata[symbol], self.start_datetime)
                    self.dict_tickdata_index[symbol] = symbol_index
                    self.dict_tickdata_index_prev[symbol] = symbol_index
                    if symbol_index is not None:  # Only consider symbols with tick data
                        symbol_datetime = self.GetCurrentTime(symbol)
                        self.insert_moment_tick_in_list((symbol_datetime, symbol_index, symbol))
                    init = 0
            else:  # Increment indexes
                for symbol in self.dict_tickdata_index.keys():
                    symbol_index = self.dict_tickdata_index[symbol]
                    if symbol_index is not None and self.dict_tickdata[symbol].shape[0] > (symbol_index + 1):
                        self.dict_tickdata_index_prev[symbol] = symbol_index
                        symbol_index += 1
                        self.dict_tickdata_index[symbol] = symbol_index
                        symbol_datetime = self.GetCurrentTime(symbol)
                        self.insert_moment_tick_in_list((symbol_datetime, symbol_index, symbol))
                    elif symbol_index is not None:
                        self.dict_tickdata_index[symbol] = None
            if len(self.sorted_tick_moment_list) > 0:
                for symbol_datetime, symbol_index, symbol in self.sorted_tick_moment_list:
                    # Update market_data
                    self.market_data[symbol] = {'bid': self.dict_tickdata[symbol].iloc[symbol_index]['Bid'], 'ask': self.dict_tickdata[symbol].iloc[symbol_index]['Ask'], 'tick_value': self.dict_tickdata[symbol].iloc[symbol_index]['Volume']}
                    # 1. Update orders in the broker
                    self.update_orders(symbol)
                    # 2. Trigger tick data events
                    self.event_handler.on_tick(symbol, self.dict_tickdata[symbol].iloc[symbol_index]['Bid'],
                                               self.dict_tickdata[symbol].iloc[symbol_index]['Ask'])
                    # 3. Trigger bar data events
                    self.update_bar_datas(symbol)
            else:
                self.START = False

    def extract_symbol_and_timeframe(self, input_string):
        parts = input_string.split('_')
        if len(parts) != 2:
            raise ValueError("Invalid input format. The format should be <symbol>_<timeframe>.")

        symbol, timeframe = parts
        return symbol, timeframe

    def update_bar_datas(self, param_symbol):
        for symbol_tf in self.dict_bardata.keys():
            symbol, timeframe = self.extract_symbol_and_timeframe(symbol_tf)
            if symbol == param_symbol:
                prev_datetime = self.dict_tickdata[param_symbol].iloc[self.dict_tickdata_index_prev[param_symbol]][
                    'DateTime']
                curr_datetime = self.dict_tickdata[param_symbol].iloc[self.dict_tickdata_index[param_symbol]][
                    'DateTime']

                if self.has_bar_data_changed(prev_datetime, curr_datetime, timeframe):
                    bar_data_index = self.get_bar_data_index_for_date(self.dict_bardata[symbol_tf], curr_datetime,
                                                                      timeframe)
                    if bar_data_index is not None and bar_data_index > self.dict_bardata_index[symbol_tf]:
                        self.dict_bardata_index[symbol_tf] = bar_data_index
                        bar_data = self.dict_bardata[symbol_tf].iloc[self.dict_bardata_index[symbol_tf]]
                        self.bar_data[symbol_tf] = {'time': bar_data['DateTime'].strftime('%Y-%m-%d %H:%M:%S'), 'open': bar_data['Open'], 'high': bar_data['High'], 'low': bar_data['Low'], 'close': bar_data['Close'], 'tick_volume': bar_data['Volume']}
                        if symbol_tf in self.bar_data_subscription_requests:
                            self.event_handler.on_bar_data(symbol, timeframe, bar_data['DateTime'], bar_data['Open'],
                                                           bar_data['High'], bar_data['Low'], bar_data['Close'],
                                                           bar_data['Volume'])
                    else:
                        self.dict_tickdata_index[symbol_tf] = None

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

    def find_file(self, search_for, path):
        for root, dirs, files in os.walk(path):
            for file in files:
                if search_for in file:
                    return os.path.join(root, file)

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
        search_for = f"{symbol}-TICK"
        file_name = self.find_file(search_for, self.data_path)
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
        search_for = f'{symbolTime[0]}-{symbolTime[1]}'
        file_name = self.find_file(search_for, self.data_path)
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
        #logger.debug(f"-> get_historic_data({symbol}, {time_frame}, {start}, {end})")
        symbol_tf = f"{symbol}_{time_frame}"
        if symbol_tf in self.dict_bardata:
            if self.check_data_dates(self.dict_bardata[symbol_tf], start, end):
                #logger.info(self.dict_bardata[symbol_tf])
                result = convert_bar_dataframe_to_dict(self.dict_bardata[symbol_tf], start, end)
                #logger.info(f"get_historic_data() -> {result}")
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
        self.event_handler.on_historic_trades = [(ticket_no, trade_data) for ticket_no, trade_data in self.dict_trades.items() if
                  (trade_data.get('status') == OrderStatus.CLOSED or trade_data.get('status') == OrderStatus.CANCELED)]
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
        new_order_data = {'ticket_no': 0, 'symbol': symbol, 'type': order_type,
                          'lots': lots,
                          'price': price, 'SL': stop_loss, 'TP': take_profit, 'magic': magic,
                          'comment': comment, 'expiration': expiration, 'open_time': self.GetCurrentTime(symbol),
                          'close_time': None, 'commission': 0.0, 'taxes': 0.0, 'swap': 0.0,
                          'pnl': 0.0, 'status': OrderStatus.PENDING, 'open_price': 0.0,
                          'close_price': 0.0}
        if self.validate_order(new_order_data):
            self.last_ticket_no = self.last_ticket_no + 1
            self.dict_trades.setdefault(self.last_ticket_no, new_order_data)
            self.execute_order(self.last_ticket_no, new_order_data, True)
            result = True

        return result

    def execute_orders(self, symbol):
        pending_orders = [(ticket_no, trade_data) for ticket_no, trade_data in self.dict_trades.items() if
                          trade_data.get('symbol') == symbol and trade_data.get('status') == OrderStatus.PENDING]
        for ticket_no, trade_data in pending_orders:
            self.execute_order(ticket_no, trade_data)

    def execute_order(self, ticket_no, trade_data, new=False):
        order_type = trade_data.get('type')
        order_symbol = trade_data['symbol']
        tick_data = self.dict_tickdata[order_symbol].iloc[self.dict_tickdata_index[order_symbol]]
        to_inform = new
        if order_type.endswith('limit') or order_type.endswith('stop'):
            # programmed order
            if order_type == 'buylimit':
                if tick_data['Ask'] <= trade_data['price']:
                    trade_data['open_price'] = tick_data['Ask']
                    trade_data['open_time'] = tick_data['DateTime']
                    trade_data['type'] = 'buy'
                    trade_data['status'] = OrderStatus.OPEN
                    self.open_orders[ticket_no] = trade_data
                    to_inform = True
            elif order_type == 'selllimit':
                if tick_data['Bid'] >= trade_data['price']:
                    trade_data['open_price'] = tick_data['Bid']
                    trade_data['open_time'] = tick_data['DateTime']
                    trade_data['type'] = 'sell'
                    trade_data['status'] = OrderStatus.OPEN
                    self.open_orders[ticket_no] = trade_data
                    to_inform = True
            elif order_type == 'buystop':
                if tick_data['Ask'] >= trade_data['price']:
                    trade_data['open_price'] = tick_data['Ask']
                    trade_data['open_time'] = tick_data['DateTime']
                    trade_data['type'] = 'buy'
                    trade_data['status'] = OrderStatus.OPEN
                    self.open_orders[ticket_no] = trade_data
                    to_inform = True
            elif order_type == 'sellstop':
                if tick_data['Bid'] <= trade_data['price']:
                    trade_data['open_price'] = tick_data['Bid']
                    trade_data['open_time'] = tick_data['DateTime']
                    trade_data['type'] = 'sell'
                    trade_data['status'] = OrderStatus.OPEN
                    self.open_orders[ticket_no] = trade_data
                    to_inform = True
        else:  # Market orders input just now
            if order_type == 'buy':
                trade_data['open_price'] = tick_data['Ask']
                trade_data['open_time'] = tick_data['DateTime']
                trade_data['type'] = 'buy'
                trade_data['status'] = OrderStatus.OPEN
                self.open_orders[ticket_no] = trade_data
                to_inform = True
            elif order_type == 'sell':
                trade_data['open_price'] = tick_data['Bid']
                trade_data['open_time'] = tick_data['DateTime']
                trade_data['type'] = 'sell'
                trade_data['status'] = OrderStatus.OPEN
                self.open_orders[ticket_no] = trade_data
                to_inform = True

        if to_inform == True:
            self.event_handler.on_message({'type': 'INFO',
                                           'message': f'Successfully sent order {ticket_no}: {order_symbol}, {trade_data["type"]}, {trade_data["lots"]}, {trade_data["open_price"]}'})
            self.event_handler.on_order_event()

    def update_orders(self, symbol):
        open_orders = [(ticket_no, trade_data) for ticket_no, trade_data in self.dict_trades.items() if
                       trade_data.get('symbol') == symbol and
                       trade_data.get('status') == OrderStatus.OPEN and
                       (trade_data.get('SL') > 0.0 or trade_data.get('TP') > 0.0)]
        for ticket_no, trade_data in open_orders:
            self.execute_order(ticket_no, trade_data)

    def update_order(self, ticket_no, trade_data):
        order_type = trade_data.get('type')
        order_symbol = trade_data.get('symbol')
        tick_data = self.dict_tickdata[order_symbol][self.dict_tickdata_index]
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
                self.dict_trades[ticket]['status'] = OrderStatus.CLOSED
                self.dict_trades[ticket]['close_time'] = self.GetCurrentTime(symbol)
                close_price = 0.0
                if trade_data['type'] in self.buy_order_types:
                    close_price = self.dict_tickdata[symbol][self.dict_tickdata_index[symbol]]['Bid']
                else:
                    close_price = self.dict_tickdata[symbol][self.dict_tickdata_index[symbol]]['Ask']
                self.dict_trades[ticket]['close_price'] = close_price
                result = True
        elif trade_data['status'] == OrderStatus.PENDING:
            self.dict_trades[ticket]['status'] = OrderStatus.CANCELED
            self.dict_trades[ticket]['close_time'] = self.GetCurrentTime(symbol)
            result = True

        if result:
            self.event_handler.on_order_event({ticket: self.dict_trades[ticket]})
            self.open_orders.pop(ticket)
            self.event_handler.on_message({'type': 'INFO',
                                           'message': f'Successfully closed 1 orders with symbol {symbol}.'})
            self.event_handler.on_order_event()

        return result

    def GetCurrentTime(self, symbol):
        result = self.dict_tickdata[symbol].iloc[self.dict_tickdata_index[symbol]]['DateTime']
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
