import os
import ast
import pandas as pd
import json


def get_bar_data_file_name(data_path, symbol, time_frame):
    search_for = f'{symbol}_TICK_UTCPlus03-{time_frame}'
    file_name = find_file(search_for, data_path)
    return file_name


def find_file(search_for, path):
    for root, dirs, files in os.walk(path):
        for file in files:
            if search_for in file:
                return os.path.join(root, file)


def load_qdm_data_from_file(file_name):
    df = pd.read_csv(file_name)
    df['DateTime'] = pd.to_datetime(df['Date'].astype(str) + ' ' + df['Time'])
    df = df.drop(['Date', 'Time'], axis=1)
    df = df.rename(columns={'DateTime': 'time', 'Open': 'open', 'Close': 'close', 'High': 'high', 'Low': 'low',
                            'Volume': 'volume'})
    return df.set_index('time')


def extract_dictionaries_from_file(filename, symbol=None):
    dictionaries = []
    with open(filename, 'r') as file:
        lines = file.readlines()
        for line in lines:
            dict_str = line.strip()
            try:
                dictionary = ast.literal_eval(dict_str)
                # Only take into account orders with same symbol
                if symbol is None or symbol == dictionary['symbol']:
                    dictionaries.append(dictionary)
            except (SyntaxError, ValueError):
                pass
    df = pd.DataFrame(dictionaries)
    return df


def get_daily_returns_from_file(returns_file_name):
    # Read JSON data from the file
    with open(returns_file_name, 'r') as file:
        json_data = file.read()
    # Parse the JSON data
    data_dict = json.loads(json_data)
    # Convert keys (timestamps) to datetime objects
    datetime_index = pd.to_datetime(list(data_dict.keys()), unit='ms', utc=False)
    # Convert values to float and create a Pandas Series
    data_series = pd.Series(list(data_dict.values()), index=datetime_index, name="Date", dtype='float64')
    return data_series


def get_most_recent_file(folder_path, specific_string):
    matching_files = []
    # List all files in the folder
    files = os.listdir(folder_path)
    # Filter files that contain the specific string
    for file in files:
        if specific_string in file:
            matching_files.append(file)
    # If no matching files were found, return None
    if not matching_files:
        return None
    # Get the most recently modified file
    most_recent_file = max(matching_files, key=lambda f: os.path.getmtime(os.path.join(folder_path, f)))
    return most_recent_file
