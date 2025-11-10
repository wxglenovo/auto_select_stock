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
OUTPUT_PNG = "selected_stock_count.png"
MIN_MARKET_CAP = 5  # 亿
MIN_LIST_DAYS = 30

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

def filter_stocks(stocks):
    selected = {}
    for code, file_path in tqdm(stocks.items(), desc="筛选股票"):
        df = read_day_file(file_path)
        if df is None or df.empty:
            continue
        # 剔除上市天数不足
        if (df["日期"].max() - df["日期"].min()).days < MIN_LIST_DAYS:
            continue
        df = calc_rsi_wr(df)
        # 选股条件：RSI>70 & WR1<20 & WR2<20
        last_row = df.iloc[-1]
        if last_row["RSI"] > 70 and last_row["WR1"] < 20 and last_row["WR2"] < 20:
            selected[code] = last_row["收盘"]
    return selected

def main():
    print("[INFO] 开始运行自动选股程序")
    stocks = get_all_stocks()
    print(f"[INFO] 共发现股票: {len(stocks)}")
    if not stocks:
        print("[错误] 没有找到任何 .day 文件，直接退出")
        return

    selected = filter_stocks(stocks)
    print(f"[INFO] 选中股票数量: {len(selected)}")

    if selected:
        # 保存 CSV
        df_out = pd.DataFrame(list(selected.items()), columns=["代码","收盘"])
        df_out.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
        print(f"[INFO] 生成 CSV → {OUTPUT_CSV}")

        # 生成折线图
        plt.figure(figsize=(10,6))
        df_out["收盘"].plot(kind="line", title="选股数量")
        plt.ylabel("收盘价")
        plt.xlabel("股票代码")
        plt.tight_layout()
        plt.savefig(OUTPUT_PNG)
        print(f"[INFO] 生成折线图 → {OUTPUT_PNG}")
    else:
        print("[INFO] 没有股票满足条件")

if __name__ == "__main__":
    main()
