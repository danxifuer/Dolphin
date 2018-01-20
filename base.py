import numpy as np
from collections import deque
import plotly
from plotly.graph_objs import Data, Figure
from constants import *


def parse_str(string):
    if isinstance(string, bytes):
        return string.decode()
    return string


def str_equals(l_str, r_str):
    return parse_str(l_str) == parse_str(r_str)


class PlotLine:
    def __init__(self):
        plotly.tools.set_credentials_file(username='daiab',
                                          api_key='0XbDDTqKb2D4r1bQUH6x')
        self.ma_700 = []
        self.ma_5 = []
        self.time = []
        self._count = 0

    def add_data(self, ma_5, ma_700):
        self._count += 1
        self.ma_5.append(ma_5)
        self.ma_700.append(ma_700)
        if self._count >= 1:
            self._plot()
            self._count = 0

    def _plot(self):
        ma_5 = {
            "x": self.time,
            "y": self.ma_5,
            "name": 'ma_5',
            "type": "scatter"
        }
        ma_700 = {
            "x": self.time,
            "y": self.ma_700,
            "name": 'ma_700',
            "type": "scatter"
        }
        data = Data([ma_5, ma_700])
        layout = {"xaxis": {"tickangle": 30}}
        fig = Figure(data=data, layout=layout)
        url = plotly.plotly.plot(fig, filename='ma5_700.html')
        print(url)


class Strategy:
    def __init__(self, log_info):
        self._signal_file = '/opt/kungfu/buy_or_sold.txt'
        self._signal = self._read_signal_file()
        self._log_info = log_info
        log_info('(OUR SIGNAL) %s' % self._signal)
        self.short_period = 1
        self.long_period = 2
        self._md_num = 0
        self._price = deque(maxlen=self.long_period + 2)

    def get_target_pos(self, bar):
        self._price.append((bar.Volume, bar.Turnover))
        self._md_num += 1
        strategy_pos = self._get_strategy_pos()
        theory_pos = self._get_theory_pos()
        self._log_info('(Theory Pos)%s (Strategy Pos)%s' % (theory_pos, strategy_pos))
        if theory_pos > 0 and strategy_pos > 0:
            return 1
        elif theory_pos < 0 and strategy_pos < 0:
            return -1
        else:
            return 0

    def _get_theory_pos(self):
        self._md_num += 1
        if self._md_num % 5 == 0:
            self._signal = self._read_signal_file()
            self._log_info('(OUR SIGNAL) %s' % self._signal)
        return self._signal

    def _get_strategy_pos(self):
        ma_5, ma_700 = self._compute_5_700(self._price)
        if ma_5 is None or ma_700 is None:
            return 0
        return 1 if ma_5 >= ma_700 else -1

    def _read_signal_file(self):
        with open(self._signal_file) as fi:
            signal = fi.readline().strip()
            if signal not in ('1', '0', '-1'):
                print('ERROR: signal file content error ', signal)
            return int(signal)

    def _compute_5_700(self, data):
        data = np.array(data)
        if len(data) > 0:
            volume, amount = np.split(data, [1], axis=1)
            ma_5 = None
            ma_700 = None
            if volume.shape[0] < self.short_period:
                return ma_5, ma_700
            ma_5 = np.sum(amount[-self.short_period:]) / np.sum(volume[-self.short_period:])
            if volume.shape[0] >= self.long_period:
                ma_700 = np.sum(amount[-self.long_period:]) / np.sum(volume[-self.long_period:])
            self._log_info('(MA5)%s (MA700)%s' % (ma_5, ma_700))
            return ma_5, ma_700


class PosManager:
    YES = 'yesterday'
    TODAY = 'today'

    def __init__(self, log_info):
        self._pos_record = {self.YES: 0, self.TODAY: 0}
        self._log_info = log_info
        self._log_info('(PosManager Init Pos) %s' % self._pos_record)

    def init_pos(self, yes=0, today=0):
        self._pos_record[self.YES] = yes
        self._pos_record[self.TODAY] = today
        self._log_info('(PosManager Re Init Pos) %s' % self._pos_record)

    def on_switch_day(self):
        self._log_info('(PosManager Before On Switch Day) %s' % self._pos_record)
        self._pos_record[self.YES] += self._pos_record[self.TODAY]
        self._pos_record[self.TODAY] = 0
        self._log_info('(PosManager After On Switch Day) %s' % self._pos_record)

    def on_trade(self, direction, offset, volume):
        sign = 1 if str_equals(direction, DIRECTION.Buy) else -1
        self._log_info('Trade Volume %s Direction %s OFFSET %s Sign %s' % (volume, direction, offset, sign))
        volume = sign * volume
        if str_equals(offset, OFFSET.Open):
            self._pos_record[self.TODAY] += volume
        elif str_equals(offset, OFFSET.CloseToday):
            self._pos_record[self.TODAY] += volume
        elif str_equals(offset, OFFSET.Close):
            self._pos_record[self.TODAY] += volume
        elif str_equals(offset, OFFSET.CloseYesterday):
            self._pos_record[self.YES] += volume
        else:
            self._log_info('ERROR %s !!!!!!!!!' % offset)
        self._log_info('(PosManager After Trade) %s' % self._pos_record)

    def get_action(self, target_pos):
        assert self._pos_record[self.YES] * self._pos_record[self.TODAY] >= 0, "%s vs %s" % \
               (self._pos_record[self.YES], self._pos_record[self.TODAY])
        total_pos = self._pos_record[self.YES] + self._pos_record[self.TODAY]
        is_buy = target_pos > total_pos
        is_sell = target_pos < total_pos
        action = []
        if total_pos >= 0 and is_buy:
            direction = DIRECTION.Buy
            action.append((direction, OFFSET.Open, abs(target_pos - total_pos)))
        if total_pos > 0 and is_sell:
            direction = DIRECTION.Sell
            if self._pos_record[self.TODAY] > target_pos:
                action.append((direction, OFFSET.CloseToday, self._pos_record[self.TODAY] - target_pos))
                if self._pos_record[self.YES] > 0:
                    action.append((direction, OFFSET.CloseYesterday, self._pos_record[self.YES]))
            elif self._pos_record[self.TODAY] < target_pos:
                action.append((direction, OFFSET.CloseYesterday, abs(total_pos - target_pos)))
            else:
                pass
        if total_pos <= 0 and is_sell:
            direction = DIRECTION.Sell
            action.append((direction, OFFSET.Open, abs(target_pos - total_pos)))
        if total_pos < 0 and is_buy:
            direction = DIRECTION.Buy
            if self._pos_record[self.TODAY] < target_pos:
                action.append((direction, OFFSET.CloseToday, abs(self._pos_record[self.TODAY] - target_pos)))
                if self._pos_record[self.YES] < 0:
                    action.append((direction, OFFSET.CloseYesterday, abs(self._pos_record[self.YES])))
            elif self._pos_record[self.TODAY] > target_pos:
                action.append((direction, OFFSET.CloseYesterday, abs(total_pos - target_pos)))
            else:
                pass
        else:
            pass
        self._log_info('PosManager Action %s' % action)
        return action


if __name__ == '__main__':
    a = {DIRECTION.Buy: 'Buy', DIRECTION.Sell: 'Sell'}
    b = {OFFSET.CloseToday: 'CloseToday', OFFSET.CloseYesterday: 'CloseYesterday', OFFSET.Open: 'Open'}
    manager = PosManager(print)
    manager.init_pos(0, 0)
    action = manager.get_action(-1)
    for act in action:
        print('DIRECTION:', a[act[0]], ' OFFSET:', b[act[1]], ' Volume:', act[2])
