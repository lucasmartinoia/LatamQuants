import pandas as pd
import ast


def add_trade_to_file(filename, dictionary):
    copy_dict = dictionary.copy()
    copy_dict['status'] = copy_dict['status'].name
    copy_dict['open_time'] = copy_dict['open_time'].strftime('%Y-%m-%d %H:%M:%S')
    copy_dict['close_time'] = copy_dict['close_time'].strftime('%Y-%m-%d %H:%M:%S')
    add_dictionary_to_file(filename, copy_dict)


def add_dictionary_to_file(filename, dictionary):
    with open(filename, 'a') as file:
        file.write(str(dictionary))
        file.write('\n')  # Add a new line after appending the dictionary



