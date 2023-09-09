import quantstats as qs
from python.common.logging_config import logger
from python.common.files import extract_dictionaries_from_file, load_qdm_data_from_file
import pandas as pd
from pathlib import Path


def generate_report_metrics(bars_data_filename, symbol, time_frame, start_date, end_date, trades_filename):
    if Path(trades_filename).exists():
        df_bars = load_qdm_data_from_file(bars_data_filename)
        df_trades = extract_dictionaries_from_file(trades_filename, symbol)
        # extend pandas functionality with metrics, etc.
        qs.extend_pandas()
        # fetch the daily returns for a stock
        total_returns = get_trades_returns(df_bars, df_trades)
        # show sharpe ratio
        qs.stats.sharpe(total_returns)
        # or using extend_pandas() :)
        total_returns.sharpe()


def get_trade_returns(bars_data, trade_info):
    start_date = trade_info['open_time']
    end_date = trade_info['close_time']
    mask = (bars_data.index >= start_date) & (bars_data.index <= end_date)
    mask2 = (bars_data.index == end_date) & (bars_data.index <= end_date)
    trade_returns = bars_data.DataFrame(index=bars_data.index)
    trade_returns['returns'] = 0.0
    if trade_info['type'] == 'sell':
        trade_returns.loc[mask, 'returns'] = (trade_info['open_price'] / bars_data.loc[mask, 'close']) - 1
        trade_returns.loc[mask2, 'returns'] = (trade_info['open_price'] / trade_info['close_price'])-1
    else: # buy
        trade_returns.loc[mask, 'returns'] = (bars_data.loc[mask, 'close'] / trade_info['open_price']) - 1
    return trade_returns


def get_trades_returns(bars_data, trades_info):
    total_returns = bars_data.DataFrame(index=bars_data.index)
    total_returns['returns'] = 0.0
    for trade_info in trades_info:
        total_returns['returns'] = total_returns['returns'] + get_trade_returns(bars_data, trade_info)

