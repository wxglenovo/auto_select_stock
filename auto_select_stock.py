# auto_select_stock.py
import os
import struct
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = ['SimHei']  # 支持中文
plt.rcParams['axes.unicode_minus'] = False

TDX_DATA_DIR = "tdx_data"

def read_day_file(file_path):
    """解析通达信 .day 文件"""
    if not os.path.exists(file_path):
        return None
    record_struct = struct.Struct('<IIIIIfII')  # 日期, open, high, low, close, amount, vol, reserved
    with open(file_path, 'rb') as f:
        content = f.read()
        data = []
        for i in range(0, len(content), record_struct.size):
            record = record_struct.unpack(content[i:i+record_struct.size])
            date = datetime.strptime(str(record[0]), '%Y%m%d')
            open_price = record[1] / 100
            high = record[2] / 100
            low = record[3] / 100
            close = record[4] / 100
            amount = record[5] / 10
            vol = record[6]
            data.append([date, open_price, high, low, close, amount, vol])
    df = pd.DataFrame(data, columns=['日期','开盘','最高','最低','收盘','成交额','成交量'])
    df.sort_values('日期', inplace=True)
    return df

def load_all_stocks():
    """遍历 tdx_data 目录下所有 .day 文件"""
    stocks = {}
    for root, dirs, files in os.walk(TDX_DATA_DIR):
        for f in files:
            if f.endswith('.day'):
                code = os.path.splitext(f)[0]
                path = os.path.join(root, f)
                df = read_day_file(path)
                if df is not None:
                    stocks[code] = df
    return stocks

def filter_st(stocks):
    """剔除 ST 股等，这里示例直接返回"""
    # TODO: 可扩展读取股票名单或通过 FINANCE 字段过滤
    return stocks

def select_stock(stocks):
    """简单选股策略示例"""
    result = {}
    for code, df in stocks.items():
        if df.empty or len(df) < 21:
            continue
        last_close = df['收盘'].iloc[-1]
        if last_close > 10:  # 简单条件
            result[code] = last_close
    return result

def generate_report(selected_stocks, stocks):
    """生成 CSV 和折线图"""
    if not selected_stocks:
        print("[WARN] 没有选中股票")
        return
    # CSV
    df_csv = pd.DataFrame([{'股票代码': k, '收盘价': v} for k, v in selected_stocks.items()])
    df_csv.to_csv("selected_stocks.csv", index=False, encoding='utf-8-sig')
    print(f"[INFO] 生成 CSV → selected_stocks.csv")

    # 折线图
    daily_counts = []
    dates = []
    for i in range(21):
        date_list = []
        count = 0
        for code, df in stocks.items():
            if len(df) > i:
                if df['收盘'].iloc[-(i+1)] > 10:
                    count += 1
        daily_counts.append(count)
        # 取交易日
        sample_df = next(iter(stocks.values()))
        if len(sample_df) > i:
            dates.append(sample_df['日期'].iloc[-(i+1)])
    df_plot = pd.DataFrame({'日期': dates[::-1], '数量': daily_counts[::-1]})
    df_plot.set_index('日期', inplace=True)
    df_plot.plot(marker='o')
    plt.title("选股数量折线图")
    plt.xlabel("交易日")
    plt.ylabel("数量")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("selected_stock_count.png")
    print(f"[INFO] 生成折线图 → selected_stock_count.png")

def main():
    print("[INFO] 开始运行自动选股程序")
    print("[INFO] 加载股票数据...")
    stocks = load_all_stocks()
    if not stocks:
        print("[ERROR] 没有找到任何 .day 文件，直接退出")
        return
    print(f"[INFO] 共发现股票: {len(stocks)}")

    stocks = filter_st(stocks)
    selected = select_stock(stocks)
    print(f"[INFO] 选中股票数量: {len(selected)}")

    generate_report(selected, stocks)
    print("[INFO] 自动选股完成")

if __name__ == "__main__":
    main()
