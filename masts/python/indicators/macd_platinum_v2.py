import talib
import numpy as np
import matplotlib.pyplot as plt
from python.common.logging_config import logger

class macd_platinum_v2:
    def __init__(self, close, volume):
        self.close = close
        self.volume = volume

    def normalize(self, series, Length):
        h = talib.MAX(series, Length)
        l = talib.MIN(series, Length)
        res = (series - l) / (h - l)
        return res

    def calculate_macd(self):
        logger.debug('macd_platinum.calculate_macd()')
        src10 = self.close
        smooth = 5
        Length = 21
        len = 5
        fastLength = 12
        slowLength = 26
        signalLength = 9

        ma3 = talib.WMA(src10 * self.volume, len) / talib.WMA(self.volume, len)
        result1 = self.normalize(ma3, Length)
        m1 = talib.SMA(result1, smooth)
        m2 = talib.SMA(result1 * 100, smooth)
        source = self.close

        # Fast line
        ma1 = talib.EMA(source, fastLength)
        ma2 = talib.EMA(ma1, fastLength)
        zerolagEMA = ((2 * ma1) - ma2)

        # Slow line
        mas1 = talib.EMA(source, slowLength)
        mas2 = talib.EMA(mas1, slowLength)
        zerolagslowMA = ((2 * mas1) - mas2)

        # MACD line
        blueMACD = (zerolagEMA - zerolagslowMA)*10.0

        # Signal line
        emasig1 = talib.EMA(blueMACD, signalLength)
        emasig2 = talib.EMA(emasig1, signalLength)
        orgMACD = (2 * emasig1) - emasig2

        hist = blueMACD - orgMACD
        print('blueMACD: ', blueMACD)
        return blueMACD, orgMACD, hist

    def plot_macd(self):
        blueMACD, orgMACD, hist = self.calculate_macd()

        plt.plot(blueMACD, color='aqua', linewidth=1, label='MACD line')
        plt.plot(orgMACD, color='orange', linewidth=1, label='Signal')
        plt.axhline(0.0, color='#777777')

        circleYPosition = orgMACD * 1

        dotColor = np.where(hist > 0, 'aqua', '#ff0000')
        plt.scatter(np.where(np.logical_and(np.greater(blueMACD, orgMACD))), circleYPosition, marker='o', s=100, c=dotColor, label='Dots')
        plt.scatter(np.where(np.logical_and(np.less(blueMACD, orgMACD))), circleYPosition, marker='o', s=100, c=dotColor, label='Dots')

        plt.legend()
        plt.show()
