#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import warnings
warnings.filterwarnings("ignore")

# ===============================
# 配置区
# ===============================
N1, N2, N3 = 9, 10, 20
MIN_MARKET_CAP = 1  # 最小市值，单位亿
MIN_LIST_DAYS = 30  # 最小上市天数
HISTORY_DIR = "history"
HISTORY_DAYS = 250  # 下载历史天数
THREADS = 10
HISTORY_FILE = "selected_stock_count.csv"

# ===============================
# 工具函数
# ===============================
def sma(series, n):
    return series.rolling(n, min_periods=1).mean()

def get_stock_list(retries=3, delay=5):
    """获取沪深 + 北交所股票列表"""
    for attempt in range(1, retries+1):
        try:
            print(f"[{datetime.now()}] 开始获取股票列表（沪深 + 北交所）")
            df_all = ak.stock_zh_a_spot_em()
            df_list = []

            sh = df_all[df_all['所属交易所']=='上交所'][['代码','名称']]
            df_list.append(sh)

            sz = df_all[df_all['所属交易所']=='深交所'][['代码','名称']]
            df_list.append(sz)

            try:
                bj = ak.stock_info_bj_spot_em()
                bj = bj[['代码','名称']]
                df_list.append(bj)
                print(f"[{datetime.now()}] 北交所股票数量: {len(bj)}")
            except Exception as e:
                print(f"[错误] 获取北交所失败: {e}")

            df = pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame(columns=['代码','名称'])
            df.drop_duplicates(subset=['代码'], inplace=True)
            print(f"[{datetime.now()}] 股票列表获取完成，总数: {len(df)}")
            return df
        except Exception as e:
            print(f"[错误] 获取沪深股票失败: {e} (尝试 {attempt}/{retries})")
            pd.sleep(delay)
    return pd.DataFrame(columns=['代码','名称'])

def download_history(code, retries=3, delay=2):
    """下载单只股票历史行情，前复权"""
    for attempt in range(1, retries+1):
        try:
            df = ak.stock_zh_a_hist(symbol=code, adjust="qfq")
            if df.empty:
                raise ValueError("数据为空")
            df.sort_values("日期", inplace=True)
            df.to_csv(os.path.join(HISTORY_DIR, f"{code}.csv"), index=False)
            return df
        except Exception as e:
            print(f"[错误] 获取 {code} 历史数据失败: {e} (尝试 {attempt}/{retries})")
            import time
            time.sleep(delay)
    return None

def download_all_history(df_stocks):
    """多线程下载历史数据"""
    if not os.path.exists(HISTORY_DIR):
        os.makedirs(HISTORY_DIR)
    results = {}
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        future_to_code = {executor.submit(download_history, code): code for code in df_stocks['代码']}
        for future in as_completed(future_to_code):
            code = future_to_code[future]
            try:
                df = future.result()
                if df is not None:
                    results[code] = df
            except Exception as e:
                print(f"[错误] 下载 {code} 历史数据异常: {e}")
    return results

def select_stocks(df_histories):
    """选股逻辑"""
    selected = []
    for code, df in df_histories.items():
        if df.shape[0] < max(N1, N2, N3):
            continue
        # 剔除 ST
        name = df.iloc[0]['股票简称'] if '股票简称' in df.columns else code
        if 'ST' in name:
            continue
        lc = df['收盘'].shift(1)
        rsi1 = sma((df['收盘'] - lc).clip(lower=0), N1) / sma((df['收盘'] - lc).abs(), N1) * 100
        wr1 = (df['最高'].rolling(N2).max() - df['收盘']) / (df['最高'].rolling(N2).max() - df['最低'].rolling(N2).min()) * 100
        wr2 = (df['最高'].rolling(N3).max() - df['收盘']) / (df['最高'].rolling(N3).max() - df['最低'].rolling(N3).min()) * 100
        # 市值和上市天数可选，略过
        if rsi1.iloc[-1] > 70 and wr1.iloc[-1] < 20 and wr2.iloc[-1] < 20:
            selected.append(code)
    return selected

def plot_count_history(selected_count):
    """绘制折线图"""
    df_history = pd.DataFrame()
    if os.path.exists(HISTORY_FILE):
        df_history = pd.read_csv(HISTORY_FILE)
    today = datetime.now().strftime("%Y-%m-%d")
    df_history = pd.concat([df_history, pd.DataFrame([{"日期": today, "数量": len(selected_count)}])], ignore_index=True)
    # 补齐 21 个交易日
    df_history['日期'] = pd.to_datetime(df_history['日期'])
    while df_history.shape[0] < 21:
        df_history = pd.concat([pd.DataFrame([{"日期": df_history['日期'].min() - timedelta(days=1), "数量":0}]), df_history], ignore_index=True)
    plt.figure(figsize=(12,6))
    plt.plot(df_history['日期'], df_history['数量'], marker='o')
    plt.title("选股数量折线图")
    plt.xlabel("日期")
    plt.ylabel("数量")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("selected_stock_count.png")
    df_history.to_csv(HISTORY_FILE, index=False)
    print(f"[{datetime.now()}] 绘制选股数量折线图完成，保存文件: selected_stock_count.png")

# ===============================
# 主程序
# ===============================
def main():
    print(f"[{datetime.now()}] 开始运行自动选股程序")
    df_stocks = get_stock_list()
    if df_stocks.empty:
        print("[错误] 股票列表为空，程序退出")
        return

    histories = download_all_history(df_stocks)
    if not histories:
        print("[错误] 历史行情下载失败，程序退出")
        return

    selected = select_stocks(histories)
    print(f"[{datetime.now()}] 选股完成，总数: {len(selected)}")
    plot_count_history(selected)

if __name__ == "__main__":
    main()
