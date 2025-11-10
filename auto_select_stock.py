#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import struct
import datetime
import pandas as pd
import matplotlib.pyplot as plt

TDX_DATA_DIR = "tdx_data"
RESULT_CSV = "selected_stocks.csv"
COUNT_PNG = "selected_stock_count.png"
DAYS_NEED = 21

def log(msg):
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def parse_day_file(path):
    """解析单个通达信 .day 文件"""
    result = []
    if not os.path.exists(path):
        return pd.DataFrame()

    with open(path, "rb") as f:
        while True:
            buf = f.read(32)
            if not buf:
                break
            date, open_p, high, low, close, amount, vol, _ = struct.unpack("<iiiiifii", buf)
            year = date // 10000
            month = date % 10000 // 100
            day = date % 100
            result.append([datetime.date(year, month, day), open_p/100, close/100])

    return pd.DataFrame(result, columns=["date", "open", "close"])

def simple_strategy(df):
    """最近 10 天上涨 >= 6 天"""
    if df.empty or len(df) < 10:
        return False
    df10 = df.tail(10)
    rise = (df10["close"] > df10["open"]).sum()
    return rise >= 6

def main():
    log("开始运行自动选股（本地通达信数据）")

    if not os.path.exists(TDX_DATA_DIR):
        log("[错误] 缺少 TDX 数据，请先在 workflow 下载！")
        return

    selected = []
    for root, _, files in os.walk(TDX_DATA_DIR):
        for file in files:
            if file.endswith(".day"):
                code = file.replace(".day", "")
                df = parse_day_file(os.path.join(root, file))
                if simple_strategy(df):
                    selected.append(code)

    today = datetime.date.today()
    log(f"今日选出：{len(selected)} 只股票")

    # 写 CSV
    pd.DataFrame({"date": today, "code": selected}).to_csv(
        RESULT_CSV, index=False, encoding="utf-8-sig"
    )

    # 更新计数折线图
    hist_file = "selected_stock_count_history.csv"
    old = pd.read_csv(hist_file) if os.path.exists(hist_file) else pd.DataFrame(columns=["date", "count"])

    old = old.tail(DAYS_NEED - 1)
    old.loc[len(old)] = [str(today), len(selected)]
    old.to_csv(hist_file, index=False, encoding="utf-8-sig")

    plt.figure()
    plt.plot(old["date"], old["count"])
    plt.xticks(rotation=45)
    plt.title("最近 21 日选股数量")
    plt.tight_layout()
    plt.savefig(COUNT_PNG)
    log("✅ 全部完成！")

if __name__ == "__main__":
    main()
