#情感分析模块
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from config import PROCESSED_DIR
from snownlp import SnowNLP
from textblob import TextBlob
from analysis.utils import detect_language
import re

#内置情感词库
#强烈正面词
POS_WORDS = {
    '支持', '赞', '和平', '正义', '加油', '胜利', '反战', '人道',
    '文明', '守护', '共赢', '光明', '合理', '勇敢', '棒', '伟大',
    '点赞', '好', '对', '优秀', '美好', '共赢', '和平解决',
}
#强烈负面词
NEG_WORDS = {
    '反对', '谴责', '霸权', '侵略', '屠杀', '无能', '认怂', '愤怒',
    '悲哀', '无耻', '暴行', '邪恶', '双标', '可笑', '荒唐', '谴责',
    '垃圾', '烂', '混蛋', '沙雕', '无语', '崩溃', '绝望', '毁灭',
}

#英文正面词，主要用于 YouTube 英文评论
POS_WORDS_EN = {
    "peace", "peaceful", "support", "hope", "safe", "safety",
    "justice", "good", "great", "right", "brave", "victory",
    "protect", "ceasefire", "humanitarian", "freedom",
    "solution", "diplomacy"
}

#英文负面词，战争舆情里这些词经常表示负面情绪
NEG_WORDS_EN = {
    "war", "attack", "attacks", "strike", "strikes", "bomb",
    "bombing", "killed", "kill", "dead", "death", "destroy",
    "destroyed", "terror", "terrorist", "genocide", "massacre",
    "crime", "evil", "hate", "horrible", "terrible", "disaster",
    "crisis", "suffer", "suffering", "civilians", "refugees",
    "children", "shame"
}

def adjusted_sentiment(text: str, language: str = "auto") -> float:
    """
    中英文分流情感分析：
    中文：SnowNLP + 中文词典修正
    英文：TextBlob + 英文战争领域词修正
    """
    if pd.isna(text) or len(str(text)) < 5:
        return 0.5

    text = str(text)

    if language == "auto":
        language = detect_language(text)

    #英文评论：使用 TextBlob，不再用 SnowNLP
    if language == "en":
        try:
            polarity = TextBlob(text).sentiment.polarity  # 范围 [-1, 1]
            score = (polarity + 1) / 2                    # 转成 [0, 1]
        except:
            score = 0.5

        words = set(re.findall(r"[A-Za-z][A-Za-z'\-]*", text.lower()))

        pos_hits = len(words & POS_WORDS_EN)
        neg_hits = len(words & NEG_WORDS_EN)

        if pos_hits:
            score = min(1.0, score + min(0.2, pos_hits * 0.06))
        if neg_hits:
            score = max(0.0, score - min(0.25, neg_hits * 0.06))

        return max(0.0, min(1.0, score))

    #中文评论：保持你原来的 SnowNLP 逻辑
    score = SnowNLP(text).sentiments

    for word in POS_WORDS:
        if word in text:
            score = min(1.0, score + 0.2)
            break

    for word in NEG_WORDS:
        if word in text:
            score = max(0.0, score - 0.3)
            break

    if any(neg in text for neg in ['不', '没', '无', '别']):
        score = score * 0.7

    return max(0.0, min(1.0, score))

def classify_sentiment(score: float) -> str:
    if score > 0.7:
        return "正面"
    elif score < 0.3:
        return "负面"
    return "中性"

def sentiment_analysis():
    print("开始情感分析")
    input_path = PROCESSED_DIR / "cleaned_data.csv"
    if not input_path.exists():
        print(f"文件不存在：{input_path}")
        return None

    df = pd.read_csv(input_path, encoding='utf-8-sig')
    print(f"评论总数：{len(df)}")

    #如果 cleaned_data.py 已经生成 language 字段，就直接使用；否则现场识别
    if 'language' not in df.columns:
        df['language'] = df['cleaned_text'].apply(detect_language)

    df['sentiment_score'] = df.apply(
        lambda row: adjusted_sentiment(row['cleaned_text'], row['language']),
        axis=1
    )

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