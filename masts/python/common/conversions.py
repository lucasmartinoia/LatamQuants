import numpy as np
def convert_historic_bars_element_to_array(element_label,data):
    result_array = []

    for date, values in data.items():
        element = values[element_label]
        result_array.append(element)

    return np.array(result_array)
