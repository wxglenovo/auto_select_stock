# tdx_data_loader.py
# -*- coding: utf-8 -*-

import os
import zipfile
import requests
import pandas as pd
from io import BytesIO
from tqdm import tqdm

# ==============================
# 配置区
# ==============================
TDX_ZIP_URL = "https://data.tdx.com.cn/vipdoc/hsjday.zip"  # 通达信日线数据包
LOCAL_DIR = "tdx_data"  # 本地存储目录
LOG_FILE = "tdx_download.log"

# ==============================
# 日志打印函数
# ==============================
def log(msg):
    print(f"[{pd.Timestamp.now()}] {msg}")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{pd.Timestamp.now()}] {msg}\n")

# ==============================
# 下载 ZIP 文件
# ==============================
def download_zip(url=TDX_ZIP_URL, local_dir=LOCAL_DIR):
    os.makedirs(local_dir, exist_ok=True)
    local_path = os.path.join(local_dir, "hsjday.zip")
    log(f"开始下载通达信日线数据包: {url}")
    
    try:
        resp = requests.get(url, stream=True, timeout=60)
        resp.raise_for_status()
        total_size = int(resp.headers.get('content-length', 0))
        with open(local_path, "wb") as f, tqdm(
            desc="下载中",
            total=total_size,
            unit='B',
            unit_scale=True,
            unit_divisor=1024,
        ) as bar:
            for data in resp.iter_content(chunk_size=1024*1024):
                f.write(data)
                bar.update(len(data))
        log(f"下载完成，保存路径: {local_path}")
        return local_path
    except Exception as e:
        log(f"[错误] 下载失败: {e}")
        return None

# ==============================
# 解压 ZIP 文件
# ==============================
def unzip_file(zip_path, extract_dir=LOCAL_DIR):
    log(f"开始解压 ZIP 文件: {zip_path}")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_dir)
        log(f"解压完成，文件存放目录: {extract_dir}")
        return extract_dir
    except Exception as e:
        log(f"[错误] 解压失败: {e}")
        return None

# ==============================
# 解析单只股票的日线数据
# 通达信格式：32字节/记录，可用 numpy.fromfile 或 struct unpack
# 假设这里使用 struct unpack 解析
# ==============================
import struct

def parse_stock_file(file_path):
    """
    解析单只股票文件，返回 DataFrame
    """
    log(f"开始解析股票文件: {file_path}")
    columns = ["日期", "开盘", "最高", "最低", "收盘", "成交量", "成交额"]
    records = []

    try:
        with open(file_path, "rb") as f:
            while True:
                data = f.read(32)
                if not data:
                    break
                if len(data) < 32:
                    break
                # 通达信日线数据格式：年月日、开高低收、成交量、成交额
                date, open_, high, low, close, vol, amount = struct.unpack('<IIIIIII', data)
                # 转换日期
                year = date % 10000
                month = (date // 10000) % 100
                day = (date // 1000000) % 100
                date_str = f"20{year:02d}-{month:02d}-{day:02d}"
                records.append([date_str, open_/100, high/100, low/100, close/100, vol, amount/100])
        df = pd.DataFrame(records, columns=columns)
        df["日期"] = pd.to_datetime(df["日期"])
        df.sort_values("日期", inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df
    except Exception as e:
        log(f"[错误] 解析失败 {file_path}: {e}")
        return pd.DataFrame(columns=columns)

# ==============================
# 批量解析股票数据
# ==============================
def parse_all_stocks(data_dir=LOCAL_DIR):
    all_files = []
    for root, dirs, files in os.walk(data_dir):
        for file in files:
            if file.endswith(".day"):
                all_files.append(os.path.join(root, file))
    
    log(f"发现 {len(all_files)} 支股票文件，开始解析...")

    all_data = {}
    for file_path in tqdm(all_files, desc="解析中"):
        stock_code = os.path.basename(file_path).replace(".day", "")
        df = parse_stock_file(file_path)
        if not df.empty:
            all_data[stock_code] = df
    log(f"解析完成，成功解析 {len(all_data)} 支股票")
    return all_data

# ==============================
# 主函数
# ==============================
def main():
    zip_path = download_zip()
    if zip_path:
        extract_dir = unzip_file(zip_path)
        if extract_dir:
            stock_data = parse_all_stocks(extract_dir)
            log(f"数据准备完成，可供选股使用")
            # 示例保存为 pickle
            pd.to_pickle(stock_data, os.path.join(extract_dir, "tdx_all_stocks.pkl"))

if __name__ == "__main__":
    main()
