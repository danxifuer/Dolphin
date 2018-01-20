import numpy as np
from collections import deque

if __name__ == '__main__':
    print('WARNING: constants module imported !!!!!!!!')
    from constants import *

SOURCE_INDEX = SOURCE.CTP
M_TICKER = b'rb1805'
M_EXCHANGE = EXCHANGE.SHFE
TRADED_VOLUME_LIMIT = 500
SHORT_PERIOD = 1
LONG_PERIOD = 2
MIN_INTERVAL = 1
SIGNAL_FILE = '/opt/kungfu/buy_or_sold.txt'

POS_NULL = 'POS_NULL'
POS_LONG = 'POS_LONG'
POS_SHORT = 'POS_SHORT'

STATUS_ACTION = {
    POS_NULL: {
        (True, True): (DIRECTION.Buy, OFFSET.Open),  # (True, True) means (predict price up, people signal up)
        (False, False): (DIRECTION.Sell, OFFSET.Open),
        (True, False): None,
        (False, True): None,
    },
    POS_LONG: {
        (True, True): None,
        (False, False): (DIRECTION.Sell, OFFSET.CloseToday),
        (True, False): (DIRECTION.Sell, OFFSET.CloseToday),
        (False, True): (DIRECTION.Sell, OFFSET.CloseToday)
    },
    POS_SHORT: {
        (True, True): (DIRECTION.Buy, OFFSET.CloseToday),
        (False, False): None,
        (True, False): (DIRECTION.Buy, OFFSET.CloseToday),
        (False, True): (DIRECTION.Buy, OFFSET.CloseToday)
    }
}

ACTION_NAME = {
    (DIRECTION.Buy, OFFSET.CloseToday): ('Buy', 'CloseToday'),
    (DIRECTION.Sell, OFFSET.CloseToday): ('Sell', 'CloseToday'),
    (DIRECTION.Buy, OFFSET.Open): ('Buy', 'Open'),
    (DIRECTION.Sell, OFFSET.Open): ('Sell', 'Open'),
}


class signal():
    pass


def read_signal_file():
    with open(SIGNAL_FILE) as fi:
        signal = fi.readline().strip()
        if signal not in ('1', '0'):
            print('ERROR: signal file content error ', signal)
        return bool(int(signal))


def parse_str(string):
    if isinstance(string, bytes):
        return string.decode()
    return string


def str_equals(l_str, r_str):
    return parse_str(l_str) == parse_str(r_str)


def print_bar(bar):
    print('(TradingDay)', bar.TradingDay,
          ' (InstrumentID)', bar.InstrumentID,
          ' (UpperLimitPrice)', bar.UpperLimitPrice,
          ' (LowerLimitPrice)', bar.LowerLimitPrice,
          ' (StartUpdateTime)', bar.StartUpdateTime,
          ' (StartUpdateMillisec)', bar.StartUpdateMillisec,
          ' (EndUpdateTime)', bar.EndUpdateTime,
          ' (EndUpdateMillisec)', bar.EndUpdateMillisec,
          ' (Open)', bar.Open,
          ' (Close)', bar.Close,
          ' (Low)', bar.Low,
          ' (High)', bar.High,
          ' (Volume)', bar.Volume,
          ' (StartVolume)', bar.StartVolume,
          ' (Turnover)', bar.Turnover,
          ' (StartTurnover)', bar.StartTurnover)


def compute_5_700(data):
    data = np.array(data)
    if len(data) > 0:
        volume, amount = np.split(data, [1], axis=1)
        ma_5 = None
        ma_700 = None
        if volume.shape[0] < SHORT_PERIOD:
            return ma_5, ma_700
        ma_5 = np.sum(amount[-SHORT_PERIOD:]) / np.sum(volume[-SHORT_PERIOD:])
        if volume.shape[0] >= LONG_PERIOD:
            ma_700 = np.sum(amount[-LONG_PERIOD:]) / np.sum(volume[-LONG_PERIOD:])
        return ma_5, ma_700


def initialize(context):
    context.log_info('initialize')
    context.add_md(source=SOURCE_INDEX)
    context.add_td(source=SOURCE_INDEX)
    context.register_bar(source=SOURCE_INDEX, min_interval=MIN_INTERVAL,
                         start_time="09:00:00", end_time="23:02:00")
    context.subscribe([M_TICKER], source=SOURCE_INDEX)
    # necessary initialization of internal fields.
    context.person_direction = read_signal_file()
    context.log_info('(OUR SIGNAL) %s' % context.person_direction)
    context.td_connected = False
    context.trade_completed = True
    context.md_num = 0
    context.volume = 0
    context.on_bar_count = 1
    # ========= bind and initialize a signal ========
    context.signal = signal()
    context.signal.name = "sample_signal"
    context.signal.TickPrice = deque(maxlen=LONG_PERIOD + 2)
    context.signal.pos_status = POS_NULL
    context.signal.trade_size = 1


