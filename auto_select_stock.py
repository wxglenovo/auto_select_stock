# auto_select_stock.py
import os
import pandas as pd
import akshare as ak
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import time

# ------------------- 配置 -------------------
DATA_DIR = r"./stock_data"                 # 历史行情存放目录
STOCK_LIST_FILE = r"./all_stock_list.csv" # 股票列表
SELECTED_FILE = r"./selected_stocks.csv"  # 每日选股结果
COUNT_HISTORY_FILE = r"./stock_count_history.csv"  # 选股数量历史
THREADS = 10  # 并行线程数
MIN_MARKET_VALUE = 1e9  # 最小市值
MIN_LISTED_DAYS = 30    # 最小上市天数

# ------------------- 工具函数 -------------------
def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

ensure_dir(DATA_DIR)

def log(msg):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {msg}")

# ------------------- 获取股票列表 -------------------
def get_stock_list():
    log("开始获取股票列表（沪深 + 北交所）")
    try:
        sh_list = ak.stock_info_a_code_name()
        sz_list = ak.stock_info_sz_name_code()
        # 北交所暂时获取失败时忽略
        try:
            bj_list = ak.stock_info_bj_stock_name()  
        except Exception as e:
            log(f"[错误] 获取北交所失败: {e}")
            bj_list = pd.DataFrame(columns=["代码","名称"])
    except Exception as e:
        log(f"[错误] 获取沪深股票列表失败: {e}")
        return pd.DataFrame(columns=["代码","名称"])
    
    df = pd.concat([sh_list, sz_list, bj_list], ignore_index=True)
    df.drop_duplicates(subset=["代码"], inplace=True)
    df.to_csv(STOCK_LIST_FILE, index=False)
    log(f"股票列表获取完成，总数: {len(df)}")
    return df

# ------------------- 下载历史行情 -------------------
def download_history(stock, retry=1):
    code = stock['代码']
    file_path = os.path.join(DATA_DIR, f"{code}.csv")
    for attempt in range(retry+1):
        try:
            df = ak.stock_zh_a_daily(symbol=code, adjust="qfq")  # 前复权
            if df.empty:
                raise ValueError("数据为空")
            df = df[['日期','开盘','收盘','最高','最低','成交量','成交额']]
            df.to_csv(file_path, index=False)
            return code
        except Exception as e:
            log(f"[错误] 获取 {code} 历史数据失败: {e} (尝试 {attempt+1}/{retry+1})")
            time.sleep(1)
    return code

def update_history(stock_list):
    log("开始下载历史行情...")
    failed_list = []
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        for code in tqdm(executor.map(download_history, stock_list.to_dict('records')),
                         total=len(stock_list)):
            file_path = os.path.join(DATA_DIR, f"{code}.csv")
            if not os.path.exists(file_path):
                failed_list.append(code)
    # 重试失败股票
    if failed_list:
        log(f"重试 {len(failed_list)} 个下载失败的股票...")
        for stock in stock_list[stock_list['代码'].isin(failed_list)].to_dict('records'):
            download_history(stock, retry=2)

# ------------------- 选股逻辑 -------------------
def select_stocks(stock_list):
    log("开始选股...")
    selected = []
    for stock in tqdm(stock_list.to_dict('records')):
        code = stock['代码']
        file_path = os.path.join(DATA_DIR, f"{code}.csv")
        if not os.path.exists(file_path):
            continue
        df = pd.read_csv(file_path)
        if df.empty:
            continue
        # 剔除未交易的和ST品种
        if 'ST' in stock['名称']:
            continue
        if df['收盘'].iloc[-1] == 0:
            continue
        # 计算指标
        N1, N2, N3 = 9, 10, 20
        LC = df['收盘'].shift(1)
        delta = df['收盘'] - LC
        rsi1 = delta.clip(lower=0).rolling(N1).mean() / delta.abs().rolling(N1).mean() * 100
        hhv_N2 = df['最高'].rolling(N2).max()
        llv_N2 = df['最低'].rolling(N2).min()
        wr1 = 100 * (hhv_N2 - df['收盘']) / (hhv_N2 - llv_N2)
        hhv_N3 = df['最高'].rolling(N3).max()
        llv_N3 = df['最低'].rolling(N3).min()
        wr2 = 100 * (hhv_N3 - df['收盘']) / (hhv_N3 - llv_N3)
        # 市值及天数判断（简单用行数代替上市天数）
        if len(df) < MIN_LISTED_DAYS:
            continue
        # 选股条件
        if rsi1.iloc[-1] > 70 and wr1.iloc[-1] < 20 and wr2.iloc[-1] < 20:
            selected.append(stock)
    df_selected = pd.DataFrame(selected)
    df_selected.to_csv(SELECTED_FILE, index=False)
    log(f"选股完成，总数: {len(df_selected)}")
    return df_selected

# ------------------- 绘制折线图 -------------------
def plot_count_history(df_selected):
    log("绘制选股数量折线图...")
    today = datetime.now().strftime("%Y-%m-%d")
    if os.path.exists(COUNT_HISTORY_FILE):
        df_history = pd.read_csv(COUNT_HISTORY_FILE)
    else:
        df_history = pd.DataFrame(columns=["日期","数量"])
    df_history = df_history.append({"日期": today, "数量": len(df_selected)}, ignore_index=True)
    df_history.to_csv(COUNT_HISTORY_FILE, index=False)
    plt.figure(figsize=(10,5))
    plt.plot(pd.to_datetime(df_history['日期']), df_history['数量'], marker='o')
    plt.title("每日选股数量")
    plt.xlabel("日期")
    plt.ylabel("数量")
    plt.grid(True)
    plt.savefig("selected_stock_count.png")
    plt.close()
    log("折线图保存完成: selected_stock_count.png")

# ------------------- 主函数 -------------------
def main():
    log("开始运行自动选股程序")
    if os.path.exists(STOCK_LIST_FILE):
        stock_list = pd.read_csv(STOCK_LIST_FILE)
    else:
        stock_list = get_stock_list()
    update_history(stock_list)
    df_selected = select_stocks(stock_list)
    plot_count_history(df_selected)
    log("程序运行结束")

if __name__ == "__main__":
    main()
