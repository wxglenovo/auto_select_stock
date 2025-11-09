import os
import pandas as pd
import akshare as ak
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------------- 文件路径 ----------------
DATA_DIR = "stock_data"
STOCK_LIST_FILE = "all_stock_list.csv"
SELECTED_FILE = "selected_stocks.csv"
HISTORY_COUNT_FILE = "stock_count_history.csv"

# ---------------- 参数 ----------------
N1, N2, N3 = 9, 10, 20
MIN_MARKET_VALUE = 1  # 单位: 亿
LIST_DAYS = 30        # 上市天数筛选
THREADS = 10          # 多线程数

# ---------------- 日志函数 ----------------
def log(msg: str):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

# ---------------- 获取股票列表 ----------------
def get_stock_list():
    log("开始获取股票列表（沪深 + 北交所）")
    all_list = []
    try:
        sh = ak.stock_info_a_code_name()
        all_list.append(sh.rename(columns={"代码":"代码","名称":"名称"}))
        log(f"沪市数量: {len(sh)}")
    except:
        log("[错误] 获取沪市失败")
    try:
        sz = ak.stock_info_sz_name_code()
        sz = sz.rename(columns={"code":"代码","name":"名称"})
        all_list.append(sz)
        log(f"深市数量: {len(sz)}")
    except:
        log("[错误] 获取深市失败")
    try:
        bj = ak.stock_info_bj_stock_name_em()
        bj = bj.rename(columns={"代码":"代码","名称":"名称"})
        all_list.append(bj)
        log(f"北交所数量: {len(bj)}")
    except:
        log("[错误] 获取北交所失败")
    
    if all_list:
        df = pd.concat(all_list, ignore_index=True)
        df.drop_duplicates(subset=["代码"], inplace=True)
        df.to_csv(STOCK_LIST_FILE, index=False, encoding="utf-8-sig")
        log(f"总股票数量: {len(df)}, 已保存到 {STOCK_LIST_FILE}")
        return df
    else:
        return pd.DataFrame(columns=["代码","名称"])

# ---------------- 获取历史数据 ----------------
def get_history(code):
    try:
        df = ak.stock_zh_a_daily(symbol=code, adjust="qfq")  # 前复权
        df = df.reset_index()
        df = df.rename(columns={"date":"日期","open":"开盘","close":"收盘","high":"最高","low":"最低","volume":"成交量"})
        df = df.sort_values("日期")
        df = df[df["收盘"].notna()]  # 剔除未交易
        return df
    except:
        log(f"[错误] 获取 {code} 历史数据失败")
        return None

# ---------------- RSI/WR 选股逻辑 ----------------
def calc_rsi_wr(df):
    LC = df["收盘"].shift(1)
    delta = df["收盘"] - LC
    df["RSI1"] = delta.clip(lower=0).rolling(N1).mean() / delta.abs().rolling(N1).mean() * 100
    df["WR1"] = 100 * (df["最高"].rolling(N2).max() - df["收盘"]) / (df["最高"].rolling(N2).max() - df["最低"].rolling(N2).min())
    df["WR2"] = 100 * (df["最高"].rolling(N3).max() - df["收盘"]) / (df["最高"].rolling(N3).max() - df["最低"].rolling(N3).min())
    return df

# ---------------- 单日选股 ----------------
def select_stock_one_day(code, name):
    df = get_history(code)
    if df is None or len(df) < max(N1,N2,N3)+1:
        return None
    df = calc_rsi_wr(df)
    last = df.iloc[-1]
    if last["RSI1"] > 70 and last["WR1"] < 20 and last["WR2"] < 20:
        return {"代码": code, "名称": name}
    return None

# ---------------- 获取交易日列表 ----------------
def get_trade_days(last_n=21):
    today = datetime.now().date()
    days = []
    d = today
    while len(days) < last_n:
        if d.weekday() < 5:  # 周一~周五
            days.append(d.strftime("%Y-%m-%d"))
        d -= timedelta(days=1)
    days.reverse()
    return days

# ---------------- 主流程 ----------------
def main():
    log("开始运行自动选股程序")
    
    os.makedirs(DATA_DIR, exist_ok=True)
    stock_list = get_stock_list()
    
    trade_days = get_trade_days(21)
    
    history_counts = pd.DataFrame(columns=["日期","数量"])
    if os.path.exists(HISTORY_COUNT_FILE):
        history_counts = pd.read_csv(HISTORY_COUNT_FILE)
    
    for day in trade_days:
        log(f"开始处理交易日: {day}")
        selected = []
        with ThreadPoolExecutor(max_workers=THREADS) as executor:
            futures = {executor.submit(select_stock_one_day, row["代码"], row["名称"]): row for idx,row in stock_list.iterrows()}
            for f in as_completed(futures):
                res = f.result()
                if res:
                    selected.append(res)
        selected_df = pd.DataFrame(selected)
        history_counts = history_counts.append({"日期": day, "数量": len(selected_df)}, ignore_index=True)
    
    # 保存选股数量历史
    history_counts.to_csv(HISTORY_COUNT_FILE, index=False, encoding="utf-8-sig")
    
    # 保存今日选股结果
    today_selected = pd.DataFrame(selected)
    today_selected.to_csv(SELECTED_FILE, index=False, encoding="utf-8-sig")
    log(f"今日选股完成，数量: {len(today_selected)}，已保存到 {SELECTED_FILE}")
    
    # 绘制折线图
    plt.figure(figsize=(10,5))
    plt.plot(pd.to_datetime(history_counts["日期"]), history_counts["数量"], marker='o')
    plt.title("选股数量折线图")
    plt.xlabel("日期")
    plt.ylabel("选股数量")
    plt.grid(True)
    plt.savefig("selected_stock_count.png")
    plt.close()
    log("折线图保存完成: selected_stock_count.png")

if __name__ == "__main__":
    main()
