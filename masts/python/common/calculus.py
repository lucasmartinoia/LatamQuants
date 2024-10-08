import pandas as pd
import datetime
from forex_python.converter import CurrencyRates

def calculate_trailing_stop(trade_info, market_price, margin_points):
    result = None
    if trade_info['type'] == 'buy':
        price_diff = market_price['bid'] - trade_info['open_price']
        jumps = abs(int(price_diff / margin_points))
        if jumps > 0:
            new_sl = trade_info['open_price'] + (jumps-1)*margin_points
            if trade_info['SL'] < new_sl:
                result = new_sl
    elif trade_info['type'] == 'sell':
        price_diff = trade_info['open_price'] - market_price['ask']
        jumps = abs(int(price_diff / margin_points))
        if jumps > 0:
            new_sl = trade_info['open_price'] - (jumps-1)*margin_points
            if new_sl < trade_info['SL']:
                result = new_sl
    return result


def get_pip_value(digits):
    return 10 ** (-1 * (digits - 1))

def get_daily_trades_returns_on_close_date(trades_info, investment = 100000.0):
    df_trades = trades_info.copy()
    # Convert 'datetime' column in df2 to datetime objects
    df_trades['close_date'] = pd.to_datetime(df_trades['close_time']).dt.date

    # Generate a date range between init_date and end_date (inclusive)
    date_range = pd.date_range(df_trades['close_date'].iloc[0], df_trades['close_date'].iloc[len(df_trades) - 1])

    # Create a DataFrame with the date range as the index and no columns
    df_result = pd.DataFrame(index=date_range)
    df_result['Close'] = 0.0

    # Calculate accum returns
    accum_return = investment # Initial capital
    i = 0

    while i < len(df_result):
        day_return = (df_trades[df_trades['close_date'] == df_result.iloc[i].name])['pnl'].sum()
        accum_return = accum_return + day_return
        df_result.iloc[i]['Close'] = accum_return
        i = i + 1
    return df_result['Close']


def get_exchange_rate(base_currency, quote_currency, date_time=None):
    exchange_rate = 1.0
    if base_currency != quote_currency:
        if date_time is None:
            date_time = datetime.datetime.now()
        # Initialize CurrencyRates object
        c = CurrencyRates(force_decimal=True)
        # Get historic exchange rate
        exchange_rate = float(c.get_rate(base_currency, quote_currency, date_time))
    return exchange_rate

def normalize_order_size(calculated_size, min_volume):
    decimal_places = len(str(min_volume).split(".")[1])
    normalized_size = float(f'{calculated_size:.{decimal_places}f}')
    if normalized_size < min_volume:
        normalized_size = 0.0
    return normalized_size
