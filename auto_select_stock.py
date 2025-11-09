#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

# ------------------ 配置 ------------------
N1, N2, N3 = 9, 10, 20
MIN_MARKET_CAP = 1  # 单位：亿
MIN_LIST_DAYS = 30
HISTORY_DIR = "history"
HISTORY_FILE = "selected_stock_count.csv"
THREADS = 10
# -----------------------------------------

# ------------------ 工具函数 ------------------
def get_stock_list():
    print(f"[{datetime.now()}] 开始获取股票列表（沪深 + 北交所）")
    df_list = []
    try:
        df_all = ak.stock_zh_a_spot_em()
        # 沪A
        sh = df_all[df_all['所属交易所']=='上交所'][['代码','名称']]
        df_list.append(sh)
        # 深A
        sz = df_all[df_all['所属交易所']=='深交所'][['代码','名称']]
        df_list.append(sz)
        # 北交所
        try:
            bj = ak.stock_info_bj_spot_em()
            bj = bj[['代码','名称']]
            df_list.append(bj)
            print(f"[{datetime.now()}] 北交所股票数量: {len(bj)}")
        except Exception as e:
            print(f"[错误] 获取北交所失败: {e}")
    except Exception as e:
        print(f"[错误] 获取沪深股票失败: {e}")

    if df_list:
        df = pd.concat(df_list, ignore_index=True)
        df.drop_duplicates(subset=['代码'], inplace=True)
    else:
        df = pd.DataFrame(columns=['代码','名称'])
    print(f"[{datetime.now()}] 股票列表获取完成，总数: {len(df)}")
    return df

def download_history(code):
    for attempt in range(3):
        try:
            df = ak.stock_zh_a_hist(symbol=code, adjust="qfq")
            if df.empty:
                raise ValueError("数据为空")
            df = df.sort_values("日期")
            return df
        except Exception as e:
            print(f"[错误] 获取 {code} 历史数据失败: {e} (尝试 {attempt+1}/3)")
    return None

def download_all_history(df_stocks):
    if not os.path.exists(HISTORY_DIR):
        os.makedirs(HISTORY_DIR)
    stock_data = {}
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = {executor.submit(download_history, code): code for code in df_stocks['代码']}
        for future in as_completed(futures):
            code = futures[future]
            data = future.result()
            if data is not None:
                stock_data[code] = data
    return stock_data

def calculate_indicators(df):
    df = df.copy()
    df['LC'] = df['收盘'].shift(1)
    df['RSI1'] = df[['收盘','LC']].apply(lambda x: max(x['收盘']-x['LC'],0), axis=1).rolling(N1).mean() / \
                 df[['收盘','LC']].apply(lambda x: abs(x['收盘']-x['LC']), axis=1).rolling(N1).mean() * 100
    df['HHV10'] = df['最高'].rolling(N2).max()
    df['LLV10'] = df['最低'].rolling(N2).min()
    df['WR1'] = 100*(df['HHV10']-df['收盘'])/(df['HHV10']-df['LLV10'])
    df['HHV20'] = df['最高'].rolling(N3).max()
    df['LLV20'] = df['最低'].rolling(N3).min()
    df['WR2'] = 100*(df['HHV20']-df['收盘'])/(df['HHV20']-df['LLV20'])
    return df

def select_stocks(stock_data, df_info):
    selected = []
    today = datetime.now().strftime("%Y-%m-%d")
    for code, df in stock_data.items():
        if df.empty:
            continue
        df = calculate_indicators(df)
        last_row = df.iloc[-1]
        # 剔除未交易
        if last_row['收盘'] == 0:
            continue
        # 剔除ST
        name = df_info.loc[df_info['代码']==code,'名称'].values[0]
        if 'ST' in name:
            continue
        # 市值和天数过滤（简化处理）
        if last_row['成交额'] < MIN_MARKET_CAP*1e8 or len(df) < MIN_LIST_DAYS:
            continue
        if last_row['RSI1']>70 and last_row['WR1']<20 and last_row['WR2']<20:
            selected.append({'代码':code,'名称':name})
    return pd.DataFrame(selected)

def plot_count_history(df_selected):
    today = datetime.now().strftime("%Y-%m-%d")
    if os.path.exists(HISTORY_FILE):
        df_history = pd.read_csv(HISTORY_FILE, parse_dates=['日期'])
    else:
        df_history = pd.DataFrame(columns=['日期','数量'])
    df_history = pd.concat([df_history, pd.DataFrame([{'日期':today,'数量':len(df_selected)}])], ignore_index=True)
    df_history['日期'] = pd.to_datetime(df_history['日期'])
    df_history.sort_values('日期', inplace=True)
    # 补齐前21个交易日
    min_date = df_history['日期'].min()
    start_date = min_date - pd.Timedelta(days=21)
    all_days = pd.date_range(start=start_date, end=df_history['日期'].max(), freq='B')  # 跳过周末
    df_history = df_history.set_index('日期').reindex(all_days, fill_value=0).rename_axis('日期').reset_index()
    plt.figure(figsize=(10,5))
    plt.plot(df_history['日期'], df_history['数量'], marker='o')
    plt.xlabel("日期")
    plt.ylabel("选股数量")
    plt.title("每日选股数量折线图")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("selected_stock_count.png")
    print(f"[{datetime.now()}] 绘制选股数量折线图完成，保存文件: selected_stock_count.png")
    df_history.to_csv(HISTORY_FILE, index=False)

# ------------------ 主函数 ------------------
def main():
    print(f"[{datetime.now()}] 开始运行自动选股程序")
    df_stocks = get_stock_list()
    if df_stocks.empty:
        print(f"[错误] 股票列表为空，程序退出")
        return
    stock_data = download_all_history(df_stocks)
    df_selected = select_stocks(stock_data, df_stocks)
    print(f"[{datetime.now()}] 选股完成，总数: {len(df_selected)}")
    df_selected.to_csv("selected_stocks.csv", index=False, encoding='utf-8-sig')
    plot_count_history(df_selected)

if __name__ == "__main__":
    main()
