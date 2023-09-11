
def calculate_trailing_stop(trade_info, market_price, margin_points):
    result = None
    if trade_info['type'] == 'buy':
        price_diff = market_price['bid'] - trade_info['open_price']
        jumps = abs(int(price_diff / margin_points))
        if jumps > 0:
            new_sl = trade_info['open_price'] + (jumps-1)*margin_points
            if trade_info['SL'] < new_sl:
                result = new_sl
    elif trade_info['type'] == 'sell':
        price_diff = trade_info['open_price'] - market_price['ask']
        jumps = abs(int(price_diff / margin_points))
        if jumps > 0:
            new_sl = trade_info['open_price'] - (jumps-1)*margin_points
            if new_sl < trade_info['SL']:
                result = new_sl
    return result


def get_pip_value(digits):
    return 10 ** (-1 * (digits - 1))

