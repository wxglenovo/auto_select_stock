# auto_select_stock.py
# -*- coding: utf-8 -*-

import os
import pandas as pd
import matplotlib.pyplot as plt
import akshare as ak
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

# -----------------------
# 配置目录
# -----------------------
DATA_DIR = "stock_data"
STOCK_LIST_FILE = os.path.join(DATA_DIR, "all_stock_list.csv")
SELECTED_FILE = os.path.join(DATA_DIR, "selected_stocks.csv")
HISTORY_FILE = os.path.join(DATA_DIR, "stock_count_history.csv")

# 确保目录存在
os.makedirs(DATA_DIR, exist_ok=True)

# -----------------------
# 获取股票列表（沪深 + 北交所）
# -----------------------
def get_stock_list():
    print(f"[{datetime.now()}] 开始获取股票列表（沪深 + 北交所）")
    sh_sz_list = ak.stock_info_a_code_name()
    bj_list = ak.stock_info_bj_stock_name()
    all_stocks = pd.concat([sh_sz_list, bj_list], ignore_index=True)
    # 剔除ST
    all_stocks = all_stocks[~all_stocks['name'].str.contains('ST|退')]
    all_stocks.to_csv(STOCK_LIST_FILE, index=False, encoding='utf-8-sig')
    print(f"[{datetime.now()}] 股票列表获取完成，总数: {len(all_stocks)}")
    return all_stocks

# -----------------------
# 获取股票历史行情（前复权）
# -----------------------
def get_stock_history(code, start_date):
    try:
        df = ak.stock_zh_a_daily(symbol=code, adjust="qfq")
        df = df[df.index >= start_date]
        df['code'] = code
        return df
    except Exception as e:
        print(f"[错误] 获取 {code} 历史数据失败: {e}")
        return None

# -----------------------
# 计算选股条件
# -----------------------
def rsi_wr_filter(df):
    if df is None or len(df) < 20:
        return False

    df = df.copy()
    df['LC'] = df['close'].shift(1)
    N1, N2, N3 = 9, 10, 20
    df['U'] = (df['close'] - df['LC']).clip(lower=0)
    df['D'] = abs(df['close'] - df['LC'])
    df['RSI1'] = df['U'].rolling(N1).mean() / df['D'].rolling(N1).mean() * 100
    df['HHV_N2'] = df['high'].rolling(N2).max()
    df['LLV_N2'] = df['low'].rolling(N2).min()
    df['WR1'] = 100 * (df['HHV_N2'] - df['close']) / (df['HHV_N2'] - df['LLV_N2'])
    df['HHV_N3'] = df['high'].rolling(N3).max()
    df['LLV_N3'] = df['low'].rolling(N3).min()
    df['WR2'] = 100 * (df['HHV_N3'] - df['close']) / (df['HHV_N3'] - df['LLV_N3'])

    # 当天最后一行
    last = df.iloc[-1]
    if last['RSI1'] > 70 and last['WR1'] < 20 and last['WR2'] < 20:
        return True
    return False

# -----------------------
# 多线程选股
# -----------------------
def select_stocks(stock_list, start_date):
    selected = []
    print(f"[{datetime.now()}] 开始多线程选股，股票总数: {len(stock_list)}")
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(get_stock_history, row['code'], start_date): row for _, row in stock_list.iterrows()}
        for future in futures:
            row = futures[future]
            df = future.result()
            if rsi_wr_filter(df):
                selected.append({'code': row['code'], 'name': row['name']})
    print(f"[{datetime.now()}] 选股完成，符合条件股票数量: {len(selected)}")
    return pd.DataFrame(selected)

# -----------------------
# 绘制折线图
# -----------------------
def plot_history(history_df):
    plt.figure(figsize=(10,6))
    plt.plot(history_df['date'], history_df['count'], marker='o')
    plt.title("每日选股数量折线图")
    plt.xlabel("日期")
    plt.ylabel("选股数量")
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    chart_file = os.path.join(DATA_DIR, "selected_stock_count.png")
    plt.savefig(chart_file)
    print(f"[{datetime.now()}] 折线图已保存: {chart_file}")

# -----------------------
# 主程序
# -----------------------
def main():
    print(f"[{datetime.now()}] 开始运行自动选股程序")
    if os.path.exists(STOCK_LIST_FILE):
        stock_list = pd.read_csv(STOCK_LIST_FILE, dtype=str)
    else:
        stock_list = get_stock_list()

    # 获取最近 21 个交易日
    today = datetime.today()
    start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')  # 预留30天，自动跳过节假日
    selected_df = select_stocks(stock_list, start_date)
    
    # 保存选股结果
    selected_df.to_csv(SELECTED_FILE, index=False, encoding='utf-8-sig')
    print(f"[{datetime.now()}] 选股结果已保存: {SELECTED_FILE}")

    # 更新历史记录
    if os.path.exists(HISTORY_FILE):
        history_df = pd.read_csv(HISTORY_FILE, parse_dates=['date'])
    else:
        history_df = pd.DataFrame(columns=['date', 'count'])
    
    history_df = history_df.append({'date': today.strftime('%Y-%m-%d'), 'count': len(selected_df)}, ignore_index=True)
    history_df.to_csv(HISTORY_FILE, index=False, encoding='utf-8-sig')

    # 绘制折线图
    plot_history(history_df)
    print(f"[{datetime.now()}] 自动选股程序执行完成")

if __name__ == "__main__":
    main()
