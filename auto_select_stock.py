#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import pandas as pd
import akshare as ak
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# ========== 配置区 ==========
DATA_DIR = "data"
HISTORY_DIR = os.path.join(DATA_DIR, "history")
SELECTED_CSV = "selected_stocks.csv"
COUNT_HISTORY_CSV = "selected_count_history.csv"
COUNT_HISTORY_IMG = "selected_stock_count.png"
THREAD_NUM = 10  # 多线程数量
TRADING_DAYS_BACK = 21  # 首次补齐的交易日数量
MIN_LISTED_DAYS = 30
MIN_MARKET_VALUE = 1  # 单位：亿元
# ==========================

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(HISTORY_DIR, exist_ok=True)

def log(msg):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {msg}")

# 获取股票列表
def get_stock_list():
    log("开始获取股票列表（沪深 + 北交所）")
    all_stocks = []

    try:
        sh_df = ak.stock_info_a_code_name()
        sh_df["市场"] = "上证"
        all_stocks.append(sh_df)
        log(f"沪市股票数量: {len(sh_df)}")
    except Exception as e:
        log(f"[错误] 获取上证股票失败: {e}")

    try:
        sz_df = ak.stock_info_sz_name()
        sz_df["市场"] = "深证"
        all_stocks.append(sz_df)
        log(f"深市股票数量: {len(sz_df)}")
    except Exception as e:
        log(f"[错误] 获取深证股票失败: {e}")

    try:
        bj_df = ak.stock_info_bj_stock()
        bj_df["市场"] = "北交所"
        all_stocks.append(bj_df)
        log(f"北交所股票数量: {len(bj_df)}")
    except Exception as e:
        log(f"[错误] 获取北交所股票失败: {e}")

    if not all_stocks:
        log("[错误] 没有获取到任何股票")
        return pd.DataFrame()

    df = pd.concat(all_stocks, ignore_index=True)

    # 数据清理
    df.dropna(subset=["代码"], inplace=True)
    df = df[~df["名称"].str.contains("ST|退|*")]  # 剔除ST、退市等
    df = df.reset_index(drop=True)
    log(f"总股票数量（剔除无效和ST股）: {len(df)}")
    return df

# 下载历史行情
def fetch_history(stock):
    code = stock["代码"]
    market = stock["市场"]
    filename = os.path.join(HISTORY_DIR, f"{market}_{code}.csv")

    if os.path.exists(filename):
        df = pd.read_csv(filename, parse_dates=["日期"])
        return code, df

    try:
        if market in ["上证", "深证"]:
            df = ak.stock_zh_a_daily(symbol=code, adjust="qfq")  # 前复权
        elif market == "北交所":
            df = ak.bj_stock_hist(symbol=code)
        else:
            log(f"[错误] 未知市场: {market}")
            return code, pd.DataFrame()

        if df.empty or "日期" not in df.columns:
            log(f"[错误] 获取 {code} 历史数据失败: 数据为空或缺失列")
            return code, pd.DataFrame()

        df.to_csv(filename, index=False)
        return code, df
    except Exception as e:
        log(f"[错误] 获取 {code} 历史数据失败: {e}")
        return code, pd.DataFrame()

# 选股逻辑
def select_stocks(df_history):
    selected = []
    for code, df in df_history.items():
        if df.empty or len(df) < 2:
            continue
        df = df.sort_values("日期")
        df["前收盘"] = df["收盘价"].shift(1)
        df["涨跌幅"] = (df["收盘价"] - df["前收盘"]) / df["前收盘"] * 100
        df["RSI1"] = df["涨跌幅"].rolling(9).mean()
        df["WR1"] = (df["最高价"].rolling(10).max() - df["收盘价"]) / \
                    (df["最高价"].rolling(10).max() - df["最低价"].rolling(10).min()) * 100
        df["WR2"] = (df["最高价"].rolling(20).max() - df["收盘价"]) / \
                    (df["最高价"].rolling(20).max() - df["最低价"].rolling(20).min()) * 100
        last = df.iloc[-1]
        if last["RSI1"] > 70 and last["WR1"] < 20 and last["WR2"] < 20:
            selected.append(code)
    return selected

# 绘制折线图
def plot_count_history(df_counts):
    plt.figure(figsize=(10, 5))
    plt.plot(df_counts["日期"], df_counts["数量"], marker="o")
    plt.title("每日选股数量")
    plt.xlabel("日期")
    plt.ylabel("数量")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(COUNT_HISTORY_IMG)
    log("绘制选股数量折线图完成")

# 主程序
def main():
    log("开始运行自动选股程序")
    df_stocks = get_stock_list()
    if df_stocks.empty:
        log("[错误] 股票列表为空，退出")
        return

    # 下载历史行情（多线程）
    df_history = {}
    with ThreadPoolExecutor(max_workers=THREAD_NUM) as executor:
        future_to_stock = {executor.submit(fetch_history, row): row for _, row in df_stocks.iterrows()}
        for future in as_completed(future_to_stock):
            code, hist = future.result()
            df_history[code] = hist

    log("历史行情下载完成")

    # 选股
    selected_codes = select_stocks(df_history)
    df_selected = df_stocks[df_stocks["代码"].isin(selected_codes)]
    df_selected.to_csv(SELECTED_CSV, index=False)
    log(f"选股完成，总数: {len(df_selected)}")

    # 更新选股数量历史
    today = datetime.now().strftime("%Y-%m-%d")
    if os.path.exists(COUNT_HISTORY_CSV):
        df_counts = pd.read_csv(COUNT_HISTORY_CSV)
    else:
        df_counts = pd.DataFrame(columns=["日期", "数量"])

    df_counts = pd.concat([df_counts, pd.DataFrame([{"日期": today, "数量": len(df_selected)}])],
                          ignore_index=True)
    df_counts.to_csv(COUNT_HISTORY_CSV, index=False)

    # 绘制折线图
    plot_count_history(df_counts)

if __name__ == "__main__":
    main()
