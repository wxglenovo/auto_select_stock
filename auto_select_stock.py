#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import akshare as ak
import pandas as pd
import numpy as np
import datetime
import os
import time
import json
import matplotlib.pyplot as plt
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# ===============================
# 配置
# ===============================
HISTORY_DIR = "history"
RESULT_CSV = "selected_stocks.csv"
COUNT_PNG = "selected_stock_count.png"
RECORD_FILE = "selection_count.json"
THREADS = 25
TRADE_DAYS = 21

# ===============================
# 工具函数
# ===============================
def log(msg):
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def today_str():
    return datetime.date.today().strftime("%Y-%m-%d")

def is_weekend_or_holiday():
    d = datetime.date.today()
    if d.weekday() >= 5:
        return True
    holiday_list = ["2025-01-01", "2025-02-01"]  # 可扩展
    return today_str() in holiday_list

# ===============================
# 获取股票列表（沪深 + 北交所）
# ===============================
def get_stock_list():
    try:
        log("开始获取沪深A股列表...")
        df_a = ak.stock_zh_a_spot_em()
        df_a = df_a[~df_a["名称"].str.contains("ST")]
        df_a = df_a[df_a["最新价"] > 0]
        df_a = df_a[df_a["代码"].str.len() == 6]

        log("尝试获取北交所股票列表...")
        try:
            df_bj = ak.stock_info_bj_name()
            df_bj.columns = ["代码", "名称"]
        except:
            log("⚠ 获取北交所失败，跳过")
            df_bj = pd.DataFrame(columns=["代码", "名称"])

        df = pd.concat([df_a[["代码", "名称"]], df_bj], ignore_index=True)
        df = df.drop_duplicates(subset="代码")
        log(f"已获取股票总数：{len(df)}")
        return df
    except Exception as e:
        log(f"[错误] 获取股票失败：{e}")
        return pd.DataFrame()

# ===============================
# 下载历史行情（单只）
# ===============================
def download_stock(code):
    try:
        file = f"{HISTORY_DIR}/{code}.csv"
        if os.path.exists(file):
            return code

        df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
        if df.empty:
            return None

        df.to_csv(file, index=False)
        return code
    except:
        return None

# ===============================
# 多线程下载行情
# ===============================
def download_all(df):
    os.makedirs(HISTORY_DIR, exist_ok=True)

    log("开始下载历史行情（多线程）...")
    ok, fail = [], []
    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        tasks = {pool.submit(download_stock, c): c for c in df["代码"]}
        for future in tqdm(as_completed(tasks), total=len(tasks), desc="下载中"):
            code = tasks[future]
            result = future.result()
            if result:
                ok.append(result)
            else:
                fail.append(code)

    if fail:
        log(f"⚠ 下载失败 {len(fail)} 只股票，已跳过")
    return ok

# ===============================
# 简易选股策略（示例：收盘 > 20日均线）
# ===============================
def select(df):
    result = []
    for _, row in df.iterrows():
        code = row["代码"]
        file = f"{HISTORY_DIR}/{code}.csv"
        if not os.path.exists(file):
            continue
        hist = pd.read_csv(file)
        if len(hist) < 20:
            continue
        close = hist["收盘"].iloc[-1]
        ma20 = hist["收盘"].tail(20).mean()
        if close > ma20:
            result.append(row)
    return pd.DataFrame(result)

# ===============================
# 记录选股数量（自动补齐 21 天）
# ===============================
def record_count(today_num):
    if os.path.exists(RECORD_FILE):
        with open(RECORD_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}

    data[today_str()] = today_num
    data = dict(sorted(data.items())[-TRADE_DAYS:])

    with open(RECORD_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data

# ===============================
# 生成折线图
# ===============================
def plot_count(data):
    plt.figure(figsize=(10, 5))
    x = list(data.keys())
    y = list(data.values())
    plt.plot(x, y, marker="o")
    plt.xticks(rotation=45)
    plt.title("最近21个交易日选股数量")
    plt.xlabel("日期")
    plt.ylabel("选股数")
    plt.tight_layout()
    plt.savefig(COUNT_PNG)
    plt.close()

# ===============================
# 主程序
# ===============================
def main():
    log("🚀 自动选股程序启动")

    if is_weekend_or_holiday():
        log("今天是周末或节假日，程序退出")
        return

    df = get_stock_list()
    if df.empty:
        log("❌ 无股票列表，退出")
        return

    download_all(df)

    log("开始执行选股策略…")
    selected = select(df)
    selected.to_csv(RESULT_CSV, index=False, encoding="utf-8-sig")
    log(f"✅ 今日选出 {len(selected)} 只股票，已保存至 {RESULT_CSV}")

    count = record_count(len(selected))
    plot_count(count)
    log(f"📈 选股数量折线图已生成：{COUNT_PNG}")

    log("✅ 程序结束")

if __name__ == "__main__":
    main()
