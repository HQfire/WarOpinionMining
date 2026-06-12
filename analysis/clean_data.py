"""
数据清洗模块
===========
对从各平台爬取的原始评论数据进行清洗、去重、格式化和标准化处理。
最终输出干净的结构化CSV数据，供后续分析和建模使用。

处理流程：
1. 加载并合并所有原始CSV文件
2. 去除重复行
3. 清洗文本内容（去除HTML标签、URL、特殊字符等）
4. 处理缺失值
5. 标准化字段格式
6. 保存清洗后的数据
"""

import os
import re
import glob
import pandas as pd


def load_data(file_pattern):
    """
    加载所有匹配file_pattern的CSV文件，合并为一个DataFrame。
    
    参数:
        file_pattern: str, 文件匹配模式，例如 "data/raw/*.csv"
    
    返回:
        pd.DataFrame, 合并后的数据框
    
    异常:
        FileNotFoundError: 当没有找到匹配的文件时抛出
    """
    csv_files = glob.glob(file_pattern)
    if not csv_files:
        raise FileNotFoundError(f"未找到匹配模式 '{file_pattern}' 的CSV文件")

    print(f"[加载数据] 找到 {len(csv_files)} 个CSV文件:")
    df_list = []
    for f in csv_files:
        print(f"  - 正在读取: {f}")
        df_part = pd.read_csv(f, encoding='utf-8')
        df_list.append(df_part)

    df = pd.concat(df_list, ignore_index=True)
    print(f"[加载数据] 合并完成，共 {len(df)} 行数据")
    return df


def clean_text(text):
    """
    清洗单条文本内容，执行以下操作：
    - 去除HTML标签
    - 去除URL链接
    - 去除特殊字符和多余空白字符
    - 规范化Unicode表情符号（保留基本表情）
    
    参数:
        text: str, 原始文本
    
    返回:
        str, 清洗后的文本；若输入非字符串则返回空字符串
    """
    if not isinstance(text, str):
        return ""

    # 1. 去除HTML标签（如 <br>, <div> 等）
    text = re.sub(r'<[^>]+>', '', text)

    # 2. 去除URL链接（http/https/ftp）
    text = re.sub(r'https?://\S+|ftp://\S+', '', text)

    # 3. 去除特殊控制字符（保留常用标点和中英文）
    #    保留：中英文、数字、常用标点、空格
    #    使用字符串拼接避免raw string中的无效转义警告
    keep_pattern = (
        r'[^\u4e00-\u9fff\u3400-\u4dbfa-zA-Z0-9\s'
        r'，。！？、；：""''（）【】《》'
        r',!?;:"\'\(\)\[\]\{\}'
        r'—…\n\r\t'
        r'-]'
    )
    text = re.sub(keep_pattern, '', text)

    # 4. 规范化空白字符：多个空格/换行合并为单个空格
    text = re.sub(r'\s+', ' ', text)

    # 5. 去除首尾空白
    text = text.strip()

    return text


def remove_duplicates(df):
    """
    基于'content'列去除完全重复的行，保留首次出现的记录。
    
    参数:
        df: pd.DataFrame
    
    返回:
        pd.DataFrame, 去重后的数据框
    """
    before = len(df)
    df = df.drop_duplicates(subset=['content'], keep='first')
    after = len(df)
    print(f"[去重] 去除 {before - after} 条重复数据，剩余 {after} 条")
    return df


def handle_missing(df):
    """
    处理缺失值：
    - 删除'content'列为空的行（无法分析的评论）
    - 将'like_count'列的缺失值填充为0
    
    参数:
        df: pd.DataFrame
    
    返回:
        pd.DataFrame, 处理后的数据框
    """
    before = len(df)

    # 删除content为空的记录——没有内容无法进行下游分析
    df = df.dropna(subset=['content'])
    after_content = len(df)
    if before - after_content > 0:
        print(f"[缺失值处理] 删除 {before - after_content} 条内容为空的数据")

    # like_count缺失值填充为0——表示没有点赞数据
    if 'like_count' in df.columns:
        missing_likes = df['like_count'].isna().sum()
        if missing_likes > 0:
            df['like_count'] = df['like_count'].fillna(0).astype(int)
            print(f"[缺失值处理] 填充 {missing_likes} 条like_count缺失值为0")

    print(f"[缺失值处理] 完成后共 {len(df)} 条数据")
    return df


