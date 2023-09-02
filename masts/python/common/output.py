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
