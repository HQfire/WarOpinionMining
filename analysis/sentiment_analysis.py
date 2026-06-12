# analysis/sentiment_analysis.py
"""
情感分析模块（SnowNLP + 情感词典修正）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from config import PROCESSED_DIR
from snownlp import SnowNLP


# ---------- 内置情感词库 ----------
# 强烈正面词
POS_WORDS = {
    '支持', '赞', '和平', '正义', '加油', '胜利', '反战', '人道',
    '文明', '守护', '共赢', '光明', '合理', '勇敢', '棒', '伟大',
    '点赞', '好', '对', '优秀', '美好', '共赢', '和平解决',
}
# 强烈负面词
NEG_WORDS = {
    '反对', '谴责', '霸权', '侵略', '屠杀', '无能', '认怂', '愤怒',
    '悲哀', '无耻', '暴行', '邪恶', '双标', '可笑', '荒唐', '谴责',
    '垃圾', '烂', '混蛋', '沙雕', '无语', '崩溃', '绝望', '毁灭',
}


def adjusted_sentiment(text: str) -> float:
    """基于规则修正的情感计算"""
    if pd.isna(text) or len(str(text)) < 5:
        return 0.5
    score = SnowNLP(text).sentiments

    # 词典修正
    for word in POS_WORDS:
        if word in text:
            score = min(1.0, score + 0.2)
            break
    for word in NEG_WORDS:
        if word in text:
            score = max(0.0, score - 0.3)
            break
    # 强否定词减弱正面
    if any(neg in text for neg in ['不', '没', '无', '别']):
        score = score * 0.7

    # 确保边界
    return max(0.0, min(1.0, score))


def classify_sentiment(score: float) -> str:
    if score > 0.7:
        return "正面"
    elif score < 0.3:
        return "负面"
    return "中性"


def sentiment_analysis():
    print("开始情感分析（增强版）...")
    input_path = PROCESSED_DIR / "cleaned_data.csv"
    if not input_path.exists():
        print(f"⚠️ 文件不存在：{input_path}")
        return None

    df = pd.read_csv(input_path, encoding='utf-8-sig')
    print(f"评论总数：{len(df)}")

    df['sentiment_score'] = df['cleaned_text'].apply(adjusted_sentiment)
    df['sentiment'] = df['sentiment_score'].apply(classify_sentiment)

    stats = df['sentiment'].value_counts()
    print("\n情感分布：")
    print(stats)
    print(f"正面占比：{stats.get('正面',0)/len(df):.2%}")
    print(f"负面占比：{stats.get('负面',0)/len(df):.2%}")

    output_path = PROCESSED_DIR / "sentiment_results.csv"
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"结果已保存：{output_path}")
    return df


if __name__ == "__main__":
    sentiment_analysis()
