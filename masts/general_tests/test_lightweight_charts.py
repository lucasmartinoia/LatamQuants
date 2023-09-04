import pandas as pd
import pandas_ta as ta
from lightweight_charts import Chart
import talib
from python.common.conversions import convert_historic_bars_element_to_array

chart = Chart()

file_name = 'C:/QuantDataManager/export/2023.9.4EURUSD_TICK_UTCPlus03-H4-No Session.csv'

# Read the H1 file into a DataFrame
df = pd.read_csv(file_name)

# Convert the 'Date' and 'Time' columns to a datetime column
df['DateTime'] = pd.to_datetime(df['Date'].astype(str) + ' ' + df['Time'])

# Set the 'Datetime' column as the index
#df.set_index('DateTime', inplace=True)

# Remove the 'Date' and 'Time' columns
df = df.drop('Date', axis=1)
df = df.drop('Time', axis=1)

# Rename columns
df = df.rename(columns={"DateTime": "date", "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})

# prepare indicator values
ema_50 = pd.DataFrame()
ema_50['time'] = df['date']
ema_50['value'] = talib.EMA(df['close'], timeperiod=50)
ema_50 = ema_50.reset_index()
ema_50 = ema_50.dropna()

ema_100 = pd.DataFrame()
ema_100['time'] = df['date']
ema_100['value'] = talib.EMA(df['close'], timeperiod=100)
ema_100 = ema_100.reset_index()
ema_100 = ema_100.dropna()

ema_240 = pd.DataFrame()
ema_240['time'] = df['date']
ema_240['value'] = talib.EMA(df['close'], timeperiod=240)
ema_240 = ema_240.reset_index()
ema_240 = ema_240.dropna()

# this library expects lowercase columns for date, open, high, low, close, volume
df = df.reset_index()
df.columns = df.columns.str.lower()
chart.set(df)

# add sma line
line = chart.create_line()
line.set(ema_50)

line = chart.create_line()
line.set(ema_100)

line = chart.create_line()
line.set(ema_240)

chart.watermark('MASTS')
chart.show(block=True)
