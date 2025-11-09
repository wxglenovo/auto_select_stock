# -*- coding: utf-8 -*-
import os
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import akshare as ak
import warnings
warnings.filterwarnings("ignore")

plt.rcParams['font.sans-serif'] = ['SimHei']  # 中文字体
plt.rcParams['axes.unicode_minus'] = False

# --------------------
# 配置参数
# --------------------
N1 = 9
N2 = 10
N3 = 20
MIN_LISTED_DAYS = 30
MIN_MARKET_CAP = 1e9  # 10亿

HISTORY_DIR = "history_data"
os.makedirs(HISTORY_DIR, exist_ok=True)

# --------------------
# 获取股票列表（沪深 + 北交所）
# --------------------
def get_stock_list():
    print(f"[{datetime.now()}] 开始获取股票列表（沪深 + 北交所）")
    # 上证A股
    try:
        sh_list = ak.stock_info_a_code_name()
        sh_list['市场'] = 'SH'
    except Exception as e:
        print(f"[错误] 获取上证A股失败: {e}")
        sh_list = pd.DataFrame(columns=['代码','名称','市场'])
    # 深圳A股
    try:
        sz_list = ak.stock_info_sz_name_code()
        sz_list['市场'] = 'SZ'
    except Exception as e:
        print(f"[错误] 获取深证A股失败: {e}")
        sz_list = pd.DataFrame(columns=['代码','名称','市场'])
    # 北交所
    try:
        bj_list = ak.stock_info_bj_stock_name()
        bj_list['市场'] = 'BJ'
    except Exception as e:
        print(f"[错误] 获取北交所失败: {e}")
        bj_list = pd.DataFrame(columns=['代码','名称','市场'])
    # 合并
    df = pd.concat([sh_list, sz_list, bj_list], ignore_index=True)
    df.drop_duplicates(subset=['代码'], inplace=True)
    print(f"[{datetime.now()}] 股票列表获取完成，总数: {len(df)}")
    return df

# --------------------
# 下载历史行情
# --------------------
def download_history(stock_code, market):
    file_path = os.path.join(HISTORY_DIR, f"{stock_code}.csv")
    for attempt in range(3):
        try:
            if market in ['SH','SZ']:
                df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
            else:
                df = ak.stock_bj_hist(symbol=stock_code)
            if df.empty:
                raise ValueError("数据为空")
            df.to_csv(file_path, index=False)
            return True
        except Exception as e:
            print(f"[错误] 获取 {stock_code} 历史数据失败: {e} (尝试 {attempt+1}/3)")
    return False

def download_all_history(df_stocks):
    print(f"[{datetime.now()}] 开始下载历史行情...")
    failed = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_code = {executor.submit(download_history, row['代码'], row['市场']): row['代码'] for idx, row in df_stocks.iterrows()}
        for future in as_completed(future_to_code):
            code = future_to_code[future]
            success = future.result()
            if not success:
                failed.append(code)
    if failed:
        print(f"[{datetime.now()}] 重试 {len(failed)} 个下载失败的股票...")
        for code in failed:
            row = df_stocks[df_stocks['代码'] == code].iloc[0]
            download_history(row['代码'], row['市场'])

# --------------------
# 选股逻辑
# --------------------
def select_stocks(df_prices):
    df = df_prices.copy()
    df['LC'] = df['close'].shift(1)
    df['RSI1'] = df['LC'].combine(df['close'], lambda lc, c: max(c-lc,0)) \
                 .rolling(N1).mean() / df['LC'].combine(df['close'], lambda lc, c: abs(c-lc)).rolling(N1).mean() * 100
    df['WR1'] = (df['high'].rolling(N2).max() - df['close']) / (df['high'].rolling(N2).max() - df['low'].rolling(N2).min()) * 100
    df['WR2'] = (df['high'].rolling(N3).max() - df['close']) / (df['high'].rolling(N3).max() - df['low'].rolling(N3).min()) * 100
    selected = df[(df['RSI1'] > 70) & (df['WR1'] < 20) & (df['WR2'] < 20)]
    return selected

# --------------------
# 绘制选股数量折线图
# --------------------
def plot_count_history(df_selected):
    history_file = "selected_stock_count.csv"
    if os.path.exists(history_file):
        df_history = pd.read_csv(history_file, parse_dates=['日期'])
    else:
        df_history = pd.DataFrame(columns=['日期','数量'])
    today = pd.Timestamp(datetime.now().date())
    df_history = pd.concat([df_history, pd.DataFrame([{"日期": today, "数量": len(df_selected)}])], ignore_index=True)
    df_history.to_csv(history_file, index=False)

    plt.figure(figsize=(10,6))
    plt.plot(df_history['日期'], df_history['数量'], marker='o')
    plt.title("每日选股数量")
    plt.xlabel("日期")
    plt.ylabel("选股数量")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("selected_stock_count.png")
    print(f"[{datetime.now()}] 绘制选股数量折线图完成，保存文件: selected_stock_count.png")

# --------------------
# 主函数
# --------------------
def main():
    print(f"[{datetime.now()}] 开始运行自动选股程序")
    df_stocks = get_stock_list()
    if df_stocks.empty:
        print(f"[{datetime.now()}] 股票列表为空，退出")
        return

    download_all_history(df_stocks)

    # 模拟选股：这里只做示例，只读取最新一条数据
    df_selected = pd.DataFrame(columns=['代码','名称'])
    for idx, row in df_stocks.iterrows():
        try:
            file_path = os.path.join(HISTORY_DIR, f"{row['代码']}.csv")
            if not os.path.exists(file_path):
                continue
            df_price = pd.read_csv(file_path)
            if df_price.empty:
                continue
            # 剔除停牌/ST/未交易
            if 'close' not in df_price.columns or df_price['close'].iloc[-1] == 0:
                continue
            if row['名称'].startswith('ST'):
                continue
            sel = select_stocks(df_price)
            if not sel.empty:
                df_selected = pd.concat([df_selected, pd.DataFrame([row])], ignore_index=True)
        except Exception as e:
            print(f"[错误] 处理 {row['代码']} 出错: {e}")

    df_selected.to_csv("selected_stocks.csv", index=False)
    print(f"[{datetime.now()}] 选股完成，总数: {len(df_selected)}")

    plot_count_history(df_selected)

if __name__ == "__main__":
    main()
