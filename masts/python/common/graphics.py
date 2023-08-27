import finplot as fplt
import pandas as pd
import matplotlib.pyplot as plt

def generate_trade_chart(df, trade_data):
    # Convert bar_data_list to a DataFrame
    df['DateTime'] = pd.to_datetime(df['DateTime'])
    df.set_index('DateTime', inplace=True)
    df.columns = ['date', 'open', 'high', 'low', 'close']

    # Convert open_time and close_time to datetime objects
    trade_data['open_time'] = pd.to_datetime(trade_data['open_time'])
    trade_data['close_time'] = pd.to_datetime(trade_data['close_time'])

    # Create the candlestick chart
    #fplt.candlestick_ochl(df[['date', 'open', 'close', 'high', 'low']])

    # Create the candlestick chart using finplot
    ax, ax2 = fplt.create_plot('Candlestick Chart with Trade Data', rows=2)

    # Plot candlestick chart
    fplt.candlestick_ochl(df[['date', 'open', 'close', 'high', 'low']], ax=ax)

    # Plot trade data points
    color = 'b' if trade_data['type'] == 'buy' else 'r'
    #ax.plot([trade_data['open_time'].floor('T'), trade_data['close_time']], [trade_data['open_price'].floor('T'), trade_data['close_price']], color=color)

    # Set chart title and axis labels
    #fplt.title('Candlestick Chart with Trade Data')
    #ax.set_xlabel('Date')
    #ax.set_ylabel('Price')

    # Save the chart as an image
    ticket_no = trade_data['ticket_no']
    image_name = f"trade_no_{ticket_no}.png"
    fplt.savefig(image_name, dpi=150)

    #plt.close()  # Close the plot to free up resources
    return image_name
