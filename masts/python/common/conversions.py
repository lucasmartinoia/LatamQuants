import numpy as np
import pandas as pd

def convert_historic_bars_element_to_array(element_label,data):
    result_array = []

    for date, values in data.items():
        element = values[element_label]
        result_array.append(element)

    return np.array(result_array)

def convert_bar_dataframe_to_dict(df, start_datetime=None, end_datetime=None):
    # Filter the DataFrame based on start_datetime and end_datetime
    if start_datetime is not None:
        df = df[df['DateTime'] >= start_datetime]
    if end_datetime is not None:
        df = df[df['DateTime'] <= end_datetime]

    # Convert the DataFrame to dictionary with orient='records'
    data_dict = df.to_dict(orient='records')

    # Iterate over each dictionary item and modify the keys and values
    for item in data_dict:
        # Convert DateTime to the desired format
        item['DateTime'] = item['DateTime'].strftime("%Y.%m.%d %H:%M")

        # Rename the keys and convert the values to float
        item['open'] = float(item.pop('Open'))
        item['high'] = float(item.pop('High'))
        item['low'] = float(item.pop('Low'))
        item['close'] = float(item.pop('Close'))
        item['tick_volume'] = float(item.pop('Volume'))

    # Group the data by DateTime and convert it to the desired dictionary format
    grouped_data = {}
    for item in data_dict:
        datetime_str = item['DateTime']
        grouped_data[datetime_str] = {
            'open': item['open'],
            'high': item['high'],
            'low': item['low'],
            'close': item['close'],
            'tick_volume': item['tick_volume']
        }

    return grouped_data
