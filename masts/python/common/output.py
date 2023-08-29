import pandas as pd
import ast

def add_dictionary_to_file(filename, dictionary):
    with open(filename, 'a') as file:
        file.write(str(dictionary))
        file.write('\n')  # Add a new line after appending the dictionary

def extract_dictionaries_from_file(filename):
    dictionaries = []

    with open(filename, 'r') as file:
        lines = file.readlines()
        dict_str = ''
        for line in lines:
            if line.strip() == '':
                if dict_str:
                    try:
                        dictionary = ast.literal_eval(dict_str)
                        dictionaries.append(dictionary)
                    except (SyntaxError, ValueError):
                        pass
                    dict_str = ''
            else:
                dict_str += line

    if dict_str:
        try:
            dictionary = ast.literal_eval(dict_str)
            dictionaries.append(dictionary)
        except (SyntaxError, ValueError):
            pass

    df = pd.DataFrame(dictionaries)
    return df
