import akshare as ak
import pandas as pd
import datetime
import matplotlib.pyplot as plt
import os

# -----------------------------
# 配置文件
# -----------------------------
DATA_DIR = "stock_data"
SELECTED_FILE = "selected_stocks.csv"
HISTORY_FILE = "stock_count_history.csv"
MIN_MARKET_CAP = 10  # 单位：亿
LIST_DAYS = 60       # 上市天数下限

os.makedirs(DATA_DIR, exist_ok=True)

# -----------------------------
# 选股公式逻辑
# -----------------------------
def calculate_indicators(df):
    # RSI
    N1, N2, N3 = 9, 10, 20
    df['LC'] = df['close'].shift(1)
    df['diff'] = df['close'] - df['LC']
    df['up'] = df['diff'].apply(lambda x: max(x, 0))
    df['down'] = df['diff'].abs()
    df['RSI1'] = df['up'].rolling(N1).mean() / df['down'].rolling(N1).mean() * 100

    # WR指标
    df['HHV_N2'] = df['high'].rolling(N2).max()
    df['LLV_N2'] = df['low'].rolling(N2).min()
    df['WR1'] = 100*(df['HHV_N2']-df['close'])/(df['HHV_N2']-df['LLV_N2'])

    df['HHV_N3'] = df['high'].rolling(N3).max()
    df['LLV_N3'] = df['low'].rolling(N3).min()
    df['WR2'] = 100*(df['HHV_N3']-df['close'])/(df['HHV_N3']-df['LLV_N3'])
    return df

def check_market_cap_and_listdays(stock_info):
    return (stock_info['list_days'] >= LIST_DAYS) & (stock_info['market_cap'] >= MIN_MARKET_CAP*1e8)

def select_stock(df, stock_info):
    df = calculate_indicators(df)
    latest = df.iloc[-1]
    condition = (latest['RSI1']>70) & (latest['WR1']<20) & (latest['WR2']<20)
    condition &= check_market_cap_and_listdays(stock_info)
    return condition

# -----------------------------
# 获取股票列表和历史行情
# -----------------------------
def get_stock_list():
    stock_list = ak.stock_info_a_code_name()
    stock_list['code'] = stock_list['code'].astype(str)
    return stock_list

def get_stock_history(code, start_date, end_date):
    df = ak.stock_zh_a_daily(symbol=code, start_date=start_date, end_date=end_date)
    df = df.rename(columns={'日期':'date','开盘':'open','收盘':'close','最高':'high','最低':'low','成交量':'volume'})
    df = df.sort_values('date')
    return df[['date','open','high','low','close','volume']]

# -----------------------------
# 计算前21个交易日选股数量
# -----------------------------
def main():
    today = datetime.date.today()
    stock_list = get_stock_list()
    history_records = []

    # 首次运行：补前21个交易日
    start_date = (today - datetime.timedelta(days=40)).strftime('%Y%m%d')
    end_date = today.strftime('%Y%m%d')

    for idx, row in stock_list.iterrows():
        code = row['code']
        try:
            df = get_stock_history(code, start_date, end_date)
        except:
            continue

        # 股票信息
        stock_info = {
            'market_cap': 1e9, # 示例：假设100亿市值
            'list_days': 120   # 示例：上市天数
        }

        # 遍历每个交易日
        for date in df['date'].tolist():
            sub_df = df[df['date']<=date]
            try:
                if select_stock(sub_df, stock_info):
                    history_records.append({'date': date, 'code': code})
            except:
                continue

    # 汇总每天选股数量
    history_df = pd.DataFrame(history_records)
    daily_count = history_df.groupby('date')['code'].count().reset_index()
    daily_count = daily_count.sort_values('date')
    daily_count.to_csv(HISTORY_FILE, index=False, encoding='utf-8-sig')

    # -----------------------------
    # 绘制折线图
    # -----------------------------
    plt.figure(figsize=(12,6))
    plt.plot(daily_count['date'], daily_count['code'], marker='o')
    plt.title("每日选股数量")
    plt.xlabel("日期")
    plt.ylabel("选股数量")
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("selected_stock_count.png")
    plt.show()
    print("[✔] 选股数量折线图生成完成: selected_stock_count.png")

if __name__ == "__main__":
    main()
