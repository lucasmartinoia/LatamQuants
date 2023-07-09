from time import sleep
from random import random
from datetime import datetime, timedelta

from api.dwx_client import dwx_client
from indicators.macd_platinum_v2 import macd_platinum_v2
from python.common.conversions import convert_historic_bars_element_to_array
from python.common.logging_config import setup_logging, logger
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
                 MT4_directory_path=None,
                 sleep_delay=0.005,             # 5 ms for time.sleep()
                 max_retry_command_seconds=10,  # retry to send the command for 10 seconds if not successful.
                 verbose=True
                 ):
        self.validate_parameters(mode,back_test_start,back_test_end,back_test_directory_path,MT4_directory_path)

        # store params
        self.mode = mode
        self.back_test_start = back_test_start
        self.back_test_end = back_test_end
        self.back_test_directory_path = back_test_directory_path
        self.MT4_directory_path = MT4_directory_path
        self.sleep_delay = sleep_delay
        self.max_retry_command_seconds = max_retry_command_seconds
        self.verbose = verbose

        # private info
        self.last_open_time = datetime.utcnow()
        self.last_modification_time = datetime.utcnow()

        # set mode
        if self.mode == "live":
            self.dma = dwx_client(self, MT4_directory_path, sleep_delay,
                                  max_retry_command_seconds, verbose=verbose)
            sleep(1)
        #elif self.mode == "backtest":
        # TODO: use new backtesting class once implemented

        self.dma.start()
        
        # account information is stored in self.dwx.account_info.
        logger.info(f"Account info: {self.dma.account_info}")

        # subscribe to tick data:
        #self.dma.subscribe_symbols(['BTCUSD'])

        # subscribe to bar data:
        self.dma.subscribe_symbols_bar_data([['BTCUSD', 'M15']])

        # request historic data:
        end = datetime.utcnow()
        start = end - timedelta(days=40)  # 40d = 240h
        self.dma.get_historic_data('BTCUSD', 'H4', start.timestamp(), end.timestamp())

    def validate_parameters(self,mode,
                back_test_start,
                back_test_end,
                back_test_directory_path,
                MT4_directory_path):

        if mode=="backtest":
            if back_test_start==None:
                raise Exception("back_test_start is required")
            elif back_test_end==None:
                raise Exception("back_test_end is required")
            elif back_test_end<=back_test_start:
                raise Exception("back_test_end cannot be lower or equal to back_test_start")
            elif back_test_directory_path==None:
                raise Exception("back_test_directory_path is required")
        elif mode=="live":
            if MT4_directory_path==None:
                raise Exception("MT4_directory_path is required")
        else:
            raise Exception("mode parameter is not 'backtest' neither 'live'")

    def on_tick(self, symbol, bid, ask):
        now = datetime.utcnow()
        logger.debug(f'on_tick: {symbol} {bid} {ask}')

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
        logger.debug(f'on_bar_data: {symbol} {time_frame} {time} {open_price} {high} {low} {close_price}')

    def on_historic_data(self, symbol, time_frame, data):
        logger.debug(f'historic_data: {symbol} {time_frame} {len(data)} bars')

        close_prices = convert_historic_bars_element_to_array('close', data)
        volumes = convert_historic_bars_element_to_array('tick_volume', data)
        self.macd_plat = macd_platinum_v2(close_prices, volumes)
        blueMACD, orgMACD, hist = self.macd_plat.calculate_macd()

    def on_historic_trades(self):
        logger.debug(f'historic_trades: {len(self.dma.historic_trades)}')
    
    def on_message(self, message):
        if message['type'] == 'ERROR':
            logger.debug(f"{message['type']}|{message['error_type']}|{message['description']}")
        elif message['type'] == 'INFO':
            logger.debug(f"{message['type']}|{message['message']}")


    # triggers when an order is added or removed, not when only modified. 
    def on_order_event(self):
        logger.debug(f'on_order_event. open_orders: {len(self.dma.open_orders)} open orders')


""" =====================================================================================================
    BACKTESTING - CLASS AND EVENTS
    =====================================================================================================
"""

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

# FXOpen Demo Account
MT4_files_dir = 'C:/Users/Usuario/AppData/Roaming/MetaQuotes/Terminal/30D279B64B1858168C932D8264853F2B/MQL4/Files'
logger.info('MT4_files_dir -> ' + MT4_files_dir)
processor = tick_processor('live',None,None,None,MT4_files_dir)
while processor.dma.ACTIVE:
    sleep(1)

# Backtesting
#
#
