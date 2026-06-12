"""
情感分析模块
===========
对清洗后的评论数据进行情感倾向分析，自动识别中英文文本，
分别使用SnowNLP（中文）和TextBlob（英文）进行情感评分，
将每条评论分类为正面(Positive)、中性(Neutral)或负面(Negative)。

分析流程：
1. 加载清洗后的评论数据
2. 检测每条评论的语言
3. 根据语言选择对应的情感分析器
4. 计算情感分数并映射到情感标签
5. 统计整体和分平台的情感分布
6. 输出分析结果
"""

import os
import re
import pandas as pd


def detect_language(text):
    """
    检测文本语言，优先使用langdetect库，回退到字符集判断。

    参数:
        text: str, 输入文本

    返回:
        str, 'zh' 表示中文, 'en' 表示英文
    """
    if not text or not isinstance(text, str) or len(text.strip()) == 0:
        return 'zh'

    text = text.strip()

    # 统计中文字符和英文字符数量
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    english_chars = len(re.findall(r'[a-zA-Z]', text))

    # 中文字符明显占优时直接判定为中文
    if chinese_chars > english_chars * 2 and chinese_chars > 2:
        return 'zh'

    try:
        from langdetect import detect
        lang = detect(text)
        if lang.startswith('zh'):
            return 'zh'
        else:
            return 'en'
    except ImportError:
        if chinese_chars > english_chars:
            return 'zh'
        else:
            return 'en'
    except Exception:
        if chinese_chars > english_chars:
            return 'zh'
        else:
            return 'en'


def analyze_chinese(text):
    """
    使用SnowNLP对中文文本进行情感分析。

    SnowNLP情感分析原理：
    - 基于朴素贝叶斯分类器，输出0~1之间的情感分数
    - 越接近1表示越正面，越接近0表示越负面
    - 默认模型基于电商评论训练，对通用文本也有一定效果

    参数:
        text: str, 中文文本

    返回:
        tuple, (情感标签, 情感分数)
        标签: 'positive', 'neutral', 'negative'
        分数: 0~1之间的浮点数
    """
    try:
        from snownlp import SnowNLP
        s = SnowNLP(text)
        score = s.sentiments  # 返回0~1之间的情感分数
    except ImportError:
        print("[错误] SnowNLP未安装，请执行: pip install snownlp")
        return ('neutral', 0.5)
    except Exception as e:
        print(f"[警告] SnowNLP分析失败: {e}")
        return ('neutral', 0.5)

    # 映射分数到情感标签
    # score >= 0.6: 正面情感（文本中积极词汇较多）
    # 0.4 <= score < 0.6: 中性情感（正负词汇相对平衡）
    # score < 0.4: 负面情感（文本中消极词汇较多）
    label = classify_polarity(score, 'zh')
    return (label, score)


def analyze_english(text):
    """
    使用TextBlob对英文文本进行情感分析。

    TextBlob情感分析原理：
    - 基于NLTK的情感词典和模式匹配
    - 返回polarity（极性）和subjectivity（主观性）两个指标
    - polarity范围[-1, 1]，-1最负面，+1最正面，0中性

    参数:
        text: str, 英文文本

    返回:
        tuple, (情感标签, 情感分数)
        标签: 'positive', 'neutral', 'negative'
        分数: -1~1之间的浮点数（polarity）
    """
    try:
        from textblob import TextBlob
        blob = TextBlob(text)
        score = blob.sentiment.polarity  # 返回-1~1之间的情感极性
    except ImportError:
        print("[错误] TextBlob未安装，请执行: pip install textblob")
        return ('neutral', 0.0)
    except Exception as e:
        print(f"[警告] TextBlob分析失败: {e}")
        return ('neutral', 0.0)

    # 映射polarity到情感标签
    # polarity > 0.1: 正面情感
    # -0.1 <= polarity <= 0.1: 中性情感
    # polarity < -0.1: 负面情感
    label = classify_polarity(score, 'en')
    return (label, score)


def classify_polarity(score, lang):
    """
    统一的情感极性分类函数，将分数映射到情感标签。

    参数:
        score: float, 情感分数
        lang: str, 语言代码 'zh' 或 'en'

    返回:
        str, 情感标签: 'positive', 'neutral', 'negative'
    """
    if lang == 'zh':
        # SnowNLP分数范围[0, 1]
        if score >= 0.6:
            return 'positive'
        elif score >= 0.4:
            return 'neutral'
        else:
            return 'negative'
    else:
        # TextBlob polarity范围[-1, 1]
        if score > 0.1:
            return 'positive'
        elif score >= -0.1:
            return 'neutral'
        else:
            return 'negative'


