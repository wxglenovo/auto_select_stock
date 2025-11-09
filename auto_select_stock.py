#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import pandas as pd
import akshare as ak
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------------- 配置 ----------------
RESULT_CSV = "selected_stocks.csv"
COUNT_PNG = "selected_stock_count.png"
MAX_THREADS = 10
TRADING_DAYS = 21  # 最近交易日数量
HIST_DIR = "history_data"
os.makedirs(HIST_DIR, exist_ok=True)

# ---------------- 工具函数 ----------------
def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def get_last_trading_day(date):
    # 简单跳过周末
    while date.weekday() >= 5:
        date -= timedelta(days=1)
    return date

def is_valid_stock(stock):
    # 剔除ST股和未上市股票
    code = stock['代码'] if '代码' in stock else stock['股票代码']
    name = stock['名称'] if '名称' in stock else stock['股票简称']
    if 'ST' in name or code.startswith('688') or code.startswith('300') or code.startswith('0') or code.startswith('6'):
        return True
    return True

# ---------------- 获取股票列表 ----------------
def get_stock_list():
    log("开始获取股票列表（沪深 + 北交所）")
    try:
        df_a = ak.stock_zh_a_spot_em()
        df_a = df_a.rename(columns={"代码": "代码", "名称": "名称"})
    except Exception as e:
        log(f"[错误] 获取沪深股票失败: {e}")
        df_a = pd.DataFrame(columns=["代码", "名称"])
    try:
        df_bj = ak.stock_info_bj_stock_name()
        df_bj = df_bj.rename(columns={"股票代码": "代码", "股票简称": "名称"})
    except Exception as e:
        log(f"[错误] 获取北交所失败: {e}")
        df_bj = pd.DataFrame(columns=["代码", "名称"])
    df_all = pd.concat([df_a, df_bj], ignore_index=True)
    df_all = df_all.drop_duplicates(subset=["代码"])
    df_all = df_all[df_all.apply(is_valid_stock, axis=1)]
    log(f"股票列表获取完成，总数: {len(df_all)}")
    if len(df_all) == 0:
        log("[错误] 股票列表为空，程序退出")
        exit(1)
    return df_all

# ---------------- 下载历史行情 ----------------
def download_stock_history(stock_code):
    try:
        file_path = os.path.join(HIST_DIR, f"{stock_code}.csv")
        if os.path.exists(file_path):
            return stock_code, file_path
        df_hist = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="")
        if df_hist.empty:
            raise ValueError("数据为空")
        df_hist.to_csv(file_path, index=False)
        return stock_code, file_path
    except Exception as e:
        log(f"[错误] 获取 {stock_code} 历史数据失败: {e}")
        return stock_code, None

def download_all_history(df_stocks):
    log("开始下载历史行情...")
    results = {}
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        future_to_code = {executor.submit(download_stock_history, code): code for code in df_stocks['代码']}
        for future in as_completed(future_to_code):
            code = future_to_code[future]
            try:
                _, file_path = future.result()
                results[code] = file_path
            except Exception as e:
                results[code] = None
                log(f"[错误] {code} 下载异常: {e}")
    return results

# ---------------- 选股逻辑 ----------------
def select_stocks(history_files):
    # 简单示例：最新收盘价大于10元的选股
    selected = []
    for code, file in history_files.items():
        if not file:
            continue
        df = pd.read_csv(file)
        df['日期'] = pd.to_datetime(df['日期'])
        last_trade = get_last_trading_day(datetime.now().date())
        df_recent = df[df['日期'] <= pd.Timestamp(last_trade)].sort_values('日期').tail(1)
        if not df_recent.empty and df_recent['收盘'].values[0] > 10:
            selected.append({
                "代码": code,
                "名称": df_recent['股票名称'].values[0] if '股票名称' in df_recent else code,
                "收盘价": df_recent['收盘'].values[0],
                "日期": last_trade
            })
    df_selected = pd.DataFrame(selected)
    return df_selected

# ---------------- 绘制折线图 ----------------
def plot_count_history(df_selected):
    df_history_file = "stock_count_history.csv"
    today = get_last_trading_day(datetime.now().date())
    if os.path.exists(df_history_file):
        df_history = pd.read_csv(df_history_file)
        df_history['日期'] = pd.to_datetime(df_history['日期'])
    else:
        df_history = pd.DataFrame(columns=["日期", "数量"])
    df_history = pd.concat([df_history, pd.DataFrame([{"日期": today, "数量": len(df_selected)}])], ignore_index=True)
    df_history.to_csv(df_history_file, index=False)

    plt.figure(figsize=(12, 6))
    plt.plot(df_history['日期'], df_history['数量'], marker='o')
    plt.title("选股数量折线图")
    plt.xlabel("日期")
    plt.ylabel("数量")
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(COUNT_PNG)
    log(f"绘制选股数量折线图完成，保存文件: {COUNT_PNG}")

# ---------------- 主程序 ----------------
def main():
    log("开始运行自动选股程序")
    df_stocks = get_stock_list()
    history_files = download_all_history(df_stocks)
    df_selected = select_stocks(history_files)
    if df_selected.empty:
        log("选股完成，总数: 0")
    else:
        df_selected.to_csv(RESULT_CSV, index=False, encoding="utf-8-sig")
        log(f"选股完成，总数: {len(df_selected)}, 保存文件: {RESULT_CSV}")
    plot_count_history(df_selected)

if __name__ == "__main__":
    main()
