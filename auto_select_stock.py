#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import pandas as pd
import akshare as ak
import datetime
import matplotlib.pyplot as plt

RESULT_CSV = "selected_stocks.csv"
COUNT_PNG = "selected_stock_count.png"
DAYS_NEED = 21  # 最近需要记录 21 个交易日选股数量

def log(msg):
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def is_trade_day(date):
    """判断是否交易日（用上证交易日接口）"""
    try:
        trade_list = ak.tool_trade_date_hist_sina()
        return date.strftime("%Y-%m-%d") in list(trade_list["trade_date"])
    except:
        return True  # 网络失败则按交易日处理避免程序退出

def get_last_trade_day():
    """获取最近一个交易日（周末或节假日自动回退）"""
    today = datetime.date.today()
    while not is_trade_day(today):
        today -= datetime.timedelta(days=1)
    return today

def get_stock_pool():
    """获取沪深A股 + 北交所股票列表（剔除 ST、退市、无效股票）"""
    log("获取沪深股票...")
    try:
        df_sh = ak.stock_info_sh_name()
    except:
        log("[错误] 沪深获取失败，返回空列表")
        df_sh = pd.DataFrame()

    log("获取北交所股票...")
    try:
        df_bj = ak.stock_info_bj_name()
    except:
        log("[错误] 北交所获取失败，返回空列表")
        df_bj = pd.DataFrame()

    if df_sh.empty and df_bj.empty:
        log("[严重] 股票列表获取失败，程序终止")
        return []

    df = pd.concat([df_sh, df_bj], ignore_index=True)

    # 剔除 ST、退市、空名称
    df = df.dropna(subset=["code", "name"])
    df = df[~df["name"].str.contains("ST")]
    df = df[df["name"].str.strip() != ""]

    log(f"股票数量：{len(df)}")
    return df["code"].tolist()

def simple_strategy(code):
    """简单选股策略：最近 10 天上涨多于下跌则入选"""
    try:
        df = ak.stock_zh_a_daily(symbol=code)
        if df is None or len(df) < 10:
            return False
        df = df.tail(10)
        rise_days = (df["close"] > df["open"]).sum()
        return rise_days >= 6
    except:
        log(f"[跳过] 下载失败: {code}")
        return False

def main():
    log("开始运行自动选股程序")

    today = get_last_trade_day()
    log(f"有效交易日：{today}")

    pool = get_stock_pool()
    if not pool:
        log("[错误] 股票池为空，退出")
        return

    selected = []
    for code in pool:
        if simple_strategy(code):
            selected.append(code)

    log(f"今日选出股票数量：{len(selected)}")

    # 存 CSV
    df_result = pd.DataFrame({"date": [today] * len(selected), "code": selected})
    df_result.to_csv(RESULT_CSV, index=False, encoding="utf-8-sig")
    log(f"已保存选股结果 CSV：{RESULT_CSV}")

    # 处理折线图历史
    count_data = []
    if os.path.exists(RESULT_CSV):
        try:
            old = pd.read_csv(RESULT_CSV)
            count_by_day = old.groupby("date")["code"].count().reset_index()
            count_data = count_by_day.values.tolist()
        except:
            count_data = []

    # 保留最近 21 个交易日
    count_data = count_data[-(DAYS_NEED - 1):]
    count_data.append([str(today), len(selected)])

    df_draw = pd.DataFrame(count_data, columns=["date", "count"])
    df_draw.to_csv("selected_stock_count_history.csv", index=False, encoding="utf-8-sig")

    # 生成折线图
    plt.figure()
    plt.plot(df_draw["date"], df_draw["count"])
    plt.xticks(rotation=45)
    plt.title("最近 21 日选股数量")
    plt.tight_layout()
    plt.savefig(COUNT_PNG)
    log(f"已生成折线图：{COUNT_PNG}")

    log("✅ 全部完成！")

if __name__ == "__main__":
    main()
