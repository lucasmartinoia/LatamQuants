from python.common.logging_config import logger
from python.common.files import extract_dictionaries_from_file, load_qdm_data_from_file
from pathlib import Path
from python.common.files import get_daily_returns_from_file
import quantstats as qs
import pandas as pd
import json

def generate_report_metrics(symbol, returns_filename):
    if Path(returns_filename).exists():
        qs.extend_pandas()
        # Load returns from file.
        df_returns = get_daily_returns_from_file(returns_filename)

        # generate full metric report
        #report_file_name = returns_filename[:-4] + f'_report_metrics_full.json'
        #df_metrics = qs.reports.metrics(df_returns, "SPY", mode='full', display=False)
        #df_metrics.to_json(report_file_name)

        # Generate html report to file.
        returns_file_name = returns_filename[:-4] + f'_{symbol}_report_full.html'
        result = qs.reports.html(df_returns, "SPY", output=returns_file_name)
        dummy = 1
        # # Example: load existent report and access to a metric
        # df_new = pd.read_json(report_file_name)
        # strategy_sharpe = df_new['Strategy']['Sharpe']
        # benchmark_sharpe = df_new['Benchmark (SPY)']['Sharpe']
        # # End example

def get_trade_returns_old(bars_data, trade_info):
    start_date = trade_info['open_time']
    end_date = trade_info['close_time']
    mask = (bars_data.index >= start_date) & (bars_data.index <= end_date)
    mask2 = (bars_data.index == end_date) & (bars_data.index <= end_date)
    trade_returns = pd.DataFrame(index=bars_data.index)
    trade_returns['returns'] = 0.0
    if trade_info['type'] == 'sell':
        trade_returns.loc[mask, 'returns'] = (trade_info['open_price'] / bars_data.loc[mask, 'close']) - 1
        trade_returns.loc[mask2, 'returns'] = (trade_info['open_price'] / trade_info['close_price'])-1
    else: # buy
        trade_returns.loc[mask, 'returns'] = (bars_data.loc[mask, 'close'] / trade_info['open_price']) - 1
    return trade_returns['returns']



def get_trades_returns_old(bars_data, trades_info):
    total_returns = pd.DataFrame(index=bars_data.index)
    total_returns['returns'] = 0.0
    i = 0
    for index, trade_info in trades_info.iterrows():
        total_returns['returns'] = total_returns['returns'] + get_trade_returns(bars_data, trade_info)
    return total_returns['returns']
