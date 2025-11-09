import akshare as ak
import pandas as pd
import datetime
import matplotlib.pyplot as plt
import os
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

# -----------------------------
# 配置文件
# -----------------------------
DATA_DIR = "stock_data"
SELECTED_FILE = "selected_stocks.csv"
HISTORY_FILE = "stock_count_history.csv"
MIN_MARKET_CAP = 10  # 亿
LIST_DAYS = 60       # 上市天数下限
MAX_THREADS = 10     # 并行线程数
os.makedirs(DATA_DIR, exist_ok=True)

# -----------------------------
# 选股公式逻辑
# -----------------------------
def calculate_indicators(df):
    N1, N2, N3 = 9, 10, 20
    df['昨日收盘'] = df['close'].shift(1)
    df['涨跌'] = df['close'] - df['昨日收盘']
    df['上涨'] = df['涨跌'].apply(lambda x: max(x, 0))
    df['下跌'] = df['涨跌'].abs()
    df['RSI1'] = df['上涨'].rolling(N1).mean() / df['下跌'].rolling(N1).mean() * 100

    df['最高N2'] = df['high'].rolling(N2).max()
    df['最低N2'] = df['low'].rolling(N2).min()
    df['WR1'] = 100*(df['最高N2']-df['close'])/(df['最高N2']-df['最低N2'])

    df['最高N3'] = df['high'].rolling(N3).max()
    df['最低N3'] = df['low'].rolling(N3).min()
    df['WR2'] = 100*(df['最高N3']-df['close'])/(df['最高N3']-df['最低N3'])
    return df

def check_market_cap_and_listdays(stock_info):
    return (stock_info['上市天数'] >= LIST_DAYS) & (stock_info['市值'] >= MIN_MARKET_CAP*1e8)

def select_stock(df, stock_info):
    df = calculate_indicators(df)
    latest = df.iloc[-1]

    # 剔除未交易（成交量为0）和 ST 股票
    if latest['volume'] == 0:
        return False
    if 'ST' in stock_info['名称'].upper():
        return False

    条件 = (latest['RSI1']>70) & (latest['WR1']<20) & (latest['WR2']<20)
    条件 &= check_market_cap_and_listdays(stock_info)
    return 条件

# -----------------------------
# 获取股票列表和历史行情（前复权）
# -----------------------------
def get_stock_list():
    print("[信息] 正在获取股票列表...")
    stock_list = ak.stock_info_a_code_name()
    stock_list['code'] = stock_list['code'].astype(str)
    print(f"[信息] 共获取到 {len(stock_list)} 只股票")
    return stock_list

def get_stock_history(code, start_date, end_date):
    try:
        df = ak.stock_zh_a_daily(symbol=code, start_date=start_date, end_date=end_date, adjust="qfq")
        df = df.rename(columns={'日期':'date','开盘':'open','收盘':'close','最高':'high','最低':'low','成交量':'volume'})
        df = df.sort_values('date')
        return df[['date','open','high','low','close','volume']]
    except Exception as e:
        print(f"[错误] 获取 {code} 历史数据失败: {e}")
        return pd.DataFrame()

# -----------------------------
# 并行处理单只股票
# -----------------------------
def process_stock(row, start_date, end_date):
    code = row['code']
    df = get_stock_history(code, start_date, end_date)
    if df.empty:
        return []

    stock_info = {
        '名称': row['name'],
        '市值': 1e9,        # 示例市值，可根据需求修改
        '上市天数': 120     # 示例上市天数
    }

    结果 = []
    for date in df['date'].tolist():
        sub_df = df[df['date']<=date]
        try:
            if select_stock(sub_df, stock_info):
                结果.append({'日期': date, '股票代码': code, '名称': row['name']})
        except Exception as e:
            print(f"[警告] {code} 在 {date} 选股异常: {e}")
            continue
    return 结果

# -----------------------------
# 主程序
# -----------------------------
def main():
    today = datetime.date.today()
    stock_list = get_stock_list()
    history_records = []

    start_date = (today - datetime.timedelta(days=40)).strftime('%Y%m%d')
    end_date = today.strftime('%Y%m%d')
    print(f"[信息] 正在处理股票历史行情，日期区间：{start_date} - {end_date}")

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = {executor.submit(process_stock, row, start_date, end_date): row['code'] for idx, row in stock_list.iterrows()}
        for future in tqdm(as_completed(futures), total=len(futures), desc="正在处理股票"):
            result = future.result()
            if result:
                history_records.extend(result)

    if not history_records:
        print("[提示] 没有符合条件的股票")
        return

    history_df = pd.DataFrame(history_records)
    daily_count = history_df.groupby('日期')['股票代码'].count().reset_index()
    daily_count = daily_count.sort_values('日期')
    daily_count.to_csv(HISTORY_FILE, index=False, encoding='utf-8-sig')
    print(f"[信息] 每日选股数量已保存到 {HISTORY_FILE}")

    plt.figure(figsize=(12,6))
    plt.plot(daily_count['日期'], daily_count['股票代码'], marker='o')
    plt.title("每日选股数量折线图")
    plt.xlabel("日期")
    plt.ylabel("选股数量")
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("selected_stock_count.png")
    plt.show()
    print("[信息] 折线图生成完成: selected_stock_count.png")

if __name__ == "__main__":
    print("[信息] 开始自动选股任务...")
    main()
    print("[信息] 自动选股任务完成。")
