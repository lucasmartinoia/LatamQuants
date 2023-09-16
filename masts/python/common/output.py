import pandas as pd
import ast
from python.common.files import extract_dictionaries_from_file
from python.common.calculus import get_daily_trades_returns_on_close_date


def add_trade_to_file(filename, dictionary):
    copy_dict = dictionary.copy()
    copy_dict['status'] = copy_dict['status'].name
    copy_dict['open_time'] = copy_dict['open_time'].strftime('%Y-%m-%d %H:%M:%S')
    copy_dict['close_time'] = copy_dict['close_time'].strftime('%Y-%m-%d %H:%M:%S')
    add_dictionary_to_file(filename, copy_dict)


def add_dictionary_to_file(filename, dictionary):
    with open(filename, 'a') as file:
        file.write(str(dictionary))
        file.write('\n')  # Add a new line after appending the dictionary


def generate_daily_returns_file(trades_filename, symbol, investment=None):
    df_trades = extract_dictionaries_from_file(trades_filename, symbol)
    df_returns = get_daily_trades_returns_on_close_date(df_trades, investment)
    returns_file_name = trades_filename[:-4] + f'_{symbol}_returns.json'
    df_returns.to_json(returns_file_name)
    return returns_file_name
