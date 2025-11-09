#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import akshare as ak
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from tqdm import tqdm
import os

# ===============================
# 配置区
# ===============================
MIN_MARKET_VALUE = 5e8  # 最小市值 5亿
MIN_LIST_DAYS = 60      # 上市天数限制
N1, N2, N3 = 9, 10, 20  # RSI / WR参数
COUNT_HISTORY_FILE = "count_history.csv"
SELECTED_CSV = "selected_stocks.csv"

# ===============================
# 获取股票列表
# ===============================
def get_stock_list():
    print(f"[{datetime.now()}] 开始获取股票列表（沪深 + 北交所）")
    # 沪市
    try:
        sh = ak.stock_em_a_stock_info()
        sh['市场'] = '上证'
    except:
        sh = pd.DataFrame(columns=['代码','名称','市场'])
    # 深市
    try:
        sz = ak.stock_em_a_stock_info(symbol="深证")
        sz['市场'] = '深证'
    except:
        sz = pd.DataFrame(columns=['代码','名称','市场'])
    # 北交所
    try:
        bj = ak.stock_em_bj_stock()
        bj['市场'] = '北交所'
    except:
        bj = pd.DataFrame(columns=['代码','名称','市场'])
    
    df = pd.concat([sh, sz, bj], ignore_index=True)
    if '代码' in df.columns:
        df.drop_duplicates(subset=['代码'], inplace=True)
    print(f"[{datetime.now()}] 股票列表获取完成，总数: {len(df)}")
    return df

# ===============================
# 获取历史行情
# ===============================
def get_stock_history(code):
    try:
        df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
        if df.empty:
            raise ValueError("数据为空")
        df['日期'] = pd.to_datetime(df['日期'])
        df = df[df['收盘'] > 0]  # 剔除未交易
        return df
    except Exception as e:
        print(f"[{datetime.now()}] [错误] 获取 {code} 历史数据失败: {e}")
        return pd.DataFrame()

# ===============================
# 选股逻辑
# ===============================
def select_stocks(df_history):
    if df_history.empty:
        return pd.DataFrame()
    df = df_history.copy()
    df['LC'] = df['收盘'].shift(1)
    df['RSI1'] = df['收盘'].sub(df['LC']).clip(lower=0).rolling(N1).mean() / df['收盘'].sub(df['LC']).abs().rolling(N1).mean() * 100
    df['HHV_N2'] = df['最高'].rolling(N2).max()
    df['LLV_N2'] = df['最低'].rolling(N2).min()
    df['WR1'] = 100*(df['HHV_N2']-df['收盘'])/(df['HHV_N2']-df['LLV_N2'])
    df['HHV_N3'] = df['最高'].rolling(N3).max()
    df['LLV_N3'] = df['最低'].rolling(N3).min()
    df['WR2'] = 100*(df['HHV_N3']-df['收盘'])/(df['HHV_N3']-df['LLV_N3'])
    selected = df[(df['RSI1']>70) & (df['WR1']<20) & (df['WR2']<20)]
    return selected

# ===============================
# 绘制选股数量折线图
# ===============================
def plot_count_history(today, count):
    try:
        df_history = pd.read_csv(COUNT_HISTORY_FILE)
        df_history['日期'] = pd.to_datetime(df_history['日期'], errors='coerce')
    except:
        df_history = pd.DataFrame(columns=['日期','数量'])
    
    df_history = pd.concat([df_history, pd.DataFrame([{"日期": today, "数量": count}])], ignore_index=True)
    
    # 补齐最近21个交易日
    all_dates = pd.bdate_range(end=today, periods=21)
    df_history = df_history.set_index('日期').reindex(all_dates, fill_value=0).reset_index()
    df_history.rename(columns={'index':'日期'}, inplace=True)
    
    plt.figure(figsize=(10,5))
    plt.plot(df_history['日期'], df_history['数量'], marker='o')
    plt.xticks(rotation=45)
    plt.title("最近21个交易日选股数量")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("selected_stock_count.png")
    plt.close()
    
    df_history.to_csv(COUNT_HISTORY_FILE, index=False)
    print(f"[{datetime.now()}] 绘制选股数量折线图完成，保存文件: selected_stock_count.png")

# ===============================
# 主函数
# ===============================
def main():
    print(f"[{datetime.now()}] 开始运行自动选股程序")
    stock_list = get_stock_list()
    selected_all = []
    for idx, row in tqdm(stock_list.iterrows(), total=len(stock_list)):
        code = row['代码']
        df_history = get_stock_history(code)
        if df_history.empty:
            continue
        df_selected = select_stocks(df_history)
        if not df_selected.empty:
            selected_all.append({
                '代码': code,
                '名称': row['名称'],
                '市场': row['市场'],
                '数量信号': len(df_selected)
            })
    df_selected_final = pd.DataFrame(selected_all)
    df_selected_final.to_csv(SELECTED_CSV, index=False)
    print(f"[{datetime.now()}] 选股完成，总数: {len(df_selected_final)}")
    
    plot_count_history(datetime.today().date(), len(df_selected_final))

# ===============================
# 执行
# ===============================
if __name__ == "__main__":
    main()
