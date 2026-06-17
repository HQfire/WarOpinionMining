#数据加载与清洗主模块
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from config import RAW_DIR, PROCESSED_DIR
from analysis.utils import (
    load_stopwords,
    add_jieba_userdict,
    advanced_clean_text,
    tokenize,
    standardize_columns,
    detect_language
)
#加载jieba自定义领域词
add_jieba_userdict()

def load_and_clean_data(data_dir: str = None) -> pd.DataFrame:
    """
    从raw/读取所有 CSV，统一清洗并返回
    输出保存至 processed/cleaned_data.csv
    """
    data_path = RAW_DIR if data_dir is None else Path(data_dir)
    print(f"正在加载数据，目录：{data_path}")
    if not data_path.exists():
        print(f"目录 {data_path} 不存在！")
        return None
    csv_files = list(data_path.glob("*.csv"))
    if not csv_files:
        print("没有找到任何CSV文件！")
        return None

    print(f"发现 {len(csv_files)} 个文件：{[f.name for f in csv_files]}")

    stopwords = load_stopwords()
    dfs = []

    for file in csv_files:
        platform = file.stem
        print(f"正在读取 {file.name}")
        try:
            df = pd.read_csv(file, encoding='utf-8-sig')
        except:
            try:
                df = pd.read_csv(file, encoding='gbk')
            except Exception as e:
                print(f"读取 {file.name} 失败：{e}")
                continue

        #统一列名
        df = standardize_columns(df, platform)
        #必须存在content列
        if 'content' not in df.columns or df['content'].dropna().empty:
            print(f"{file.name} 无有效 content 列，跳过")
            continue
        #清洗
        df['cleaned_text'] = df['content'].apply(advanced_clean_text)
        df['language'] = df['cleaned_text'].apply(detect_language)
        df['tokens'] = df.apply(
            lambda row: tokenize(row['cleaned_text'], stopwords, row['language']),
            axis=1
        )

        dfs.append(df)

    if not dfs:
        print("所有文件都无法处理！")
        return None

    #合并
    merged = pd.concat(dfs, ignore_index=True)

    #去重、过滤短文本
    merged = merged.drop_duplicates(subset=['cleaned_text'])
    merged = merged[merged['cleaned_text'].str.len() > 5]

    print(f"\n清洗后有效评论数：{len(merged)}")
    print("各平台分布：")
    print(merged['platform'].value_counts())
    print("语言分布：")
    print(merged['language'].value_counts())

    #保存
    output_path = PROCESSED_DIR / "cleaned_data.csv"
    merged.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"数据已保存至：{output_path}")

    return merged

if __name__ == "__main__":
    df = load_and_clean_data()