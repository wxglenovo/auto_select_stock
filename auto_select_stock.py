import os
import pandas as pd
import matplotlib.pyplot as plt
import zipfile
import requests

DATA_DIR = "tdx_data"

# 下载函数
def download_tdx_zip(url, filename):
    os.makedirs(DATA_DIR, exist_ok=True)
    zip_path = os.path.join(DATA_DIR, filename)
    if os.path.exists(zip_path):
        print(f"{filename} 已存在，跳过下载")
        return zip_path

    print(f"正在下载: {url}")
    r = requests.get(url, timeout=20)
    if r.status_code != 200:
        print(f"下载失败: {url}")
        return None

    with open(zip_path, "wb") as f:
        f.write(r.content)

    print(f"下载完成 → {zip_path}")
    return zip_path

# 解压 zip
def unzip_file(zip_path):
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(DATA_DIR)
            print(f"完成解压: {zip_path}")
    except:
        print(f"解压失败: {zip_path}")

# 读取 .day 文件
def read_day_file(path):
    try:
        data = pd.fromfile(path, dtype="<i4")
        if data.size % 8 != 0:
            return None
        data = data.reshape((-1, 8))
        df = pd.DataFrame()
        df["date"] = data[:, 0]
        df["open"] = data[:, 1] / 100
        df["high"] = data[:, 2] / 100
        df["low"] = data[:, 3] / 100
        df["close"] = data[:, 4] / 100
        return df
    except:
        return None

def main():
    # ✅ 下载三个市场数据
    files = [
        ("https://data.tdx.com.cn/download/shlday.zip", "shlday.zip"),
        ("https://data.tdx.com.cn/download/szlday.zip", "szlday.zip"),
        ("https://data.tdx.com.cn/download/bjlday.zip", "bjlday.zip"),
    ]

    for url, name in files:
        zip_path = download_tdx_zip(url, name)
        if zip_path:
            unzip_file(zip_path)

    # ✅ 搜索所有 day 文件
    day_files = []
    for root, dirs, files in os.walk(DATA_DIR):
        for f in files:
            if f.endswith(".day"):
                day_files.append(os.path.join(root, f))

    print(f"共发现股票: {len(day_files)}")

    if len(day_files) == 0:
        print("没有找到任何 .day 文件，直接退出")
        return

    daily_count = {}

    for f in day_files:
        df = read_day_file(f)
        if df is None or len(df) < 25:
            continue

        close = df["close"]
        high = df["high"]
        low = df["low"]

        rsi1 = (
            (close - close.shift(1)).clip(lower=0).rolling(9).mean()
            / (close - close.shift(1)).abs().rolling(9).mean() * 100
        )

        wr1 = (high.rolling(10).max() - close) / (high.rolling(10).max() - low.rolling(10).min() + 0.01) * 100
        wr2 = (high.rolling(20).max() - close) / (high.rolling(20).max() - low.rolling(20).min() + 0.01) * 100

        df["cond"] = (rsi1 > 70) & (wr1 < 20) & (wr2 < 20)

        for idx, row in df[df["cond"]].iterrows():
            daily_count[row["date"]] = daily_count.get(row["date"], 0) + 1

    # ✅ 没数据也不卡
    if len(daily_count) == 0:
        print("没有任何入选股票，直接退出")
        return

    s = pd.Series(daily_count).sort_index()
    print(s.tail())

    plt.figure()
    s.plot()
    plt.title("每日入选数量")
    plt.xlabel("交易日")
    plt.ylabel("数量")
    plt.savefig("daily_selected_count.png")
    print("✅ 图已生成: daily_selected_count.png")

if __name__ == "__main__":
    main()
