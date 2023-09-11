from python.common.reports import generate_report_metrics
from python.common.graphics import graph_trading_results

bar_data_file_name = 'C:/QuantDataManager/export/2023.9.4EURUSD_TICK_UTCPlus03-H4-No Session.csv'
symbol = 'EURUSD'
timeframe = 'H4'
trades_filename = 'C:\Lucas\devs\GitHub\LatamQuants\masts\output/trades_20230911_134411_backtest.txt'
start_datetime = None
end_datetime = None
#generate_report_metrics(bar_data_file_name, symbol, timeframe, start_datetime, end_datetime, trades_filename)
graph_trading_results(bar_data_file_name, symbol, timeframe, start_datetime, end_datetime,
                      trades_filename)
