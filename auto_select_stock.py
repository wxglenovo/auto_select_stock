# tdx_data_downloader.py
# -*- coding: utf-8 -*-

import os
import requests
from bs4 import BeautifulSoup
from zipfile import ZipFile
import pandas as pd
from io import BytesIO
import logging

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')

# 配置
BASE_DIR = "tdx_data"
ZIP_FILENAME = "hsjday.zip"
EXTRACT_DIR = os.path.join(BASE_DIR, "day_files")

# -----------------------------
# 1. 自动获取最新 ZIP 链接
# -----------------------------
def get_latest_zip_url():
    url = "https://www.tdx.com.cn/article/vipdata.html"
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            if "hsjday.zip" in a['href']:
                href = a['href']
                if href.startswith("http"):
                    return href
                else:
                    # 相对路径拼接主域名
                    return "https://www.tdx.com.cn" + href
    except Exception as e:
        logging.error(f"获取最新 ZIP 链接失败: {e}")
    return None

# -----------------------------
# 2. 下载 ZIP 包
# -----------------------------
def download_zip(zip_url):
    try:
        logging.info(f"开始下载: {zip_url}")
        r = requests.get(zip_url, timeout=60)
        r.raise_for_status()
        os.makedirs(BASE_DIR, exist_ok=True)
        zip_path = os.path.join(BASE_DIR, ZIP_FILENAME)
        with open(zip_path, "wb") as f:
            f.write(r.content)
        logging.info(f"下载完成: {zip_path}")
        return zip_path
    except Exception as e:
        logging.error(f"下载失败: {e}")
        return None

# -----------------------------
# 3. 解压 ZIP 包
# -----------------------------
def unzip_file(zip_path):
    try:
        logging.info(f"开始解压: {zip_path}")
        os.makedirs(EXTRACT_DIR, exist_ok=True)
        with ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(EXTRACT_DIR)
        logging.info(f"解压完成, 文件在: {EXTRACT_DIR}")
        return EXTRACT_DIR
    except Exception as e:
        logging.error(f"解压失败: {e}")
        return None

# -----------------------------
# 4. 解析 DAY 文件为 DataFrame
# -----------------------------
def parse_day_file(day_file):
    """解析通达信 .DAY 文件，返回 DataFrame"""
    try:
        import struct
        # 通达信 .DAY 文件格式: 每32字节 = 1条记录
        # 前4字节日期, 4字节开盘价, 4字节最高价, 4字节最低价, 4字节收盘价, 4字节成交量, 4字节成交金额, 4字节未知
        record_size = 32
        with open(day_file, "rb") as f:
            content = f.read()
        n = len(content) // record_size
        records = []
        for i in range(n):
            record = content[i*record_size:(i+1)*record_size]
            date, open_, high, low, close, vol, amount, _ = struct.unpack('<IIIIIIII', record)
            # 日期转换
            yyyy = date // 10000
            mm = (date % 10000) // 100
            dd = date % 100
            date_str = f"{yyyy:04d}-{mm:02d}-{dd:02d}"
            records.append({
                "日期": date_str,
                "开盘": open_/100,
                "最高": high/100,
                "最低": low/100,
                "收盘": close/100,
                "成交量": vol,
                "成交金额": amount
            })
        df = pd.DataFrame(records)
        return df
    except Exception as e:
        logging.error(f"解析文件 {day_file} 失败: {e}")
        return pd.DataFrame()

# -----------------------------
# 5. 批量解析目录中的所有 DAY 文件
# -----------------------------
def parse_all_day_files(extract_dir):
    all_data = {}
    for filename in os.listdir(extract_dir):
        if filename.upper().endswith(".DAY"):
            code = filename[:6]  # 文件名前6位为股票代码
            day_path = os.path.join(extract_dir, filename)
            df = parse_day_file(day_path)
            if not df.empty:
                all_data[code] = df
    logging.info(f"解析完成，总共股票: {len(all_data)}")
    return all_data

# -----------------------------
# 6. 主函数：一键抓取+下载+解析
# -----------------------------
def fetch_and_parse_tdx():
    zip_url = get_latest_zip_url()
    if not zip_url:
        logging.error("无法获取最新 ZIP 链接")
        return {}
    zip_path = download_zip(zip_url)
    if not zip_path:
        return {}
    extract_dir = unzip_file(zip_path)
    if not extract_dir:
        return {}
    data_dict = parse_all_day_files(extract_dir)
    return data_dict

# -----------------------------
# 测试运行
# -----------------------------
if __name__ == "__main__":
    all_stock_data = fetch_and_parse_tdx()
    # 打印某支股票前5条记录
    for code, df in all_stock_data.items():
        logging.info(f"{code} 前5条记录:\n{df.head()}")
        break
