# auto_select_stock.py
import os
import pandas as pd
import numpy as np
import akshare as ak
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import matplotlib.pyplot as plt

# ---------------- 配置 ----------------
DATA_DIR = "stock_data"                 # 历史行情存放目录
STOCK_LIST_FILE = "all_stock_list.csv" # 股票列表
SELECTED_FILE = "selected_stocks.csv"  # 每日选股结果
HISTORY_FILE = "stock_count_history.csv" # 每日选股数量历史
THREADS = 10                            # 并行线程数
N1, N2, N3 = 9, 10, 20                  # RSI和WR参数
MIN_MARKET_CAP = 5e8                     # 最小市值

os.makedirs(DATA_DIR, exist_ok=True)

# ---------------- 日志 ----------------
def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

# ---------------- 工具 ----------------
def get_stock_list():
    """读取股票列表，若不存在则获取沪深所有A股"""
    if os.path.exists(STOCK_LIST_FILE):
        df = pd.read_csv(STOCK_LIST_FILE, dtype=str)
        return df['code'].tolist()
    else:
        log("股票列表不存在，自动获取沪深A股列表")
        sh_list = ak.stock_info_sh_name_code(symbol="sh")
        sz_list = ak.stock_info_sz_name_code(symbol="sz")
        df = pd.concat([sh_list, sz_list], ignore_index=True)
        df.to_csv(STOCK_LIST_FILE, index=False)
        return df['code'].tolist()

def download_latest_price(code):
    """下载指定股票历史及最新行情"""
    try:
        df_today = ak.stock_zh_a_daily(symbol=code)
        if df_today.empty:
            log(f"[错误] {code} 今日数据为空")
            return None
        if '日期' in df_today.columns:
            df_today.rename(columns={'日期':'date','开盘':'open','收盘':'close','最高':'high','最低':'low','成交量':'volume'}, inplace=True)
        df_today['date'] = pd.to_datetime(df_today['date'])
        df_today = df_today.sort_values('date')
        
        file_path = os.path.join(DATA_DIR, f"{code}.csv")
        if os.path.exists(file_path):
            df_hist = pd.read_csv(file_path)
            df_hist['date'] = pd.to_datetime(df_hist['date'])
            df = pd.concat([df_hist, df_today]).drop_duplicates(subset='date', keep='last')
        else:
            df = df_today
        df.to_csv(file_path, index=False)
        return df
    except Exception as e:
        log(f"[错误] 下载 {code} 历史数据失败: {e}")
        return None

def SMA(series, n):
    return series.rolling(n).mean()

def compute_indicators(df):
    df = df.copy()
    df['LC'] = df['close'].shift(1)
    df['RSI1'] = SMA(np.maximum(df['close']-df['LC'],0), N1) / SMA(np.abs(df['close']-df['LC']), N1) * 100
    df['HHV_N2'] = df['high'].rolling(N2).max()
    df['LLV_N2'] = df['low'].rolling(N2).min()
    df['WR1'] = 100*(df['HHV_N2']-df['close'])/(df['HHV_N2']-df['LLV_N2'])
    df['HHV_N3'] = df['high'].rolling(N3).max()
    df['LLV_N3'] = df['low'].rolling(N3).min()
    df['WR2'] = 100*(df['HHV_N3']-df['close'])/(df['HHV_N3']-df['LLV_N3'])
    return df

def select_stock(code):
    df = download_latest_price(code)
    if df is None or df.empty:
        return None
    df = compute_indicators(df)
    # 剔除未交易日和ST
    if 'ST' in code.upper():
        return None
    latest = df.iloc[-1]
    if latest['close'] == 0:
        return None
    if latest['RSI1'] > 70 and latest['WR1'] < 20 and latest['WR2'] < 20:
        return {'code': code, 'date': latest['date'].strftime('%Y-%m-%d')}
    return None

# ---------------- 主程序 ----------------
def main():
    log("开始运行自动选股程序")
    stock_list = get_stock_list()
    log(f"股票总数: {len(stock_list)}")
    results = []
    
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        future_to_code = {executor.submit(select_stock, code): code for code in stock_list}
        for future in as_completed(future_to_code):
            code = future_to_code[future]
            try:
                res = future.result()
                if res:
                    results.append(res)
                    log(f"[选中] {res['code']} {res['date']}")
            except Exception as e:
                log(f"[错误] {code} 处理失败: {e}")
    
    if results:
        df_sel = pd.DataFrame(results)
        df_sel.to_csv(SELECTED_FILE, index=False)
        log(f"选股结果已保存: {SELECTED_FILE}")
        
        # 生成折线图
        if os.path.exists(HISTORY_FILE):
            df_hist = pd.read_csv(HISTORY_FILE)
        else:
            df_hist = pd.DataFrame(columns=['date','count'])
        today = datetime.today().strftime('%Y-%m-%d')
        df_hist = pd.concat([df_hist, pd.DataFrame([{'date': today, 'count': len(df_sel)}])])
        df_hist.drop_duplicates(subset='date', keep='last', inplace=True)
        df_hist.to_csv(HISTORY_FILE, index=False)
        
        plt.figure(figsize=(10,6))
        plt.plot(pd.to_datetime(df_hist['date']), df_hist['count'], marker='o')
        plt.title("每日选股数量折线图")
        plt.xlabel("日期")
        plt.ylabel("选股数量")
        plt.grid(True)
        plt.tight_layout()
        plt.savefig("selected_stock_count.png")
        log("折线图已生成: selected_stock_count.png")
    else:
        log("今日未选出股票")

if __name__ == "__main__":
    main()
