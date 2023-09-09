from collections import defaultdict
import dateutil.parser
import finplot as fplt
import numpy as np
import pandas as pd
import requests
from datetime import datetime, timedelta
import matplotlib.colors as mcolors
from python.common.output import extract_dictionaries_from_file
import talib
from python.common.conversions import convert_historic_bars_to_dataframe
from pathlib import Path

def get_color_code(color_name):
    color_name = color_name.lower()
    if color_name in mcolors.CSS4_COLORS:
        return mcolors.CSS4_COLORS[color_name]
    else:
        return None


def local2timestamp(s):
    return int(dateutil.parser.parse(s).timestamp())


def load_qdm_data(file_name):
    df = pd.read_csv(file_name)
    df['DateTime'] = pd.to_datetime(df['Date'].astype(str) + ' ' + df['Time'])
    df = df.drop(['Date', 'Time'], axis=1)
    df = df.rename(columns={'DateTime':'time', 'Open':'open', 'Close':'close', 'High':'high', 'Low':'low', 'Volume':'volume'})
    return df.set_index('time')


def plot_accumulation_distribution(df, ax):
    ad = (2*df.close-df.high-df.low) * df.volume / (df.high - df.low)
    ad.cumsum().ffill().plot(ax=ax, legend='Accum/Dist', color='#f00000')


def plot_bollinger_bands(df, ax):
    mean = df.close.rolling(20).mean()
    stddev = df.close.rolling(20).std()
    df['boll_hi'] = mean + 2.5*stddev
    df['boll_lo'] = mean - 2.5*stddev
    p0 = df.boll_hi.plot(ax=ax, color='#808080', legend='BB')
    p1 = df.boll_lo.plot(ax=ax, color='#808080')
    fplt.fill_between(p0, p1, color='#bbb')


def plot_ema(df, ax, periods, color, width=2):
    color_code = get_color_code(color)
    talib.EMA(df['close'], timeperiod=periods).plot(ax=ax, legend=f'EMA_{periods}', color=color_code, width=width)


def plot_heikin_ashi(df, ax):
    df['h_close'] = (df.open+df.close+df.high+df.low) / 4
    ho = (df.open.iloc[0] + df.close.iloc[0]) / 2
    for i,hc in zip(df.index, df['h_close']):
        df.loc[i, 'h_open'] = ho
        ho = (ho + hc) / 2
    print(df['h_open'])
    df['h_high'] = df[['high','h_open','h_close']].max(axis=1)
    df['h_low'] = df[['low','h_open','h_close']].min(axis=1)
    df[['h_open','h_close','h_high','h_low']].plot(ax=ax, kind='candle')


def plot_candles(df, ax):
    df[['open', 'close', 'high', 'low']].plot(ax=ax, kind='candle')


def plot_heikin_ashi_volume(df, ax):
    df[['h_open','h_close','volume']].plot(ax=ax, kind='volume')


def plot_on_balance_volume(df, ax):
    obv = df.volume.copy()
    obv[df.close < df.close.shift()] = -obv
    obv[df.close==df.close.shift()] = 0
    obv.cumsum().plot(ax=ax, legend='OBV', color='#008800')


def plot_rsi(df, ax):
    diff = df.close.diff().values
    gains = diff
    losses = -diff
    with np.errstate(invalid='ignore'):
        gains[(gains<0)|np.isnan(gains)] = 0.0
        losses[(losses<=0)|np.isnan(losses)] = 1e-10 # we don't want divide by zero/NaN
    n = 14
    m = (n-1) / n
    ni = 1 / n
    g = gains[n] = np.nanmean(gains[:n])
    l = losses[n] = np.nanmean(losses[:n])
    gains[:n] = losses[:n] = np.nan
    for i,v in enumerate(gains[n:],n):
        g = gains[i] = ni*v + m*g
    for i,v in enumerate(losses[n:],n):
        l = losses[i] = ni*v + m*l
    rs = gains / losses
    df['rsi'] = 100 - (100/(1+rs))
    df.rsi.plot(ax=ax, legend='RSI')
    fplt.set_y_range(0, 100, ax=ax)
    fplt.add_band(30, 70, ax=ax)


def plot_vma(df, ax):
    df.volume.rolling(20).mean().plot(ax=ax, color='#c0c030')


def graph_trading_results(bars_data_filename, symbol, time_frame, start_date, end_date, trades_filename):
    df = load_qdm_data(bars_data_filename)
    # graph title
    ax = fplt.create_plot(f'MASTS + {symbol} {time_frame}', rows=1)
    ax.set_visible(xgrid=True, ygrid=True)
    # price chart
    plot_candles(df, ax)
    plot_ema(df, ax, 50, "red")
    plot_ema(df, ax, 100, "yellow")
    plot_ema(df, ax, 240, "black")
    graph_trades(trades_filename, symbol)
    # restore view (X-position and zoom) when we run this again
    # fplt.autoviewrestore()
    fplt.show()


def graph_trades(trades_filename, symbol):
    if Path(trades_filename).exists():
        df = extract_dictionaries_from_file(trades_filename, symbol)
        df.apply(graph_trade, axis=1)


def graph_trade(trade_info):
    open_datetime = pd.to_datetime(trade_info['open_time'])
    close_datetime = pd.to_datetime(trade_info['close_time'])
    open_price = trade_info['open_price']
    close_price = trade_info['close_price']
    # colors
    color_line_buy = get_color_code('blue')
    color_line_sell = get_color_code('red')
    color_rect_profit = get_color_code('lightgreen')
    color_rect_loss = get_color_code('orange')
    color_text = get_color_code('black')
    color_line = None
    color_rect = None
    text_price = None
    if trade_info['type'] == 'buy':
        color_line = color_line_buy
    else:
        color_line = color_line_sell

    if trade_info['pnl'] >= 0.0:
        color_rect = color_rect_profit
    else:
        color_rect = color_rect_loss
    if close_price > open_price:
        text_price = close_price * 1.001
    else:
        text_price = close_price * 0.999
    text_label = f"#{trade_info['ticket_no']}_{trade_info['type']}_{trade_info['pnl']}"

    # plotting
    line = fplt.add_line((open_datetime, open_price), (close_datetime, close_price), color=color_line, interactive=True)
    rect = fplt.add_rect((open_datetime, open_price), (close_datetime, close_price), color=color_rect, interactive=True)
    text = fplt.add_text((open_datetime, open_price), text_label, color=color_text)


def graph_trend_from_backtesting(historic_bars, symbol, time_frame, ema50, ema100, ema240):
    df = convert_historic_bars_to_dataframe(historic_bars)
    # graph title
    ax = fplt.create_plot(f'MASTS [GraphTrend] + {symbol} {time_frame}', rows=1)
    ax.set_visible(xgrid=True, ygrid=True)
    # price chart
    plot_candles(df, ax)
    # plot emas
    df['ema50'] = ema50
    df['ema100'] = ema100
    df['ema240'] = ema240
    width = 2
    red_code = get_color_code("red")
    yellow_code = get_color_code("yellow")
    black_code = get_color_code("black")
    df.ema50.plot(ax=ax, legend='ema50', color=red_code, width=width)
    df.ema100.plot(ax=ax, legend='ema100', color=yellow_code, width=width)
    df.ema240.plot(ax=ax, legend='ema240', color=black_code, width=width)
    fplt.show()