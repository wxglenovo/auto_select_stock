# auto_select_stock.py
# -*- coding: utf-8 -*-

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import akshare as ak

# ============================
# 配置区
# ============================
DATA_DIR = r"stock_data"                 # 历史行情存放目录
STOCK_LIST_FILE = os.path.join(DATA_DIR, "all_stock_list.csv")
SELECTED_FILE = os.path.join(DATA_DIR, "selected_stocks.csv")
HISTORY_FILE = os.path.join(DATA_DIR, "stock_count_history.csv")
NUM_DAYS_BACK = 21                       # 首次补全天数
THREADS = 10                             # 并行线程数

# ============================
# 工具函数
# ============================
def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def is_trading_day(date):
    return date.weekday() < 5  # 周一到周五

# ============================
# 获取股票列表（沪深 + 北交所）
# ============================
def get_stock_list():
    log("开始获取股票列表（沪深 + 北交所）")
    os.makedirs(DATA_DIR, exist_ok=True)
    # 沪深 A 股
    sh_list = ak.stock_info_a_code_name("上证A股")
    sz_list = ak.stock_info_a_code_name("深证A股")
    # 北交所
    bj_list = ak.stock_info_bj_a_code_name()
    all_stocks = pd.concat([sh_list, sz_list, bj_list], ignore_index=True)
    all_stocks.to_csv(STOCK_LIST_FILE, index=False)
    log(f"股票列表获取完成，总数：{len(all_stocks)}")
    return all_stocks

# ============================
# 获取历史行情
# ============================
def fetch_history(stock):
    code = stock['code']
    try:
        df = ak.stock_zh_a_daily(symbol=code, adjust="qfq")  # 前复权
        df = df[['日期','开盘','收盘','最高','最低','成交量','成交额']]
        df['code'] = code
        df['name'] = stock['name']
        return df
    except Exception as e:
        log(f"[错误] 获取 {code} 历史数据失败: {e}")
        return None

# ============================
# 选股逻辑
# ============================
def select_stocks(df):
    df = df.copy()
    # 剔除未交易和 ST
    df = df[df['收盘'] > 0]
    df = df[~df['name'].str.contains("ST|退")]
    # 计算 RSI / WR
    N1, N2, N3 = 9, 10, 20
    LC = df['收盘'].shift(1)
    df['RSI1'] = df['收盘'].diff().clip(lower=0).rolling(N1).mean() / df['收盘'].diff().abs().rolling(N1).mean() * 100
    df['WR1'] = (df['最高'].rolling(N2).max() - df['收盘']) / (df['最高'].rolling(N2).max() - df['最低'].rolling(N2).min()) * 100
    df['WR2'] = (df['最高'].rolling(N3).max() - df['收盘']) / (df['最高'].rolling(N3).max() - df['最低'].rolling(N3).min()) * 100
    # 市值及天数条件（这里用成交额代替示例）
    df['市值及天数'] = df['成交额'] > 1e7
    # 筛选
    selected = df[(df['RSI1'] > 70) & (df['WR1'] < 20) & (df['WR2'] < 20) & (df['市值及天数'])]
    return selected[['code','name','收盘','日期']]

# ============================
# 主流程
# ============================
def main():
    log("开始运行自动选股程序")
    
    # 获取股票列表
    if not os.path.exists(STOCK_LIST_FILE):
        stock_list = get_stock_list()
    else:
        stock_list = pd.read_csv(STOCK_LIST_FILE)
        log(f"加载本地股票列表，总数：{len(stock_list)}")
    
    # 并行获取历史数据
    all_history = []
    log("开始获取历史行情...")
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = [executor.submit(fetch_history, stock) for idx, stock in stock_list.iterrows()]
        for f in futures:
            df = f.result()
            if df is not None:
                all_history.append(df)
    if not all_history:
        log("未获取到任何历史数据，程序退出")
        return
    
    history_df = pd.concat(all_history, ignore_index=True)
    
    # 获取最近 NUM_DAYS_BACK 个交易日
    history_df['日期'] = pd.to_datetime(history_df['日期'])
    last_dates = sorted(history_df['日期'].unique())
    trading_days = [d for d in last_dates if is_trading_day(d)]
    if len(trading_days) > NUM_DAYS_BACK:
        trading_days = trading_days[-NUM_DAYS_BACK:]
    
    log(f"处理最近 {len(trading_days)} 个交易日的数据")
    
    # 每日选股数量
    count_history = []
    for day in trading_days:
        day_df = history_df[history_df['日期']==day]
        selected = select_stocks(day_df)
        count_history.append({'日期': day, '数量': len(selected)})
        log(f"{day.date()} 选股数量: {len(selected)}")
        if day == trading_days[-1]:
            selected.to_csv(SELECTED_FILE, index=False)
    
    # 绘制折线图
    history_count_df = pd.DataFrame(count_history)
    history_count_df.to_csv(HISTORY_FILE, index=False)
    plt.figure(figsize=(10,5))
    plt.plot(history_count_df['日期'], history_count_df['数量'], marker='o')
    plt.title('每日选股数量折线图')
    plt.xlabel('日期')
    plt.ylabel('选股数量')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(os.path.join(DATA_DIR,'selected_stock_count.png'))
    log("折线图已保存")
    
    log("自动选股程序运行完成")

if __name__ == "__main__":
    main()