def analyze_sentiment(df):
    """
    对DataFrame中的所有评论进行批量情感分析。

    处理流程：
    1. 遍历每行数据
    2. 检测语言并选择对应的分析器
    3. 计算情感分数和标签
    4. 将结果添加到DataFrame

    参数:
        df: pd.DataFrame, 包含'content'列的评论数据

    返回:
        pd.DataFrame, 添加了'sentiment_label'和'sentiment_score'列的数据框
    """
    labels = []
    scores = []

    total = len(df)
    for idx, row in df.iterrows():
        content = row.get('content', '')

        if not isinstance(content, str) or not content.strip():
            labels.append('neutral')
            scores.append(0.5)
            continue

        # 检测语言
        lang = detect_language(content)

        # 根据语言选择分析器
        if lang == 'zh':
            label, score = analyze_chinese(content)
        else:
            label, score = analyze_english(content)

        labels.append(label)
        scores.append(score)

        # 每处理100条打印一次进度
        if (idx + 1) % 100 == 0 or (idx + 1) == total:
            print(f"  情感分析进度: {idx + 1}/{total}")

    # 将结果添加到DataFrame
    df['sentiment_label'] = labels
    df['sentiment_score'] = scores

    # 统计各情感标签数量
    label_counts = df['sentiment_label'].value_counts()
    print(f"\n[情感分析] 分析完成! 共 {total} 条数据")
    for label in ['positive', 'neutral', 'negative']:
        count = label_counts.get(label, 0)
        pct = count / total * 100 if total > 0 else 0
        print(f"  {label}: {count} 条 ({pct:.1f}%)")

    return df


def summary_stats(df):
    """
    生成情感分析的汇总统计信息。

    统计维度：
    - 整体情感分布（数量和百分比）
    - 各平台（如微博、知乎、YouTube等）的情感分布

    参数:
        df: pd.DataFrame, 包含'sentiment_label'和'platform'列的已分析数据

    返回:
        dict, 包含整体统计和分平台统计的字典
    """
    stats = {}

    # 整体情感分布统计
    total = len(df)
    label_counts = df['sentiment_label'].value_counts().to_dict()

    stats['total'] = total
    stats['distribution'] = {}
    for label in ['positive', 'neutral', 'negative']:
        count = label_counts.get(label, 0)
        pct = round(count / total * 100, 1) if total > 0 else 0
        stats['distribution'][label] = {'count': count, 'percentage': pct}

    # 各平台情感分布统计
    if 'platform' in df.columns:
        stats['by_platform'] = {}
        platforms = df['platform'].unique()
        for platform in platforms:
            platform_df = df[df['platform'] == platform]
            platform_total = len(platform_df)
            platform_label_counts = platform_df['sentiment_label'].value_counts().to_dict()

            platform_stats = {'total': platform_total, 'distribution': {}}
            for label in ['positive', 'neutral', 'negative']:
                count = platform_label_counts.get(label, 0)
                pct = round(count / platform_total * 100, 1) if platform_total > 0 else 0
                platform_stats['distribution'][label] = {'count': count, 'percentage': pct}

            stats['by_platform'][platform] = platform_stats

    return stats


def print_summary(stats):
    """
    格式化打印情感分析汇总统计。

    参数:
        stats: dict, summary_stats()返回的统计字典
    """
    print("\n" + "=" * 60)
    print("📊 情感分析汇总统计")
    print("=" * 60)

    print(f"\n总数据量: {stats['total']} 条")

    print("\n【整体情感分布】")
    for label, data in stats['distribution'].items():
        label_cn = {'positive': '正面', 'neutral': '中性', 'negative': '负面'}.get(label, label)
        print(f"  {label_cn}({label}): {data['count']} 条 ({data['percentage']}%)")

    if 'by_platform' in stats:
        print("\n【各平台情感分布】")
        for platform, pstats in stats['by_platform'].items():
            print(f"\n  平台: {platform} (共 {pstats['total']} 条)")
            for label, data in pstats['distribution'].items():
                label_cn = {'positive': '正面', 'neutral': '中性', 'negative': '负面'}.get(label, label)
                print(f"    {label_cn}: {data['count']} 条 ({data['percentage']}%)")

    print("=" * 60)


def main():
    """
    情感分析模块入口函数。

    从 data/processed/clean_data.csv 读取清洗后的数据，
    执行情感分析，将结果保存到 data/processed/sentiment_results.csv，
    并打印情感分布汇总统计。

    如果 clean_data.csv 不存在，回退到使用示例数据。
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    input_path = os.path.join(base_dir, "data", "processed", "clean_data.csv")
    output_path = os.path.join(base_dir, "data", "processed", "sentiment_results.csv")
    output_dir = os.path.join(base_dir, "data", "processed")

    # 检查输入文件是否存在
    if not os.path.exists(input_path):
        print(f"[警告] 输入文件不存在: {input_path}")
        print("[提示] 请先运行 clean_data.py 生成清洗后的数据")
        # 回退到示例数据
        sample_path = os.path.join(base_dir, "data", "sample", "sample_comments.csv")
        if os.path.exists(sample_path):
            print(f"[回退] 将使用示例数据: {sample_path}")
            input_path = sample_path
        else:
            return

    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    try:
        print(f"[读取] 正在读取数据: {input_path}")
        df = pd.read_csv(input_path, encoding='utf-8')
        print(f"[读取] 共 {len(df)} 条数据\n")

        # 执行情感分析
        df = analyze_sentiment(df)

        # 保存结果
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"\n[保存] 情感分析结果已保存至: {output_path}")

        # 打印汇总统计
        stats = summary_stats(df)
        print_summary(stats)

    except Exception as e:
        print(f"[错误] 情感分析过程中发生异常: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
