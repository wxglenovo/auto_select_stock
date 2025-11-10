import os
import re
import requests
import zipfile
import struct
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from io import BytesIO
from bs4 import BeautifulSoup

# ========== ① 抓取下载链接 ==========
def fetch_latest_zip_url():
    print("🔍 正在从通达信官网获取最新数据包下载链接...")
    url = "https://www.tdx.com.cn/article/vipdata.html"
    resp = requests.get(url, timeout=10)
    resp.encoding = resp.apparent_encoding
    soup = BeautifulSoup(resp.text, "html.parser")

    links = soup.find_all("a", href=True)
    for a in links:
        if "day" in a["href"] and a["href"].endswith(".zip"):
            zip_url = a["href"]
            if not zip_url.startswith("http"):
                zip_url = "https://www.tdx.com.cn/" + zip_url.lstrip("/")
            print(f"✅ 找到下载链接：{zip_url}")
            return zip_url

    raise Exception("❌ 未找到日线数据ZIP下载链接，网页可能更新了！")


# ========== ② 下载 ZIP ==========
def download_zip(url, save_path):
    print("⬇️ 正在下载数据文件...")
    resp = requests.get(url, timeout=30)
    with open(save_path, "wb") as f:
        f.write(resp.content)
    print(f"✅ 下载完成：{save_path}")


# ========== ③ 解压 ==========
def unzip_file(zip_path, extract_to):
    print("📦 正在解压文件...")
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_to)
    print(f"✅ 解压完成：{extract_to}")


# ========== ④ 解析 .day 文件 ==========
def parse_day_file(filepath, code):
    results = []
    with open(filepath, "rb") as f:
        while data := f.read(32):
            date, open_p, high, low, close, amount, vol, _ = struct.unpack("IIIIIfII", data)
            date = datetime.strptime(str(date), "%Y%m%d")
            results.append([code, date, open_p/100, high/100, low/100, close/100, vol, amount])
    return results


def load_all_day_files(root_dir):
    print("📑 正在解析所有 .day 文件...")
    all_rows = []
    for root, _, files in os.walk(root_dir):
        for name in files:
            if name.endswith(".day"):
                code = name.replace(".day", "")
                path = os.path.join(root, name)
                rows = parse_day_file(path, code)
                all_rows.extend(rows)

    df = pd.DataFrame(all_rows, columns=["code","date","open","high","low","close","volume","amount"])
    print(f"✅ 解析完成，共 {len(df)} 条K线")
    return df


# ========== ⑤ 选股逻辑 ==========
def calc_indicators(df):
    df = df.sort_values(["code","date"])
    df["pct"] = df.groupby("code")["close"].pct_change()
    df["rsi"] = df.groupby("code")["pct"].apply(lambda x: x.rolling(14).apply(
        lambda s: (s[s>0].sum() / abs(s).sum())*100 if abs(s).sum()!=0 else None
    ))

    high_roll = df.groupby("code")["high"].apply(lambda x: x.rolling(14).max())
    low_roll = df.groupby("code")["low"].apply(lambda x: x.rolling(14).min())
    df["wr"] = (high_roll - df["close"]) / (high_roll - low_roll + 1e-9) * 100

    df["days"] = df.groupby("code").cumcount() + 1
    return df


def pick_stocks(df):
    print("📊 正在执行选股规则：RSI>55, WR<60, 上市≥60天, 流通市值 10~100 亿")
    # 假设 amount (成交额) 可以反推市值（这里只是示范，如你有真实市值接口可替换）
    df["market_cap"] = df["amount"].rolling(10).mean() * 240  # 大致推估

    cond = (
        (df["rsi"] > 55) &
        (df["wr"] < 60) &
        (df["days"] >= 60) &
        (df["market_cap"] >= 1e9) &
        (df["market_cap"] <= 1e10)
    )

    picked = df[cond]
    print(f"✅ 选出 {len(picked)} 条记录")
    return picked


# ========== ⑥ 按日期统计数量 ==========
def count_by_date(picked):
    cnt = picked.groupby("date")["code"].nunique()
    return cnt


# ========== ⑦ 画折线图 ==========
def plot_line(cnt):
    print("📈 正在绘制折线图...")
    plt.figure()
    cnt.plot()
    plt.title("每日选出股票数量")
    plt.xlabel("日期")
    plt.ylabel("数量")
    plt.tight_layout()
    plt.savefig("picked_count.png")
    print("✅ 图已保存：picked_count.png")


# ========== 主程序 ==========

def main():
    os.makedirs("data", exist_ok=True)

    zip_url = fetch_latest_zip_url()
    zip_path = "data/tdx_day.zip"

    download_zip(zip_url, zip_path)
    unzip_file(zip_path, "data/day")

    df = load_all_day_files("data/day")
    df = calc_indicators(df)
    picked = pick_stocks(df)
    cnt = count_by_date(picked)

    plot_line(cnt)
    print("🎉 全部完成！图已生成。")


if __name__ == "__main__":
    main()
