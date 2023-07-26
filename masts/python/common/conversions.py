import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from python.common.logging_config import logger


def convert_historic_bars_element_to_array(element_label, data):
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


def get_timeframe_delta(timeframe):
    timeframe_intervals = {
        'M1': timedelta(minutes=1),
        'M5': timedelta(minutes=5),
        'M15': timedelta(minutes=15),
        'M30': timedelta(minutes=30),
        'H1': timedelta(hours=1),
        'H4': timedelta(hours=4),
        'D1': timedelta(days=1)}

    if timeframe not in timeframe_intervals:
        logger.error(
            f"has_bar_data_changed() error: invalid timeframe {timeframe}. Available timeframes: M1, M5, M15, M30, "
            f"H1, H4, D1")
        raise ValueError(
            f"has_bar_data_changed() error: invalid timeframe {timeframe}. Available timeframes: M1, M5, M15, M30, "
            f"H1, H4, D1")
    return timeframe_intervals[timeframe]


def get_bar_data_clean_date(dt, timeframe):
    logger.info(f"get_bar_data_clean_date() -> {dt} {timeframe}")
    freq = int(timeframe[1:])
    if timeframe[0] == 'D':
        clean_date = datetime(dt.year, dt.month, (dt.day - (dt.day % freq)))
    elif timeframe[0] == 'H':
        clean_date = datetime(dt.year, dt.month, dt.day, (dt.hour - (dt.hour % freq)))
    elif timeframe[0] == 'M':
        clean_date = datetime(dt.year, dt.month, dt.day, dt.hour, (dt.minute - (dt.minute % freq)))

    return clean_date


def convert_periods_to_datetime_range(periods, timeframe, end_datetime):
    # Check if there are Saturdays or Sundays between start and end datetimes
    end_datetime = get_bar_data_clean_date(end_datetime, timeframe)
    timeframe_delta = get_timeframe_delta(timeframe)
    start_datetime = end_datetime - (periods * timeframe_delta)
    current_date = end_datetime
    while current_date >= start_datetime:
        if current_date.weekday() == 5:  # Saturday
            start_datetime -= timedelta(days=1)
        elif current_date.weekday() == 6:  # Sunday
            start_datetime -= timedelta(days=1)
        current_date -= timedelta(days=1)
    return start_datetime, end_datetime


def get_lasts_from_dictionary(dictionary, n):
    if n >= len(dictionary):
        return dictionary

    keys = list(dictionary.keys())[-n:]
    return {key: dictionary[key] for key in keys}
