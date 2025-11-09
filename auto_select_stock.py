#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import akshare as ak
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings

warnings.filterwarnings("ignore")

# ---------- 配置 ----------
N1, N2, N3 = 9, 10, 20
MIN_MARKET_CAP = 5  # 亿
MIN_LIST_DAYS = 30
HISTORY_DIR = "history"
HISTORY_DAYS = 120
HISTORY_COUNT_FILE = "stock_count_history.csv"
MAX_THREADS = 10

os.makedirs(HISTORY_DIR, exist_ok=True)

# ---------- 中文字体 ----------
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

# ---------- 获取股票列表 ----------
def get_stock_list():
    print(f"[{datetime.now()}] 开始获取股票列表（沪深 + 北交所）")
    try:
        sh = ak.stock_info_a_code_name()
        sz = ak.stock_info_sz_name_code()
        df = pd.concat([sh, sz], ignore_index=True)
        df['市场'] = df['代码'].str[:2]
    except Exception as e:
        print(f"[错误] 获取沪深股票失败: {e}")
        df = pd.DataFrame(columns=['代码','名称','市场'])

    # 北交所股票通过板块接口
    try:
        bj = ak.stock_board_industry_name_em()
        if not bj.empty:
            bj = bj[['板块代码','板块名称','股票代码','股票简称']]
            bj = bj.rename(columns={'股票代码':'代码','股票简称':'名称'})
            bj['市场'] = 'bj'
            df = pd.concat([df, bj[['代码','名称','市场']]], ignore_index=True)
        print(f"[{datetime.now()}] 北交所股票数量: {len(bj)}")
    except Exception as e:
        print(f"[错误] 获取北交所失败: {e}")

    df.drop_duplicates(subset=['代码'], inplace=True)
    print(f"[{datetime.now()}] 股票列表获取完成，总数: {len(df)}")
    return df

# ---------- 下载历史行情 ----------
def download_history(code):
    for attempt in range(3):
        try:
            df = ak.stock_zh_a_daily(symbol=code, adjust="qfq")  # 前复权
            if df.empty:
                raise ValueError("数据为空")
            df['代码'] = code
            df.to_csv(f"{HISTORY_DIR}/{code}.csv", index=False)
            return code, df
        except Exception as e:
            print(f"[错误] 获取 {code} 历史数据失败: {e} (尝试 {attempt+1}/3)")
    return code, None

def download_all_history(df_stocks):
    results = []
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = {executor.submit(download_history, code): code for code in df_stocks['代码']}
        for future in as_completed(futures):
            code, df = future.result()
            if df is not None:
                results.append(df)
    if results:
        return pd.concat(results, ignore_index=True)
    else:
        return pd.DataFrame()

# ---------- 选股逻辑 ----------
def select_stocks(df_history, df_stocks):
    df_selected = []
    for code in df_stocks['代码']:
        try:
            df = df_history[df_history['代码']==code].copy()
            if df.empty:
                continue
            df['LC'] = df['收盘'].shift(1)
            df['涨跌'] = df['收盘'] - df['LC']
            df['RSI1'] = df['涨跌'].apply(lambda x: max(x,0)).rolling(N1).mean() / df['涨跌'].abs().rolling(N1).mean() *100
            df['WR1'] = (df['最高'].rolling(N2).max() - df['收盘']) / (df['最高'].rolling(N2).max() - df['最低'].rolling(N2).min()) *100
            df['WR2'] = (df['最高'].rolling(N3).max() - df['收盘']) / (df['最高'].rolling(N3).max() - df['最低'].rolling(N3).min()) *100

            last = df.iloc[-1]
            if (last['RSI1']>70 and last['WR1']<20 and last['WR2']<20):
                df_selected.append({'代码':code, '名称':df_stocks[df_stocks['代码']==code]['名称'].values[0]})
        except:
            continue
    return pd.DataFrame(df_selected)

# ---------- 绘制折线 ----------
def plot_count_history(df_selected):
    today = datetime.now().strftime('%Y-%m-%d')
    if os.path.exists(HISTORY_COUNT_FILE):
        df_history_count = pd.read_csv(HISTORY_COUNT_FILE)
    else:
        df_history_count = pd.DataFrame(columns=['日期','数量'])

    df_history_count = pd.concat([df_history_count, pd.DataFrame([{'日期':today,'数量':len(df_selected)}])], ignore_index=True)
    df_history_count.to_csv(HISTORY_COUNT_FILE, index=False)

    plt.figure(figsize=(12,6))
    plt.plot(pd.to_datetime(df_history_count['日期']), df_history_count['数量'], marker='o')
    plt.title("选股数量折线图")
    plt.xlabel("日期")
    plt.ylabel("数量")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("selected_stock_count.png")
    plt.close()
    print(f"[{datetime.now()}] 绘制选股数量折线图完成，保存文件: selected_stock_count.png")

# ---------- 主函数 ----------
def main():
    print(f"[{datetime.now()}] 开始运行自动选股程序")
    df_stocks = get_stock_list()
    if df_stocks.empty:
        print("[错误] 股票列表为空，程序退出")
        return

    print(f"[{datetime.now()}] 开始下载历史行情...")
    df_history = download_all_history(df_stocks)
    if df_history.empty:
        print("[错误] 历史数据下载为空，程序退出")
        return

    df_selected = select_stocks(df_history, df_stocks)
    print(f"[{datetime.now()}] 选股完成，总数: {len(df_selected)}")

    df_selected.to_csv("selected_stocks.csv", index=False)
    plot_count_history(df_selected)

if __name__ == "__main__":
    main()
