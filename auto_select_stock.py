import os
import pandas as pd
import akshare as ak
import datetime
from tqdm import tqdm
import matplotlib.pyplot as plt
from concurrent.futures import ThreadPoolExecutor

# ------------------- 配置 -------------------
DATA_DIR = "stock_data"
STOCK_LIST_FILE = "all_stock_list.csv"
SELECTED_FILE = "selected_stocks.csv"
HISTORY_FILE = "stock_count_history.csv"
N1, N2, N3 = 9, 10, 20
最小市值 = 1  # 亿
上市天数 = 60
THREADS = 8

os.makedirs(DATA_DIR, exist_ok=True)

# ------------------- 获取股票列表 -------------------
def get_stock_list():
    print("[日志] 开始获取股票列表（沪深 + 北交所）")
    try:
        sh_list = ak.stock_info_a_code_name()
        sh_list.columns = ["代码","名称"]
        print(f"[日志] 沪市数量: {len(sh_list)}")
    except:
        sh_list = pd.DataFrame(columns=["代码","名称"])
        print("[错误] 获取沪市失败")
    try:
        sz_list = ak.stock_info_sz_name_code()
        sz_list.columns = ["代码","名称"]
        print(f"[日志] 深市数量: {len(sz_list)}")
    except:
        sz_list = pd.DataFrame(columns=["代码","名称"])
        print("[错误] 获取深市失败")
    try:
        bj_list = ak.stock_info_bj_stock_name()
        bj_list.columns = ["代码","名称"]
        print(f"[日志] 北交所数量: {len(bj_list)}")
    except:
        bj_list = pd.DataFrame(columns=["代码","名称"])
        print("[警告] 北交所获取失败")
    all_list = pd.concat([sh_list, sz_list, bj_list], ignore_index=True)
    if "代码" in all_list.columns:
        all_list.drop_duplicates(subset=["代码"], inplace=True)
    print(f"[日志] 合并总数量: {len(all_list)}")
    return all_list

# ------------------- 下载历史行情 -------------------
def download_history(stock):
    code = stock['代码']
    file_path = os.path.join(DATA_DIR, f"{code}.csv")
    try:
        df = ak.stock_zh_a_daily(symbol=code, adjust="qfq")
        df = df[['日期','开盘','收盘','最高','最低','成交量','成交额']]
        df.to_csv(file_path, index=False)
    except:
        print(f"[错误] 获取 {code} 历史数据失败")
    return code

# ------------------- 选股逻辑 -------------------
def select_stock(stock):
    code = stock['代码']
    file_path = os.path.join(DATA_DIR, f"{code}.csv")
    if not os.path.exists(file_path):
        return None
    df = pd.read_csv(file_path)
    if len(df) < N3:
        return None
    # 剔除未交易日
    df = df[df['成交量']>0]
    # 简单市值和上市天数过滤（假设市值为成交额*100）
    if len(df) < 上市天数:
        return None
    LC = df['收盘'].shift(1)
    RSI1 = ((df['收盘']-LC).clip(lower=0).rolling(N1).mean() /
            (abs(df['收盘']-LC).rolling(N1).mean())*100).iloc[-1]
    WR1 = 100*(df['最高'].rolling(N2).max().iloc[-1]-df['收盘'].iloc[-1]) / \
           (df['最高'].rolling(N2).max().iloc[-1]-df['最低'].rolling(N2).min().iloc[-1])
    WR2 = 100*(df['最高'].rolling(N3).max().iloc[-1]-df['收盘'].iloc[-1]) / \
           (df['最高'].rolling(N3).max().iloc[-1]-df['最低'].rolling(N3).min().iloc[-1])
    if RSI1>70 and WR1<20 and WR2<20:
        return stock
    return None

# ------------------- 主函数 -------------------
def main():
    print(f"[日志] 开始运行自动选股程序")
    if os.path.exists(STOCK_LIST_FILE):
        stock_list = pd.read_csv(STOCK_LIST_FILE)
        print("[日志] 股票列表已存在，直接使用")
    else:
        stock_list = get_stock_list()
        stock_list.to_csv(STOCK_LIST_FILE, index=False)

    # 下载历史行情
    print("[日志] 下载历史行情...")
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        list(tqdm(executor.map(download_history, stock_list.to_dict('records')),
                  total=len(stock_list)))
    
    # 选股
    print("[日志] 开始选股...")
    selected = []
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        for res in executor.map(select_stock, stock_list.to_dict('records')):
            if res is not None:
                selected.append(res)
    selected_df = pd.DataFrame(selected)
    selected_df.to_csv(SELECTED_FILE, index=False)
    print(f"[日志] 今日选股数量: {len(selected_df)}")

    # 保存选股历史并画折线图
    today = datetime.date.today()
    if os.path.exists(HISTORY_FILE):
        history_df = pd.read_csv(HISTORY_FILE)
    else:
        history_df = pd.DataFrame(columns=["日期","数量"])
    history_df = pd.concat([history_df, pd.DataFrame([{"日期": today,"数量": len(selected_df)}])], ignore_index=True)
    history_df.to_csv(HISTORY_FILE, index=False)
    plt.figure(figsize=(10,5))
    plt.plot(pd.to_datetime(history_df['日期']), history_df['数量'], marker='o')
    plt.title("最近选股数量")
    plt.xlabel("日期")
    plt.ylabel("数量")
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig("selected_stock_count.png")
    print("[日志] 自动选股完成")

if __name__ == "__main__":
    main()
