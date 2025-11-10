import os
import pandas as pd
import matplotlib.pyplot as plt

# 通达信日线数据路径 (dzh 或 tdx)
# TDX 格式: ./tdx_data/vipdoc/sh/lday, ./tdx_data/vipdoc/sz/lday
DATA_PATH = "./tdx_data/vipdoc"

# 遍历全部股票
def load_all_stocks():
    stocks = []
    for market in ["sh", "sz", "bj"]:
        path = f"{DATA_PATH}/{market}/lday"
        if not os.path.exists(path):
            continue
        for file in os.listdir(path):
            if file.endswith(".day"):
                code = file.replace(".day", "")
                stocks.append((market, code))
    return stocks

# 读取通达信 day 格式
def read_tdx_day(file_path):
    if not os.path.isfile(file_path):
        return None
    data = pd.fromfile(file_path, dtype='<i4')
    if data.size % 8 != 0:
        return None

    data = data.reshape((-1, 8))
    df = pd.DataFrame()
    df['date'] = data[:, 0]
    df['open'] = data[:, 1] / 100.0
    df['high'] = data[:, 2] / 100.0
    df['low'] = data[:, 3] / 100.0
    df['close'] = data[:, 4] / 100.0
    df['amount'] = data[:, 5]
    df['vol'] = data[:, 6]
    return df

# 公式计算：RSI、WR
def check_condition(df, idx):
    if idx < 20:
        return False

    close = df['close']
    high = df['high']
    low = df['low']

    # RSI1
    lc = close.shift(1)
    rsi1 = (close - lc).clip(lower=0).rolling(9).mean() / (close - lc).abs().rolling(9).mean() * 100

    # WR1、WR2
    wr1 = (high.rolling(10).max() - close) / (high.rolling(10).max() - low.rolling(10).min() + 0.01) * 100
    wr2 = (high.rolling(20).max() - close) / (high.rolling(20).max() - low.rolling(20).min() + 0.01) * 100

    return (rsi1.iloc[idx] > 70) and (wr1.iloc[idx] < 20) and (wr2.iloc[idx] < 20)

# 汇总每天数量
def main():
    stocks = load_all_stocks()
    print(f"共发现股票: {len(stocks)}")

    daily_count = {}

    for market, code in stocks:
        file_path = f"{DATA_PATH}/{market}/lday/{code}.day"
        df = read_tdx_day(file_path)
        if df is None:
            continue

        for i in range(len(df)):
            date = df['date'].iloc[i]
            if check_condition(df, i):
                daily_count[date] = daily_count.get(date, 0) + 1

    # 转换为可画图格式
    series = pd.Series(daily_count).sort_index()

    print(series.tail())

    # ✅ 折线图（无休市日）
    plt.figure()
    series.plot()
    plt.title("每日符合条件股票数量")
    plt.xlabel("交易日")
    plt.ylabel("入选数量")
    plt.tight_layout()
    plt.savefig("daily_selected_count.png")
    plt.show()

if __name__ == "__main__":
    main()
