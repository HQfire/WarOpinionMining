#观点情感关键词提取
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import jieba.analyse
import jieba.posseg as pseg
from config import PROCESSED_DIR, ENTITY_STOP
from analysis.utils import add_jieba_userdict
add_jieba_userdict()

def load_cleaned_data() -> pd.DataFrame:
    data_path = PROCESSED_DIR / "cleaned_data.csv"
    if not data_path.exists():
        print(f"文件不存在：{data_path}，请先运行 clean_data.py")
        return None
    df = pd.read_csv(data_path, encoding='utf-8-sig')
    print(f"加载 {len(df)} 条评论")
    return df

def extract_opinion_keywords(df: pd.DataFrame) -> list:
    """
    从 cleaned_data.csv 中提取关键词。
    优先使用 clean_data.py 已经生成好的 tokens 字段：
    - 中文 tokens 已经经过 jieba 词性过滤
    - 英文 tokens 已经经过英文分词和停用词过滤
    这样关键词提取和词云可以共用同一套清洗结果。
    """
    print("正在基于 tokens 提取关键词 ...")

    import ast
    import re
    from collections import defaultdict

    opinion_boost = {
        '和平', '支持', '反对', '担忧', '正义', '无能', '认怂',
        '加油', '胜利', '停火', '残暴', '人道', '危机', '谴责',
        '霸权', '双标', '可笑', '悲剧', '虚伪', '胆敢', '侵略',
        '伟大', '文明', '守护', '共赢', '站队', '置身事外',

        'peace', 'support', 'ceasefire', 'justice', 'hope',
        'freedom', 'humanitarian', 'victory', 'protect',
        'terrorist', 'genocide', 'massacre', 'crime',
        'evil', 'hate', 'terrible', 'disaster', 'crisis',
    }

    vague_filter = {
        '没有', '应该', '可能', '知道', '还有', '不会', '需要',
        '估计', '看到', '觉得', '感觉', '真的', '可以', '怎么',
        '什么', '为什么', '这样', '那样', '这个', '那个', '一些',
        '很多', '有点', '比较', '非常', '很', '了', '还', '是',
        '有', '说', '想', '做', '去', '来', '看', '让', '会',
        '能', '要', '没', '不', '都', '也', '就', '个', '着',
        '吗', '吧', '啊', '呢', '呀', '上', '下', '人', '这',
        '不能', '不住', '不了', '不用', '看看', '回复',
        '不是', '也是', '还是', '只是', '可是', '总是',
        '一样', '这么', '那么', '出来', '起来', '过来',
        '只能', '才能', '开始', '结束', '变成', '看着', '存在',

        'think', 'thinking', 'thought',
        'know', 'known', 'see', 'seen', 'look', 'watch',
        'say', 'said', 'tell', 'told',
        'make', 'made', 'take', 'took',
        'go', 'going', 'come', 'coming',
        'get', 'got', 'give', 'given',
        'want', 'wanted', 'need', 'needed',
        'like', 'really', 'very', 'maybe', 'probably',
        'actually', 'basically', 'literally',
        'thing', 'things', 'something', 'anything', 'nothing',
        'someone', 'everyone', 'anyone', 'people',
        'time', 'day', 'year', 'years',
        'way', 'point', 'case', 'side',
        'yes', 'yeah', 'nope', 'ok', 'okay',
        'please', 'thanks', 'thank',
        'lol', 'lmao', 'omg',
        'one', 'even', 'never', 'always', 'still', 'back',
        'let', 'must', 'right',
    }

    entity_set = {str(w).strip().lower() for w in ENTITY_STOP if str(w).strip()}
    vague_set = {str(w).strip().lower() for w in vague_filter if str(w).strip()}
    boost_set = {str(w).strip().lower() for w in opinion_boost if str(w).strip()}

    weight_sum = defaultdict(float)

    for _, row in df.iterrows():
        tokens_value = row.get('tokens', '')

        if pd.isna(tokens_value):
            continue

        try:
            if isinstance(tokens_value, str):
                tokens = ast.literal_eval(tokens_value)
            else:
                tokens = tokens_value
        except Exception:
            tokens = str(tokens_value).split()

        if not isinstance(tokens, list):
            continue

        for token in tokens:
            word = str(token).strip()
            if not word:
                continue

            word_lower = word.lower()

            if len(word_lower) <= 1:
                continue

            #过滤纯数字、CPU 型号、无意义编号，例如 2667v3、1650v3
            if re.fullmatch(r"[0-9]+[a-z0-9]*", word_lower):
                continue

            if word_lower in entity_set:
                continue

            if word_lower in vague_set:
                continue

            #英文太短的词过滤掉
            if re.fullmatch(r"[a-z]+", word_lower) and len(word_lower) <= 2:
                continue

            #观点词略微加权
            weight = 1.5 if word_lower in boost_set else 1.0
            weight_sum[word_lower] += weight

    sorted_kw = sorted(weight_sum.items(), key=lambda x: x[1], reverse=True)[:30]
    return sorted_kw

def print_report(keywords: list, df: pd.DataFrame):
    print("\n网友观点情感关键词Top12：")
    for w, wt in keywords[:12]:
        print(f"  {w}: {wt:.2f}")
    emotion_pattern = '和平|反对战争|支持和平|反战|停火|谴责'
    emotion_df = df[df['cleaned_text'].str.contains(emotion_pattern, case=False, na=False)]
    print(f"\n和平/反战相关评论 {len(emotion_df)} 条（占比 {len(emotion_df)/len(df):.2%}）")

def save_keywords(keywords: list, output_dir: Path = PROCESSED_DIR):
    #仅保存为 CSV
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "keywords.csv"
    kw_df = pd.DataFrame(keywords, columns=['keyword', 'weight'])
    kw_df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f"关键词已保存：{csv_path}")
if __name__ == "__main__":
    df = load_cleaned_data()
    if df is not None:
        kw = extract_opinion_keywords(df)
        print_report(kw, df)
        save_keywords(kw)