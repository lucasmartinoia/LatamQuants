from python.common.graphics import graph_trading_results
from python.common.files import get_most_recent_file
from python.common.reports import generate_report_metrics

bar_data_file_name = 'C:/QuantDataManager/export/2024.3.3EURUSD_TICK_UTCPlus03-M15-No Session.csv'
symbol = 'EURUSD'
timeframe = 'H4'

# Specific files.
#trades_filename = 'C:\Lucas\devs\GitHub\LatamQuants\masts\output/trades_20230911_134411_backtest.txt'
#returns_filename = 'C:\Lucas\devs\GitHub\LatamQuants\masts\output/trades_20230916_210415_backtest_EURUSD_returns.json'

# Last files.
trades_filename = get_most_recent_file('C:\Lucas\devs\GitHub\LatamQuants\masts\output', '_backtest.txt')
trades_full_filename = 'C:\Lucas\devs\GitHub\LatamQuants\masts\output/' + trades_filename

returns_filename = get_most_recent_file('C:\Lucas\devs\GitHub\LatamQuants\masts\output', f'_{symbol}_returns.json')
returns_full_filename = 'C:\Lucas\devs\GitHub\LatamQuants\masts\output/' + returns_filename

# NOTE: METRICS REPORT (HTML) IS GENERATED USING NOTEBOOK: "Masts-Metrics Report Generator" (due is not working here).

graph_trading_results(bar_data_file_name, symbol, timeframe, None, None, trades_full_filename)
