# -*- coding: utf-8 -*-
"""
Created on Fri Jan  8 08:40:07 2021

@author: Meva
"""

# import libraries and functions
import numpy as np
import pandas as pd
import matplotlib as mpl
import scipy
import importlib
import matplotlib.pyplot as plt
from scipy.stats import skew, kurtosis, chi2, linregress
from scipy.optimize import minimize
from numpy import linalg as LA

# import our own files and reload
import stream_functions
importlib.reload(stream_functions)
import stream_classes
importlib.reload(stream_classes)
import bollinger_bands
importlib.reload(bollinger_bands)

# inputs
backtest = bollinger_bands.backtest()
backtest.ric_long = 'TOTF.PA'
backtest.ric_short = 'REP.MC'
backtest.rolling_days = 20
backtest.level_1 = 1.
backtest.level_2 = 2.
backtest.data_cut = 0.1
backtest.data_type = 'in-sample' # in-sample out-of-sample

# load data
_, _, t = stream_functions.synchronise_timeseries(backtest.ric_long, backtest.ric_short)
cut = int(backtest.data_cut*t.shape[0])
if backtest.data_type == 'in-sample':
    df1 = t.head(cut)
elif backtest.data_type == 'out-of-sample':
    df1 = t.tail(t.shape[0]-cut)
df1 = df1.reset_index(drop=True)

# spread at current close
df1['spread'] = df1['price_1']/df1['price_2']
base = df1['spread'][0]
df1['spread'] = df1['spread'] / base

# spread at previous close
df1['spread_previous'] = df1['price_1_previous']/df1['price_2_previous']
df1['spread_previous'] = df1['spread_previous'] / base

# compute bollinger bands
size = df1.shape[0]
columns = ['lower_2','lower_1','mean','upper_1','upper_2']
mtx_bollinger = np.empty((size,len(columns)))
mtx_bollinger[:] = np.nan
for n in range(backtest.rolling_days-1,size):
    vec_price = df1['spread'].values
    vec_price = vec_price[n-backtest.rolling_days+1:n+1]
    mu = np.mean(vec_price)
    sigma = np.std(vec_price)
    m = 0
    mtx_bollinger[n][m] = mu - backtest.level_2*sigma
    m = m + 1
    mtx_bollinger[n][m] = mu - backtest.level_1*sigma
    m = m + 1
    mtx_bollinger[n][m] = mu
    m = m + 1
    mtx_bollinger[n][m] = mu + backtest.level_1*sigma
    m = m + 1
    mtx_bollinger[n][m] = mu + backtest.level_2*sigma
    m = m + 1
df2 = pd.DataFrame(data=mtx_bollinger,columns=columns)
timeseries = pd.concat([df1,df2], axis=1) # axis=0 for rows, axis=1 for columns
timeseries = timeseries.dropna()
timeseries = timeseries.reset_index(drop=True)

# plot Bollinger bands and current spread
timestamps = timeseries['date']
spread = timeseries['spread']
mu = timeseries['mean']
u1 = timeseries['upper_1']
u2 = timeseries['upper_2']
l1 = timeseries['lower_1']
l2 = timeseries['lower_2']
plt.figure()
plt.title('Spread ' + backtest.ric_long + ' / ' + backtest.ric_short)
plt.xlabel('Time')
plt.ylabel('Price')
plt.plot(timestamps, mu, color='blue', label='mean')
plt.plot(timestamps, l1, color='green', label='lower_1')
plt.plot(timestamps, u1, color='green', label='upper_1')
plt.plot(timestamps, l2, color='red', label='lower_2')
plt.plot(timestamps, u2, color='red', label='upper_2')
plt.plot(timestamps, spread, color='black', label='spread')
plt.legend(loc=0)
plt.grid()
plt.show()




# loop for backtest
size = timeseries.shape[0]
columns = ['position','entry_signal','exit_signal','pnl_daily','trade','pnl_trade']
position = 0
entry_spread = 0.
can_trade = False
size = timeseries.shape[0]
mtx_backtest = np.zeros((size,len(columns)))
for n in range(size):
    # input data for the day
    spread = timeseries['spread'][n]
    spread_previous = timeseries['spread_previous'][n]
    lower_2 = timeseries['lower_2'][n]
    lower_1 = timeseries['lower_1'][n]
    mean = timeseries['mean'][n]
    upper_1 = timeseries['upper_1'][n]
    upper_2 = timeseries['upper_2'][n]
    # reset output data for the day
    pnl_daily = 0.
    trade = 0
    pnl_trade = 0.
    # check if we can trade
    if not can_trade:
        can_trade = position == 0 and spread > lower_1 and spread < upper_1
    if not can_trade:
        continue
    # enter new position
    if position == 0: 
        entry_signal = 0
        exit_signal = 0
        if spread > lower_2 and spread < lower_1:
            entry_signal = 1 # buy signal
            position = 1
            entry_spread = spread
        elif spread > upper_1 and spread < upper_2:
            entry_signal = -1 # sell signal
            position = -1
            entry_spread = spread
    # exit long position
    elif position == 1:
        entry_signal = 0
        pnl_daily = position*(spread - spread_previous)
        if n == size-1 or spread > mean or spread < lower_2:
            exit_signal = 1 # last day or take profit or stop loss
            pnl_trade = position*(spread - entry_spread)
            position = 0
            trade = 1
            can_trade = False
        else:
            exit_signal = 0
    # exit short position
    elif position == -1:
        entry_signal = 0
        pnl_daily = position*(spread - spread_previous)
        if n == size-1 or spread < mean or spread > upper_2:
            exit_signal = 1 # last day or take profit or stop loss
            pnl_trade = position*(spread - entry_spread)
            position = 0
            trade = 1
            can_trade = False
        else:
            exit_signal = 0
        
    # save data for the day
    m = 0
    mtx_backtest[n][m] = position
    m = m + 1
    mtx_backtest[n][m] = entry_signal
    m = m + 1
    mtx_backtest[n][m] = exit_signal
    m = m + 1
    mtx_backtest[n][m] = pnl_daily
    m = m + 1
    mtx_backtest[n][m] = trade
    m = m + 1
    mtx_backtest[n][m] = pnl_trade
    
df2 = pd.DataFrame(data=mtx_backtest,columns=columns)
df = pd.concat([timeseries,df2], axis=1) # axis=0 for rows, axis=1 for columns
df = df.dropna()
df = df.reset_index(drop=True)
df['cum_pnl_daily'] = np.cumsum(df['pnl_daily'])

# compute Sharpe ratio and number of trades
vec_pnl = df['pnl_daily'].values
pnl_mean = np.round(np.mean(vec_pnl) * 252, 4)
pnl_volatility = np.round(np.std(vec_pnl) * np.sqrt(252), 4)
sharpe = np.round(pnl_mean / pnl_volatility, 4)
df3 = df[df['trade'] == 1]
nb_trades = df3.shape[0]

# plot cum pnl
plot_str = 'cumulative PNL daily ' + str(backtest.ric_long) + ' / ' + str(backtest.ric_short) + '\n'\
    + 'pnl annual mean ' + str(pnl_mean) + '\n'\
    + 'pnl annual volatility ' + str(pnl_volatility) + '\n'\
    + 'pnl annual Sharpe ' + str(sharpe)
plt.figure()
plt.title(plot_str)
plt.xlabel('Time')
plt.ylabel('cum PNL')
plt.plot(df['date'], df['cum_pnl_daily'], color='blue', label='mean')
plt.grid()
plt.show()


