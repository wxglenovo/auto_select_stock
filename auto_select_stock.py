import akshare as ak
import pandas as pd
import datetime

def load_stock_list():
    print("[+] 获取沪深A股列表中...")
    df = ak.stock_info_a_code_name()
    df['code'] = df['code'].astype(str)
    return df

def get_realtime_prices(stock_list):
    print("[+] 获取实时行情中...")
    codes = stock_list['code'].tolist()
    df = ak.stock_zh_a_spot()
    return df[df['代码'].isin(codes)]

def select_stocks(df):
    print("[+] 筛选策略：涨幅 > 3% 且 换手率 > 2% ...")
    selected = df[(df['涨跌幅'] > 3) & (df['换手率'] > 2)]
    return selected[['代码', '名称', '最新价', '涨跌幅', '换手率']]

def main():
    print("===== Auto Select Stock =====")
    stock_list = load_stock_list()
    prices = get_realtime_prices(stock_list)
    result = select_stocks(prices)

    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[+] 运行时间：{now}")

    if result.empty:
        print("[!] 今天没有符合条件的股票")
    else:
        print("[+] 选股结果：")
        print(result)

    # 保存到文件
    result.to_csv("selected_stocks.csv", index=False, encoding="utf-8-sig")
    print("[+] 已保存到 selected_stocks.csv")

if __name__ == "__main__":
    main()
