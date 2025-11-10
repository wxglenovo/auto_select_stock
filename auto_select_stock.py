# auto_select_stock.py
import os
import struct
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm
from datetime import datetime, timedelta

# 配置
TDX_DATA_DIR = "tdx_data"
OUTPUT_CSV = "selected_stocks.csv"
OUTPUT_DAILY_COUNT_CSV = "daily_selected_count.csv"
OUTPUT_PNG = "selected_stock_count.png"
MIN_LIST_DAYS = 30  # 上市天数

# RSI + WR 参数
N1 = 9
N2 = 10
N3 = 20

def read_day_file(file_path):
    """解析通达信 .day 文件"""
    try:
        with open(file_path, "rb") as f:
            buf = f.read()
        record_size = 32
        num_records = len(buf) // record_size
        data = []
        for i in range(num_records):
            offset = i * record_size
            r = struct.unpack("<IIIIIfII", buf[offset:offset+record_size])
            date = r[0]
            y = date // 10000
            m = (date % 10000) // 100
            d = date % 100
            close = r[3] / 100
            high = r[1] / 100
            low = r[2] / 100
            openp = r[4] / 100
            vol = r[5]
            data.append([datetime(y, m, d), openp, high, low, close, vol])
        df = pd.DataFrame(data, columns=["日期","开盘","最高","最低","收盘","成交量"])
        df.sort_values("日期", inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df
    except Exception as e:
        print(f"[错误] 解析 {file_path} 失败: {e}")
        return None

def get_all_stocks(data_dir=TDX_DATA_DIR):
    """扫描 tdx_data 目录下所有 .day 文件"""
    stocks = {}
    for root, _, files in os.walk(data_dir):
        for f in files:
            if f.endswith(".day"):
                code = os.path.splitext(f)[0]
                stocks[code] = os.path.join(root, f)
    return stocks

def calc_rsi_wr(df):
    LC = df["收盘"].shift(1)
    delta = df["收盘"] - LC
    delta_up = delta.clip(lower=0)
    delta_abs = delta.abs()
    rsi = delta_up.rolling(N1).mean() / delta_abs.rolling(N1).mean() * 100
    hhv_high_N2 = df["最高"].rolling(N2).max()
    llv_low_N2 = df["最低"].rolling(N2).min()
    hhv_high_N3 = df["最高"].rolling(N3).max()
    llv_low_N3 = df["最低"].rolling(N3).min()
    wr1 = 100*(hhv_high_N2 - df["收盘"])/(hhv_high_N2 - llv_low_N2)
    wr2 = 100*(hhv_high_N3 - df["收盘"])/(hhv_high_N3 - llv_low_N3)
    df["RSI"] = rsi
    df["WR1"] = wr1
    df["WR2"] = wr2
    return df

def daily_selected_count(stocks):
    """统计每日选股数量"""
    all_dates = set()
    dfs = {}
    for code, file_path in tqdm(stocks.items(), desc="读取股票数据"):
        df = read_day_file(file_path)
        if df is None or df.empty:
            continue
        if (df["日期"].max() - df["日期"].min()).days < MIN_LIST_DAYS:
            continue
        df = calc_rsi_wr(df)
        dfs[code] = df
        all_dates.update(df["日期"])
    all_dates = sorted(all_dates)
    date_counts = {}
    for date in tqdm(all_dates, desc="统计每日选股数量"):
        count = 0
        for code, df in dfs.items():
            row = df[df["日期"] == date]
            if not row.empty:
                r = row.iloc[0]
                if r["RSI"] > 70 and r["WR1"] < 20 and r["WR2"] < 20:
                    count += 1
        if count > 0:
            date_counts[date] = count
    return date_counts

def main():
    print("[INFO] 开始运行自动选股程序")
    stocks = get_all_stocks()
    print(f"[INFO] 共发现股票: {len(stocks)}")
    if not stocks:
        print("[错误] 没有找到任何 .day 文件，直接退出")
        return

    date_counts = daily_selected_count(stocks)
    if not date_counts:
        print("[INFO] 没有任何日期选出股票")
        return

    # 保存每日选股数量 CSV
    df_count = pd.DataFrame(list(date_counts.items()), columns=["日期","选中数量"])
    df_count.to_csv(OUTPUT_DAILY_COUNT_CSV, index=False, encoding="utf-8-sig")
    print(f"[INFO] 生成每日选股数量 CSV → {OUTPUT_DAILY_COUNT_CSV}")

    # 保存最新一天的选中股票 CSV
    latest_date = max(date_counts.keys())
    selected_latest = {}
    for code, file_path in stocks.items():
        df = read_day_file(file_path)
        if df is None or df.empty:
            continue
        if (df["日期"].max() - df["日期"].min()).days < MIN_LIST_DAYS:
            continue
        df = calc_rsi_wr(df)
        row = df[df["日期"] == latest_date]
        if not row.empty:
            r = row.iloc[0]
            if r["RSI"] > 70 and r["WR1"] < 20 and r["WR2"] < 20:
                selected_latest[code] = r["收盘"]
    df_latest = pd.DataFrame(list(selected_latest.items()), columns=["代码","收盘"])
    df_latest.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"[INFO] 生成最新选股 CSV → {OUTPUT_CSV}")

    # 绘制折线图（休市日自动跳过）
    plt.figure(figsize=(12,6))
    df_count.set_index("日期")["选中数量"].plot(kind="line", marker="o", title="每日选股数量")
    plt.ylabel("选中数量")
    plt.xlabel("日期")
    plt.tight_layout()
    plt.savefig(OUTPUT_PNG)
    print(f"[INFO] 生成折线图 → {OUTPUT_PNG}")

if __name__ == "__main__":
    main()
