#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import pandas as pd
from datetime import datetime
from tqdm import tqdm
import matplotlib.pyplot as plt
from concurrent.futures import ThreadPoolExecutor

# ===============================
# 配置区
# ===============================
TDX_DIR = "./tdx_data"  # 本地 TDX vipdoc 目录
OUTPUT_DIR = "./output"
HISTORY_FILE = os.path.join(OUTPUT_DIR, "selected_stock_count.csv")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ===============================
# 读取所有 .day 文件
# ===============================
def get_all_day_files(tdx_dir):
    day_files = []
    for root, dirs, files in os.walk(tdx_dir):
        for f in files:
            if f.endswith(".day"):
                day_files.append(os.path.join(root, f))
    return day_files

# ===============================
# 解析 .day 文件（示例解析，实际可用 pytdx）
# ===============================
def parse_day_file(file_path):
    # 这里可以用 pytdx 或者自定义解析逻辑
    # 返回字典 { '代码': code, '日期': date, '开盘': open, '收盘': close, ... }
    # 示例只返回代码
    code = os.path.basename(file_path).split(".")[0]
    return {"代码": code}

# ===============================
# 下载/读取历史行情（本地 TDX 已有，无需下载）
# ===============================
def load_stock_data():
    day_files = get_all_day_files(TDX_DIR)
    data = []
    for f in tqdm(day_files, desc="读取TDX .day 文件"):
        try:
            row = parse_day_file(f)
            data.append(row)
        except Exception as e:
            print(f"[错误] 解析 {f} 失败: {e}")
    df = pd.DataFrame(data)
    return df

# ===============================
# 简单选股逻辑示例
# ===============================
def select_stocks(df):
    # 这里可以替换为你的选股逻辑
    return df.head(50)  # 示例选前50只

# ===============================
# 绘制选股数量历史
# ===============================
def plot_count_history(df_selected):
    today = datetime.today().strftime("%Y-%m-%d")
    if os.path.exists(HISTORY_FILE):
        df_history = pd.read_csv(HISTORY_FILE)
    else:
        df_history = pd.DataFrame(columns=["日期", "数量"])

    df_history = pd.concat([df_history, pd.DataFrame([{"日期": today, "数量": len(df_selected)}])], ignore_index=True)
    df_history.to_csv(HISTORY_FILE, index=False)

    plt.figure(figsize=(8,4))
    plt.plot(pd.to_datetime(df_history["日期"]), df_history["数量"], marker='o')
    plt.title("选股数量历史")
    plt.xlabel("日期")
    plt.ylabel("数量")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "selected_stock_count.png"))
    plt.close()

# ===============================
# 主函数
# ===============================
def main():
    print("[INFO] 开始运行自动选股程序")
    df_stocks = load_stock_data()
    if df_stocks.empty:
        print("[错误] 股票列表为空，程序退出")
        return

    print(f"[INFO] 股票列表获取完成，总数: {len(df_stocks)}")
    df_selected = select_stocks(df_stocks)
    print(f"[INFO] 选股完成，总数: {len(df_selected)}")

    plot_count_history(df_selected)
    df_selected.to_csv(os.path.join(OUTPUT_DIR, "selected_stocks.csv"), index=False)
    print("[INFO] 文件保存完成")

if __name__ == "__main__":
    main()
