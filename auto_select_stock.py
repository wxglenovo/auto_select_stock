#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import pandas as pd
import akshare as ak
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

CACHE_DIR = "history"
os.makedirs(CACHE_DIR, exist_ok=True)

def log(msg):
    print(f"[{datetime.now()}] {msg}")

def get_stock_list():
    log("开始获取股票列表（沪深 + 北交所）")
    try:
        sh_list = ak.stock_zh_a_spot_em()  # 沪深A股
        sh_list = sh_list[['代码','名称']]
        sh_list = sh_list[~sh_list['名称'].str.contains('ST|退')]
    except Exception as e:
        log(f"[错误] 获取沪深A股失败: {e}")
        sh_list = pd.DataFrame(columns=['代码','名称'])

    try:
        bj_list = ak.stock_bj_spot()  # 北交所
        bj_list = bj_list[['代码','名称']]
        bj_list = bj_list[~bj_list['名称'].str.contains('ST|退')]
    except Exception as e:
        log(f"[错误] 获取北交所失败: {e}")
        bj_list = pd.DataFrame(columns=['代码','名称'])

    df = pd.concat([sh_list, bj_list], ignore_index=True)
    df.drop_duplicates(subset=['代码'], inplace=True)
    log(f"股票列表获取完成，总数: {len(df)}")
    return df

def download_stock_history(code):
    filename = f"{CACHE_DIR}/{code}.csv"
    if os.path.exists(filename):
        try:
            df = pd.read_csv(filename, parse_dates=["日期"])
            return code, df
        except:
            os.remove(filename)

    for attempt in range(3):
        try:
            df = ak.stock_zh_a_daily(symbol=code, adjust="qfq")
            if df.empty:
                raise ValueError("数据为空")
            df.to_csv(filename, index=False)
            return code, df
        except Exception as e:
            log(f"[错误] 获取 {code} 历史数据失败: {e} (尝试 {attempt+1}/3)")
    return code, None

def download_all_histories(stock_list):
    log("开始下载历史行情...")
    results = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(download_stock_history, code): code for code in stock_list['代码']}
        for future in as_completed(futures):
            code, df = future.result()
            if df is not None:
                results[code] = df
    log("历史行情下载完成")
    return results

def select_stocks(histories):
    selected = []
    for code, df in histories.items():
        if df is None or len(df) < 21:
            continue
        df['LC'] = df['收盘价'].shift(1)
        N1, N2, N3 = 9, 10, 20
        df['RSI1'] = df['收盘价'].diff().apply(lambda x: max(x,0)).rolling(N1).mean() / df['收盘价'].diff().abs().rolling(N1).mean() * 100
        df['WR1'] = (df['最高价'].rolling(N2).max() - df['收盘价']) / (df['最高价'].rolling(N2).max() - df['最低价'].rolling(N2).min()) * 100
        df['WR2'] = (df['最高价'].rolling(N3).max() - df['收盘价']) / (df['最高价'].rolling(N3).max() - df['最低价'].rolling(N3).min()) * 100
        last = df.iloc[-1]
        if last['RSI1']>70 and last['WR1']<20 and last['WR2']<20:
            selected.append(code)
    return selected

def plot_count_history(counts):
    history_file = "selected_counts.csv"
    if os.path.exists(history_file):
        df_history = pd.read_csv(history_file, parse_dates=["日期"])
    else:
        df_history = pd.DataFrame(columns=["日期","数量"])

    today = datetime.today().strftime("%Y-%m-%d")
    df_history.loc[len(df_history)] = {"日期": today, "数量": counts}

    # 补齐前21个交易日
    while len(df_history) < 21:
        df_history = pd.concat([pd.DataFrame([{"日期": df_history['日期'].min() - timedelta(days=1), "数量":0}]), df_history], ignore_index=True)

    df_history.to_csv(history_file, index=False)
    plt.figure(figsize=(10,5))
    plt.plot(df_history['日期'], df_history['数量'], marker='o')
    plt.title("每日选股数量")
    plt.xlabel("日期")
    plt.ylabel("数量")
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("selected_stock_count.png")
    log("绘制选股数量折线图完成")

def main():
    log("开始运行自动选股程序")
    stock_list = get_stock_list()
    histories = download_all_histories(stock_list)
    selected = select_stocks(histories)
    log(f"选股完成，总数: {len(selected)}")
    plot_count_history(len(selected))
    pd.DataFrame(selected, columns=["代码"]).to_csv("selected_stocks.csv", index=False)
    log("选股结果保存完成")

if __name__ == "__main__":
    main()
