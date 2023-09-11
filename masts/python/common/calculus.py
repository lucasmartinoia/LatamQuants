
def calculate_trailing_stop(trade_info, market_price, margin_points):
    result = None
    if trade_info['type'] == 'buy':
        price_diff = market_price - trade_info['open_price']
        jumps = int(price_diff / margin_points) # division entera
        if jumps > 0:
            new_sl = trade_info['open_price'] + (jumps-1)*margin_points
            if trade_info['SL'] < new_sl:
                result = new_sl
    elif trade_info['type'] == 'sell':
        price_diff = trade_info['open_price'] - market_price
        jumps = int(price_diff / margin_points) # division entera
        if jumps > 0:
            new_sl = trade_info['open_price'] - (jumps-1)*margin_points
            if new_sl < trade_info['SL']:
                result = new_sl
    return result

