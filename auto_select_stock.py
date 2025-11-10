#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import glob
import struct
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import logging

# ===============================
# 配置区
# ===============================
TDX_DIR_HS = "tdx_data/hs/lday"  # 沪深日线文件夹
TDX_DIR_BJ = "tdx_data/bj/lday"  # 北交所日线文件夹
OUTPUT_CSV = "selected_stocks.csv"
OUTPUT_IMG = "selected_stock_count.png"
THREADS = 8
RECENT_DAYS = 21

# ===============================
# 日志配置
# ===============================
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# ===============================
# TDX .day 文件解析
# ===============================
def read_day_file(file_path):
    """
    解析通达信 .day 文件
    返回 DataFrame：日期、开盘、最高、最低、收盘、成交量
    """
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        record_size = 32
        num_records = len(data) // record_size
        records = []
        for i in range(num_records):
            offset = i * record_size
            rec = struct.unpack('<IIIIIfII', data[offset:offset + record_size])
            date = rec[0]
            # 转换成 YYYY-MM-DD
            date_str = f"{date//10000:04d}-{(date%10000)//100:02d}-{date%100:02d}"
            records.append({
                'date': date_str,
                'open': rec[1]/100,
                'high': rec[2]/100,
                'low': rec[3]/100,
                'close': rec[4]/100,
                'vol': rec[5]
            })
        df = pd.DataFrame(records)
        df.sort_values('date', inplace=True)
        return df
    except Exception as e:
        logging.error(f"[错误] 解析 {file_path} 失败: {e}")
        return pd.DataFrame()

# ===============================
# 获取所有股票列表
# ===============================
def get_stock_list():
    """
    扫描本地 TDX 目录获取股票代码列表
    """
    stock_files = glob.glob(os.path.join(TDX_DIR_HS, '*.day')) + \
                  glob.glob(os.path.join(TDX_DIR_BJ, '*.day'))
    stock_list = []
    for f in stock_files:
        code = os.path.splitext(os.path.basename(f))[0]
        # 剔除 ST 或无效股票（这里假设 ST 股代码包含 'ST'，自行调整）
        if 'ST' in code.upper():
            continue
        stock_list.append(code)
    logging.info(f"股票列表获取完成，总数: {len(stock_list)}")
    return stock_list

# ===============================
# 多线程解析历史行情
# ===============================
def download_history(stock_list):
    """
    读取本地 TDX 历史行情
    """
    results = {}
    def parse_stock(code):
        if code.startswith('bj'):
            folder = TDX_DIR_BJ
        else:
            folder = TDX_DIR_HS
        file_path = os.path.join(folder, f"{code}.day")
        df = read_day_file(file_path)
        if df.empty:
            logging.warning(f"[警告] {code} 历史行情为空")
        return code, df

    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        future_to_code = {executor.submit(parse_stock, code): code for code in stock_list}
        for future in future_to_code:
            code, df = future.result()
            if not df.empty:
                results[code] = df
    return results

# ===============================
# 选股逻辑（示例）
# ===============================
def select_stocks(histories):
    """
    简单示例：最近收盘价大于开盘价的股票
    """
    selected = []
    for code, df in histories.items():
        if df.empty:
            continue
        last_row = df.iloc[-1]
        if last_row['close'] > last_row['open']:
            selected.append(code)
    return selected

# ===============================
# 绘制选股数量折线图
# ===============================
def plot_selected_count(df_history):
    plt.figure(figsize=(10, 5))
    plt.plot(df_history['date'], df_history['count'], marker='o')
    plt.title("每日选股数量")
    plt.xlabel("日期")
    plt.ylabel("数量")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(OUTPUT_IMG)
    plt.close()
    logging.info(f"绘制选股数量折线图完成，保存文件: {OUTPUT_IMG}")

# ===============================
# 主函数
# ===============================
def main():
    logging.info("开始运行自动选股程序")
    stock_list = get_stock_list()
    if not stock_list:
        logging.error("股票列表为空，程序退出")
        return

    logging.info("开始读取历史行情...")
    histories = download_history(stock_list)

    # 首次补齐最近 RECENT_DAYS 个交易日
    df_history = pd.DataFrame()
    for i in range(RECENT_DAYS):
        date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        # 自动跳过周末和节假日
        df_history = pd.concat([df_history, pd.DataFrame([{'date': date, 'count': 0}])], ignore_index=True)
    
    # 选股
    selected = select_stocks(histories)
    df_selected = pd.DataFrame(selected, columns=['code'])
    df_selected.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
    logging.info(f"选股完成，总数: {len(selected)}，结果保存: {OUTPUT_CSV}")

    # 更新每日选股数量
    today = datetime.now().strftime('%Y-%m-%d')
    df_history.loc[df_history['date'] == today, 'count'] = len(selected)
    plot_selected_count(df_history)

if __name__ == "__main__":
    main()