def standardize_format(df):
    """
    标准化数据格式：
    - 将'publish_time'转换为统一的YYYY-MM-DD日期格式
    - 确保'platform'字段为字符串类型
    - 确保'like_count'为整数类型
    
    参数:
        df: pd.DataFrame
    
    返回:
        pd.DataFrame, 标准化后的数据框
    """
    # 标准化publish_time为日期格式
    if 'publish_time' in df.columns:
        df['publish_time'] = pd.to_datetime(df['publish_time'], errors='coerce')
        # 转换为YYYY-MM-DD字符串格式，便于CSV存储和阅读
        df['publish_time'] = df['publish_time'].dt.strftime('%Y-%m-%d')
        invalid_dates = df['publish_time'].isna().sum()
        if invalid_dates > 0:
            print(f"[格式标准化] 警告: {invalid_dates} 条数据的发布时间无法解析，已置为空")

    # 确保platform为字符串类型
    if 'platform' in df.columns:
        df['platform'] = df['platform'].astype(str)

    # 确保like_count为整数类型
    if 'like_count' in df.columns:
        df['like_count'] = pd.to_numeric(df['like_count'], errors='coerce').fillna(0).astype(int)

    print(f"[格式标准化] 字段类型已统一")
    return df


def run_pipeline(input_dir, output_path):
    """
    运行完整的数据清洗流水线。
    
    流程：加载 -> 去重 -> 清洗文本 -> 处理缺失值 -> 格式标准化 -> 保存
    
    参数:
        input_dir: str, 原始数据目录，如 "data/raw"
        output_path: str, 输出文件路径，如 "data/processed/clean_data.csv"
    
    返回:
        pd.DataFrame, 清洗后的数据框
    """
    print("=" * 60)
    print("🚀 开始数据清洗流水线")
    print("=" * 60)

    # 获取input_dir下所有CSV文件
    file_pattern = os.path.join(input_dir, "*.csv")

    # 步骤1: 加载数据
    df = load_data(file_pattern)

    # 步骤2: 去重
    df = remove_duplicates(df)

    # 步骤3: 清洗文本内容
    print("[文本清洗] 正在清洗文本内容...")
    df['content'] = df['content'].apply(clean_text)
    # 清洗后可能产生空字符串，再次删除content为空的行
    df = df[df['content'].str.strip() != '']
    print(f"[文本清洗] 完成，剩余 {len(df)} 条有效数据")

    # 步骤4: 处理缺失值
    df = handle_missing(df)

    # 步骤5: 标准化格式
    df = standardize_format(df)

    # 步骤6: 保存清洗后的数据
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"[保存] 清洗后数据已保存至: {output_path}")

    print("=" * 60)
    print(f"✅ 数据清洗流水线完成! 最终数据: {len(df)} 行 × {len(df.columns)} 列")
    print("=" * 60)
    return df


def main():
    """
    数据清洗模块入口函数。
    
    从 data/raw/ 目录加载原始CSV文件，执行清洗流水线，
    将结果保存到 data/processed/clean_data.csv。
    
    如果 data/raw/ 目录不存在或为空，则回退到使用示例数据 data/sample/。
    """
    # 项目根目录
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # 优先读取 data/raw 目录
    input_dir = os.path.join(base_dir, "data", "raw")
    if not os.path.exists(input_dir) or not glob.glob(os.path.join(input_dir, "*.csv")):
        print("[警告] data/raw/ 目录不存在或为空，将使用 data/sample/ 中的示例数据")
        input_dir = os.path.join(base_dir, "data", "sample")

    output_path = os.path.join(base_dir, "data", "processed", "clean_data.csv")
    output_dir = os.path.join(base_dir, "data", "processed")

    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    try:
        run_pipeline(input_dir, output_path)
    except FileNotFoundError as e:
        print(f"[错误] {e}")
    except Exception as e:
        print(f"[错误] 数据清洗过程中发生异常: {e}")


if __name__ == "__main__":
    main()
