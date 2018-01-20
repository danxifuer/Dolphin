from base import Strategy, PosManager, str_equals

if __name__ == '__main__':
    print('WARNING: constants module imported !!!!!!!!')
    from constants import *

SOURCE_INDEX = SOURCE.CTP
M_TICKER = b'rb1805'
M_EXCHANGE = EXCHANGE.SHFE
MIN_INTERVAL = 1


DIRECTION_NAME = {DIRECTION.Buy: 'Buy', DIRECTION.Sell: 'Sell'}
OFFSET_NAME = {OFFSET.CloseToday: 'CloseToday', OFFSET.CloseYesterday: 'CloseYesterday', OFFSET.Open: 'Open'}


def initialize(context):
    context.log_info('initialize')
    context.add_md(source=SOURCE_INDEX)
    context.add_td(source=SOURCE_INDEX)
    context.register_bar(source=SOURCE_INDEX, min_interval=MIN_INTERVAL,
                         start_time="09:00:00", end_time="23:02:00")
    context.subscribe([M_TICKER], source=SOURCE_INDEX)
    context.strategy = Strategy(context.log_info)
    context.pos_manager = PosManager(context.log_info)
    context.rid_record = []
    context.md_num = 0
    context.tick_num = 0


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


def on_bar(context, bars, min_interval, source, rcv_time):
    context.log_info('On Bar No.%s (MIN_INTERVAL) %s (SOURCE_INDEX) %s' \
                     % (context.md_num, min_interval, source))
    if min_interval == MIN_INTERVAL and source == SOURCE_INDEX and context.td_connected:
        context.log_info('(bars) %s' % bars)
        for ticker, bar in bars.items():
            if not str_equals(ticker, M_TICKER): continue
            context.md_num += 1
            target_pos = context.strategy.get_target_pos(bar)
            action = context.pos_manager.get_action(target_pos)
            if len(context.rid_record) > 0:
                context.log_info("Last order have not complete %s" % context.rid_record)
                continue
            context.log_info('Ready to insert order')
            for act in action:
                price = bar.UpperLimitPrice if act[0] == DIRECTION.Buy else bar.LowerLimitPrice
                rid = context.insert_limit_order(source=SOURCE_INDEX,
                                                 ticker=M_TICKER,
                                                 exchange_id=M_EXCHANGE,
                                                 price=price,
                                                 volume=act[2],
                                                 direction=act[0],
                                                 offset=act[1])
                context.log_info('(Insert Order) %s %s (Price) %s (Rid) %s' %
                                 (DIRECTION_NAME[act[0]],
                                  OFFSET_NAME[act[1]],
                                  price, rid))
                if rid > 0:
                    context.rid_record.append(rid)


def on_rtn_trade(context, rtn_trade, order_id, source, rcv_time):
    context.log_info("[TRADE] (InstrumentID){} (Price){} (Volume){} POS:{}".format(
        rtn_trade.InstrumentID, rtn_trade.Price, rtn_trade.Volume,
        context.get_pos(source=SOURCE_INDEX).dump()))
    if order_id in context.rid_record:
        context.pos_manager.on_trade(rtn_trade.Direction,
                                     rtn_trade.OffsetFlag,
                                     rtn_trade.Volume)
        context.rid_record.remove(order_id)


def on_error(context, error_id, error_msg, order_id, source, rcv_time):
    if order_id in context.rid_record and source == SOURCE_INDEX:
        context.trade_completed = True
    context.log_error(
        "[ERROR] (err_id){} (err_msg){} (order_id){} (source){}".format(error_id, error_msg, order_id, source))


def on_tick(context, md, source, rcv_time):
    context.tick_num += 1
    if context.tick_num > 50:
        context.tick_num = 0
        context.log_info('on tick')


def on_switch_day(context, rcv_time):
    context.log_info('On Switch Day')
    context.pos_manager.on_switch_day()
    context.register_bar(source=SOURCE_INDEX, min_interval=MIN_INTERVAL,
                         start_time="23:59:00", end_time="23:58:00")
