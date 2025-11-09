#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import zipfile
import pandas as pd
from datetime import datetime, timedelta
from tqdm import tqdm
import matplotlib.pyplot as plt

# ===============================
# 配置区
# ===============================
TDX_ZIP_URL = "https://data.tdx.com.cn/vipdoc/hsjday.zip"
TDX_DIR = "tdx_data"
RESULT_DIR = "results"
os.makedirs(TDX_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

# ===============================
# 下载 TDX ZIP
# ===============================
def download_tdx_zip(url, save_path):
    import requests
    print(f"[INFO] 下载 TDX 数据包: {url}")
    r = requests.get(url, stream=True)
    with open(save_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)
    print(f"[INFO] 下载完成: {save_path}")

# ===============================
# 解压 ZIP
# ===============================
def unzip_tdx(zip_path, extract_dir):
    print(f"[INFO] 解压 {zip_path} 到 {extract_dir}")
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_dir)

# ===============================
# 获取所有 .day 文件
# ===============================
def get_all_day_files(tdx_dir):
    day_files = []
    for root, dirs, files in os.walk(tdx_dir):
        for f in files:
            if f.endswith(".day"):
                day_files.append(os.path.join(root, f))
    return day_files

# ===============================
# 读取 TDX 股票数据
# ===============================
def read_tdx_stock_data(filepath):
    try:
        df = pd.read_csv(filepath, names=["日期","开盘","最高","最低","收盘","成交量","成交额"])
        df["日期"] = pd.to_datetime(df["日期"], format="%Y%m%d")
        df.sort_values("日期", inplace=True)
        df.reset_index(drop=True, inplace=True)
        if df.empty:
            raise ValueError("数据为空")
        return df
    except Exception as e:
        print(f"[错误] 读取 {filepath} 历史数据失败: {e}")
        return None

# ===============================
# 简单选股逻辑: 最近 21 个交易日收盘价上涨
# ===============================
def select_stocks(day_files):
    selected = []
    for f in tqdm(day_files, desc="选股"):
        df = read_tdx_stock_data(f)
        if df is None or len(df) < 21:
            continue
        if df["收盘"].iloc[-1] > df["收盘"].iloc[-21]:
            code = os.path.basename(f).split(".")[0]
            selected.append({"代码": code, "收盘": df["收盘"].iloc[-1]})
    return pd.DataFrame(selected)

# ===============================
# 绘制选股数量折线图
# ===============================
def plot_count_history(df_selected):
    today = datetime.today().strftime("%Y-%m-%d")
    df_history = pd.DataFrame([{"日期": today, "数量": len(df_selected)}])
    plt.figure(figsize=(8,4))
    plt.plot(df_history["日期"], df_history["数量"], marker="o")
    plt.title("选股数量折线图")
    plt.xlabel("日期")
    plt.ylabel("数量")
    plt.tight_layout()
    plt.savefig(os.path.join(RESULT_DIR, "selected_stock_count.png"))
    print(f"[INFO] 绘制完成，保存文件: {os.path.join(RESULT_DIR, 'selected_stock_count.png')}")

# ===============================
# 主函数
# ===============================
def main():
    zip_path = os.path.join(TDX_DIR, "hsjday.zip")
    try:
        download_tdx_zip(TDX_ZIP_URL, zip_path)
        unzip_tdx(zip_path, TDX_DIR)
    except Exception as e:
        print(f"[错误] 下载或解压 TDX 数据失败: {e}")

    day_files = get_all_day_files(TDX_DIR)
    if not day_files:
        print("[错误] 未找到任何 .day 文件，程序退出")
        return

    df_selected = select_stocks(day_files)
    if df_selected.empty:
        print("[INFO] 没有选出符合条件的股票")
    else:
        df_selected.to_csv(os.path.join(RESULT_DIR, "selected_stocks.csv"), index=False)
        print(f"[INFO] 选股完成，总数: {len(df_selected)}")
        plot_count_history(df_selected)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[错误] 脚本执行异常: {e}")
