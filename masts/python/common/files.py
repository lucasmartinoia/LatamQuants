import os
from os.path import join, exists
import pandas as pd
import numpy as np
import ast


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
    df = df.rename(columns={'DateTime':'time', 'Open':'open', 'Close':'close', 'High':'high', 'Low':'low', 'Volume':'volume'})
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