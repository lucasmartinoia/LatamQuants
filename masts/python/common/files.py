import os
from os.path import join, exists

def get_bar_data_file_name(data_path, symbol, time_frame):
    search_for = f'{symbol}-{time_frame}'
    file_name = find_file(search_for, data_path)
    return file_name

def find_file(search_for, path):
    for root, dirs, files in os.walk(path):
        for file in files:
            if search_for in file:
                return os.path.join(root, file)