def on_pos(context, pos_handler, request_id, source, rcv_time):
    if request_id == -1 and source == SOURCE_INDEX:
        context.td_connected = True
        context.log_info("td connected")
        if pos_handler is None:
            context.set_pos(context.new_pos(source=source), source=source)
        else:
            context.log_info('(Already Have Position) {}'.format(pos_handler.dump()))
    else:
        context.log_debug("[RSP_POS] {}".format(pos_handler.dump()))


def on_tick(context, md, source, rcv_time):
    pass
    # context.log_info('on tick (InstrumentID) %s' % md.InstrumentID)


def on_bar(context, bars, min_interval, source, rcv_time):
    context.log_info('On Bar No.%s (MIN_INTERVAL) %s (SOURCE_INDEX) %s' \
                     % (context.md_num, min_interval, source))
    if min_interval == MIN_INTERVAL and source == SOURCE_INDEX and context.td_connected:
        context.log_info('(bars) %s' % bars)
        for ticker, bar in bars.items():
            if not str_equals(ticker, M_TICKER):
                context.log_info('(Receive Other Ticker) %s' % ticker)
                continue
            context.signal.TickPrice.append((bar.Volume, bar.Turnover))
            context.md_num += 1
            if context.md_num > SHORT_PERIOD:
                ma_5, ma_700 = compute_5_700(context.signal.TickPrice)
                context.log_info('(MA_5)%s (MA_700)%s' % (ma_5, ma_700))
                if ma_700 is not None:
                    ma_direction = ma_5 > ma_700
                    context.log_info('Check Whether To Insert Order')
                    if not context.trade_completed:
                        context.log_info('Last trade have not complete')
                        continue
                    event = (ma_direction, context.person_direction)
                    status = context.signal.pos_status
                    action = STATUS_ACTION[status][event]
                    if action is not None:
                        price = bar.UpperLimitPrice if action[0] == DIRECTION.Buy else bar.LowerLimitPrice
                        context.rid = context.insert_limit_order(source=SOURCE_INDEX,
                                                                 ticker=M_TICKER,
                                                                 exchange_id=M_EXCHANGE,
                                                                 price=price,
                                                                 volume=context.signal.trade_size,
                                                                 direction=action[0],
                                                                 offset=action[1])
                        context.log_info('(Insert Order Action) %s (Price) %s (Rid) %s' %
                                         (ACTION_NAME[action], price, context.rid))
                        if context.rid > 0:
                            context.trade_completed = False
                    else:
                        context.log_info('Keep Position')
    if context.on_bar_count % 5 == 0:
        context.person_direction = read_signal_file()
        context.log_info('(Reread OUR SIGNAL) %s' % context.person_direction)
    context.on_bar_count += 1


def on_rtn_trade(context, rtn_trade, order_id, source, rcv_time):
    context.log_info("[TRADE] (InstrumentID){} (Price){} (Volume){} POS:{}".format(
        rtn_trade.InstrumentID, rtn_trade.Price, rtn_trade.Volume,
        context.get_pos(source=SOURCE_INDEX).dump()))
    context.log_info('(TradeVolume) %s (Direction) %s' % (rtn_trade.Volume,  rtn_trade.Direction))
    if context.rid == order_id:
        context.volume += rtn_trade.Volume
        context.trade_completed = True
        if str_equals(rtn_trade.OffsetFlag, OFFSET.Open):
            if str_equals(rtn_trade.Direction, DIRECTION.Buy):
                context.signal.pos_status = POS_LONG
            elif str_equals(rtn_trade.Direction, DIRECTION.Sell):
                context.signal.pos_status = POS_SHORT
        elif str_equals(rtn_trade.OffsetFlag, OFFSET.Close):
            context.signal.pos_status = POS_NULL


def on_error(context, error_id, error_msg, order_id, source, rcv_time):
    if order_id == context.rid and source == SOURCE_INDEX:
        context.trade_completed = True
    context.log_error(
        "[ERROR] (err_id){} (err_msg){} (order_id){} (source){}".format(error_id, error_msg, order_id, source))


def on_switch_day(context, rcv_time):
    context.log_info('On Switch Day')
    context.person_direction = read_signal_file()
    context.log_info('OUR SIGNAL: %s' % context.person_direction)
    context.register_bar(source=SOURCE_INDEX, min_interval=MIN_INTERVAL,
                         start_time="23:59:00", end_time="23:58:00")
