# auto_select_stock.py
import os
import sys
import zipfile
import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

plt.rcParams['font.sans-serif'] = ['SimHei']  # 中文字体
plt.rcParams['axes.unicode_minus'] = False

TDX_DATA_DIR = "tdx_data"

def log(msg):
    print(f"[{datetime.now()}] {msg}")

def fetch_tdx_links():
    """从官网抓取最新 TDX 数据下载链接"""
    url = "https://www.tdx.com.cn/article/vipdata.html"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        links = []
        for a in soup.find_all("a"):
            href = a.get("href")
            if href and href.endswith("day.zip"):
                links.append(href)
        return links
    except Exception as e:
        log(f"[错误] 获取 TDX 下载链接失败: {e}")
        return []

def download_and_extract(url, save_dir=TDX_DATA_DIR):
    os.makedirs(save_dir, exist_ok=True)
    filename = os.path.join(save_dir, url.split("/")[-1])
    try:
        log(f"正在下载: {url}")
        r = requests.get(url, stream=True, timeout=60)
        r.raise_for_status()
        with open(filename, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024*1024):
                f.write(chunk)
        log(f"下载完成 → {filename}")

        # 解压
        with zipfile.ZipFile(filename, "r") as zip_ref:
            zip_ref.extractall(save_dir)
        log(f"解压完成 → {save_dir}")
        return True
    except Exception as e:
        log(f"[错误] 下载或解压失败: {e}")
        return False

def parse_day_files(data_dir=TDX_DATA_DIR):
    """遍历 .day 文件，构建股票数据 DataFrame"""
    day_files = []
    for root, _, files in os.walk(data_dir):
        for file in files:
            if file.endswith(".day"):
                day_files.append(os.path.join(root, file))
    if not day_files:
        log("[错误] 没有找到任何 .day 文件，直接退出")
        sys.exit(1)
    
    stock_list = []
    for f in day_files:
        code = os.path.basename(f).split(".")[0]
        # 简单模拟读取：这里可以换成 pytdx/自定义解析
        stock_list.append({"代码": code, "文件": f})
    return pd.DataFrame(stock_list)

def is_valid_stock(code):
    """剔除 ST 股或其他规则，可以扩展"""
    if code.startswith("ST") or code.startswith("*"):
        return False
    return True

def download_stock_history(stock_row):
    """模拟下载股票历史行情"""
    # 这里可改为 pytdx 或本地解析 day 文件
    code = stock_row["代码"]
    try:
        # 读取 day 文件内容
        # 返回 DataFrame 包含 日期、开、高、低、收
        return pd.DataFrame({
            "日期": pd.date_range(end=datetime.today(), periods=21),
            "收盘": np.random.rand(21)*100
        })
    except Exception as e:
        log(f"[错误] 下载历史行情失败: {code}, {e}")
        return None

def main():
    log("开始运行自动选股程序")

    # 下载最新 TDX 数据
    links = fetch_tdx_links()
    if not links:
        log("[错误] 没有获取到任何下载链接，退出")
        sys.exit(1)
    for link in links:
        download_and_extract(link)

    # 解析 .day 文件
    df_stocks = parse_day_files()
    df_stocks = df_stocks[df_stocks["代码"].apply(is_valid_stock)]
    log(f"共发现股票: {len(df_stocks)}")
    if df_stocks.empty:
        log("[错误] 股票列表为空，程序退出")
        sys.exit(1)

    # 多线程下载历史行情
    history_list = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(download_stock_history, row) for _, row in df_stocks.iterrows()]
        for f in tqdm(futures):
            df = f.result()
            if df is not None:
                history_list.append(df)

    if not history_list:
        log("[错误] 没有成功下载任何历史行情")
        sys.exit(1)

    # 合并行情，示例: 取收盘价最后一天 > 50 选股
    selected = []
    for i, df in enumerate(history_list):
        last_close = df["收盘"].iloc[-1]
        if last_close > 50:  # 这里替换你的选股策略
            selected.append(df_stocks.iloc[i]["代码"])

    # 保存结果 CSV
    result_csv = "selected_stocks.csv"
    pd.DataFrame({"股票代码": selected}).to_csv(result_csv, index=False)
    log(f"选股完成，总数: {len(selected)}, 保存文件: {result_csv}")

    # 绘制选股数量折线图
    if history_list:
        daily_counts = [len(selected)]*len(history_list[0])  # 模拟每日数量
        dates = history_list[0]["日期"]
        plt.figure(figsize=(10,6))
        plt.plot(dates, daily_counts, marker="o")
        plt.title("每日选股数量")
        plt.xlabel("日期")
        plt.ylabel("数量")
        plt.grid(True)
        plt.tight_layout()
        img_file = "selected_stock_count.png"
        plt.savefig(img_file)
        log(f"折线图完成，保存文件: {img_file}")

if __name__ == "__main__":
    main()
