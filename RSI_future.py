import quantopian.algorithm as algo
import talib
import numpy as np
import pandas as pd
from quantopian.algorithm import calendars
import quantopian.optimize as opt
from quantopian.algorithm import order_optimal_portfolio


def initialize(context):
    """
    Called once at the start of the algorithm.
    """
    # Save the futures contracts we'll be trading and the corresponding proxies for the underlying's spot price.
    context.security = continuous_future('ES', offset=0, roll='volume', adjustment='mul')
    context.proxy = sid(8554)

    # Create empty keys that will later contain our window of cost of carry data.
    context.cost_of_carry_data = []
    context.cost_of_carry_quantiles = []

    context.price = 0
    context.current_position = 0
    context.period = 14
    context.rsi = 50
    context.small = 30
    context.large = 70
    context.upper = 0.8
    context.lower = 0.2
    # Rebalance every day, 1 hour after market open.

    algo.schedule_function(daily_rebalance, date_rules.every_day(), time_rules.market_open(),
                           calendar=calendars.US_EQUITIES)


def daily_rebalance(context, data):
    """
    Execute orders according to our schedule_function() timing.
    """

    # After collecting 30 days worth of data, execute our ordering logic by buying low cost of carry contracts.
    target_weight = {}

    primary = data.current(context.security, 'contract')

    period = context.period
    prices = data.history(context.proxy, 'price', 100, '1d')

    today20 = np.mean(prices[80:100])
    past20 = np.mean(prices[60:80])

    rsi = talib.RSI(prices, timeperiod=period)
    RSI = rsi[-1]
    RSIyesterday = context.rsi

    # William R
    highest = prices.rolling(20, center=False).max()
    lowest = prices.rolling(20, center=False).min()

    william = np.array(((highest - prices) / (highest - lowest)))

    LOWWR = np.nanmin(william[-10:])
    HIGHWR = np.nanmax(william[-10:])

    WR = ((highest[-1] - prices[-1]) / (highest[-1] - lowest[-1]))

    closebuy = ((context.current_position > 0 and RSI > 50) or RSI < 30)
    closeshort = (context.current_position < 0 and RSI < 50 or RSI > 70)

    if abs(today20 - past20) < 6:
        if RSIyesterday < 35 and RSI > 35 and WR < context.upper and HIGHWR > context.upper:
            target_weight[primary] = 3
            context.current_position = 5
            log.info("ranging buy")
        elif closebuy:
            target_weight[primary] = 0
            context.current_position = 0
        #           log.info("ranging closebuy")
        elif RSIyesterday > 70 and RSI < 70 and WR > context.lower and LOWWR < context.lower:
            target_weight[primary] = -3
            context.current_position = -5
            log.info("ranging short")
        elif closeshort:
            target_weight[primary] = 0
            context.current_position = 0
    #         log.info("ranging closeshort")
    else:
        if WR < context.upper and HIGHWR > context.upper:
            target_weight[primary] = 3
            context.current_position = 5
            log.info("trending buy")
        elif context.current_position > 0 and WR < 0.2:
            target_weight[primary] = 0
            context.current_position = 0
        #       log.info("trending closebuy")
        elif WR > context.lower and LOWWR < context.lower:
            target_weight[primary] = -3
            context.current_position = -5
            log.info("trending short")
        elif context.current_position < 0 and WR > 0.8:
            target_weight[primary] = 1
            context.current_position = 0
    #     log.info("trending closeshort")
    # If we have target weights, rebalance portfolio
    if target_weight:
        order_optimal_portfolio(
            opt.TargetWeights(target_weight),
            constraints=[]
        )

    context.rsi = RSI