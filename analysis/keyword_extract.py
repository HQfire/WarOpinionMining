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
    print("正在逐条评论提取关键词 ...")
    comment_keywords = []
    opinion_boost = {
        '和平', '支持', '反对', '担忧', '正义', '无能', '认怂',
        '加油', '胜利', '停火', '残暴', '人道', '危机', '谴责',
        '霸权', '双标', '可笑', '悲剧', '虚伪', '胆敢', '侵略',
        '伟大', '文明', '守护', '共赢', '站队', '置身事外',
    }
    entity_set = ENTITY_STOP

    #明确要屏蔽的空泛词
    vague_filter = {
        #原有一批
        '没有', '应该', '可能', '知道', '还有', '不会', '需要',
        '估计', '看到', '觉得', '感觉', '真的', '可以', '怎么',
        '什么', '为什么', '这样', '那样', '这个', '那个', '一些',
        '很多', '有点', '比较', '非常', '很', '了', '还', '是',
        '有', '说', '想', '做', '去', '来', '看', '让', '会',
        '能', '要', '没', '不', '都', '也', '就', '个', '着',
        '吗', '吧', '啊', '呢', '呀', '上', '下', '人', '这',
        #新增
        '不能', '不住', '不了', '不用', '看看', '回复',
        '不是', '也是', '还是', '只是', '可是', '总是',
        '一样', '这么', '那么', '出来', '起来', '过来',
    }

    for idx, row in df.iterrows():
        text = str(row.get('cleaned_text', ''))
        if len(text) < 10:
            continue
        words = pseg.cut(text)
        filtered = ' '.join([word for word, flag in words
                             if (flag.startswith(('v', 'a', 'd', 'an', 'vn'))
                                 or word in opinion_boost)
                             and word not in entity_set
                             and len(word) > 1])
        if not filtered.strip():
            continue
        kw = jieba.analyse.textrank(filtered, topK=5, withWeight=True)
        comment_keywords.extend(kw)

    from collections import defaultdict
    weight_sum = defaultdict(float)
    for w, wt in comment_keywords:
        if w not in entity_set and w not in vague_filter:   #过滤空泛词
            weight_sum[w] += wt

    sorted_kw = sorted(weight_sum.items(), key=lambda x: x[1], reverse=True)[:20]
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