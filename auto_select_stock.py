#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import pandas as pd
import numpy as np
import akshare as ak
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from concurrent.futures import ThreadPoolExecutor, as_completed

# ===============================
# 配置
# ===============================
HISTORY_DIR = "history_data"
OUTPUT_DIR = "output"
TRADE_DAYS_HISTORY = 21  # 首次补齐最近21个交易日
MIN_MKT_CAP = 2  # 最小市值，单位亿
MIN_LIST_DAYS = 60  # 最小上市天数
THREADS = 10

os.makedirs(HISTORY_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ===============================
# 工具函数
# ===============================
def get_stock_list():
    """获取沪深 + 北交所股票列表"""
    print(f"[{datetime.now()}] 开始获取股票列表（沪深 + 北交所）")
    all_list = pd.DataFrame(columns=['代码','名称','市场'])
    try:
        sh_list = ak.stock_info_a_code_name()
        sh_list['市场'] = '沪深'
        all_list = pd.concat([all_list, sh_list], ignore_index=True)
        print(f"[{datetime.now()}] 沪深A股数量: {len(sh_list)}")
    except Exception as e:
        print(f"[{datetime.now()}] [错误] 获取沪深A股失败: {e}")

    try:
        # 北交所可以用板块或其他接口替代
        bj_df = ak.stock_board_industry_name_em()
        bj_list = bj_df[['板块代码', '板块名称']].rename(columns={'板块代码':'代码', '板块名称':'名称'})
        bj_list['市场'] = '北交所'
        all_list = pd.concat([all_list, bj_list], ignore_index=True)
        print(f"[{datetime.now()}] 北交所股票数量: {len(bj_list)}")
    except Exception as e:
        print(f"[{datetime.now()}] [错误] 获取北交所失败: {e}")

    all_list.drop_duplicates(subset=['代码'], inplace=True)
    return all_list

def download_history(stock_code):
    """下载股票历史行情，前复权"""
    try:
        df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
        if df.empty:
            raise ValueError("数据为空")
        df.sort_values("日期", inplace=True)
        df.to_csv(f"{HISTORY_DIR}/{stock_code}.csv", index=False)
        return stock_code, True
    except Exception as e:
        print(f"[{datetime.now()}] [错误] 获取 {stock_code} 历史数据失败: {e}")
        return stock_code, False

def calculate_indicators(df):
    """计算 RSI1, WR1, WR2"""
    N1, N2, N3 = 9, 10, 20
    df['LC'] = df['收盘价'].shift(1)
    df['RSI1'] = df['收盘价'].combine(df['LC'], lambda x,y: max(x-y,0))\
                 .rolling(N1).mean() / df['收盘价'].combine(df['LC'], lambda x,y: abs(x-y))\
                 .rolling(N1).mean() * 100
    df['WR1'] = (df['最高价'].rolling(N2).max() - df['收盘价']) / \
                (df['最高价'].rolling(N2).max() - df['最低价'].rolling(N2).min()) * 100
    df['WR2'] = (df['最高价'].rolling(N3).max() - df['收盘价']) / \
                (df['最高价'].rolling(N3).max() - df['最低价'].rolling(N3).min()) * 100
    return df

def select_stock(stock_code):
    """单只股票选股"""
    file_path = f"{HISTORY_DIR}/{stock_code}.csv"
    if not os.path.exists(file_path):
        return None
    df = pd.read_csv(file_path)
    if df.empty:
        return None
    df = calculate_indicators(df)
    latest = df.iloc[-1]
    # 市值及上市天数判断
    try:
        finance = ak.stock_financial_analysis_indicator(symbol=stock_code)
        if finance.empty:
            return None
        mkt_cap = finance.iloc[0].get("总市值",0)/1e8
        list_days = (datetime.now() - pd.to_datetime(finance.iloc[0].get("上市日期",datetime.now()))).days
        if mkt_cap < MIN_MKT_CAP or list_days < MIN_LIST_DAYS:
            return None
    except:
        pass
    if latest['RSI1'] > 70 and latest['WR1'] < 20 and latest['WR2'] < 20:
        return stock_code
    return None

def plot_count_history(df_history):
    """绘制选股数量折线图"""
    plt.figure(figsize=(10,6))
    plt.plot(pd.to_datetime(df_history['日期']), df_history['数量'], marker='o')
    plt.title("选股数量历史趋势")
    plt.xlabel("日期")
    plt.ylabel("选股数量")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/selected_stock_count.png")
    plt.close()

# ===============================
# 主函数
# ===============================
def main():
    print(f"[{datetime.now()}] 开始运行自动选股程序")
    stock_list = get_stock_list()
    print(f"[{datetime.now()}] 股票列表获取完成，总数: {len(stock_list)}")

    # 多线程下载历史数据
    print(f"[{datetime.now()}] 开始下载历史行情...")
    failed_list = []
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        future_to_stock = {executor.submit(download_history, code): code for code in stock_list['代码']}
        for future in as_completed(future_to_stock):
            code, success = future.result()
            if not success:
                failed_list.append(code)
    # 失败重试一次
    for code in failed_list:
        download_history(code)

    # 选股
    selected_stocks = []
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        future_to_stock = {executor.submit(select_stock, code): code for code in stock_list['代码']}
        for future in as_completed(future_to_stock):
            res = future.result()
            if res:
                selected_stocks.append(res)
    print(f"[{datetime.now()}] 选股完成，总数: {len(selected_stocks)}")

    # 保存选股结果
    df_selected = stock_list[stock_list['代码'].isin(selected_stocks)]
    df_selected.to_csv(f"{OUTPUT_DIR}/selected_stocks.csv", index=False)

    # 处理历史选股数量
    history_file = f"{OUTPUT_DIR}/stock_count_history.csv"
    today = datetime.now().strftime("%Y-%m-%d")
    if os.path.exists(history_file):
        df_history = pd.read_csv(history_file)
    else:
        df_history = pd.DataFrame(columns=["日期","数量"])
        # 首次补齐最近TRADE_DAYS_HISTORY个交易日数量
        for i in range(TRADE_DAYS_HISTORY,0,-1):
            day = datetime.now() - timedelta(days=i)
            if day.weekday() >=5:
                continue  # 跳过周末
            df_history = pd.concat([df_history, pd.DataFrame([{"日期":day.strftime("%Y-%m-%d"), "数量":0}])], ignore_index=True)

    df_history = pd.concat([df_history, pd.DataFrame([{"日期": today, "数量": len(df_selected)}])], ignore_index=True)
    df_history.to_csv(history_file, index=False)

    # 绘图
    plot_count_history(df_history)
    print(f"[{datetime.now()}] 选股历史趋势折线图已生成")

if __name__ == "__main__":
    main()
