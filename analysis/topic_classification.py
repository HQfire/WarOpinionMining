#主题分类模块（规则+TF-IDF&KMeans聚类）
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import jieba.analyse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
import numpy as np
from config import PROCESSED_DIR
from analysis.utils import add_jieba_userdict

add_jieba_userdict()

#扩展规则分类关键词
RULE_MAP = [
    ('和平反战', ['和平', '反战', '停火', '谈判', '结束战争']),
    ('战争影响', ['影响', '经济', '油价', '生活', '物价', '后果', '危机']),
    ('势力评价', ['美国', '以色列', '伊朗', '特朗普', '内塔尼亚胡', '拜登', '政府']),
    ('中国态度', ['中国', '网友', '我们', '自己', '站队', '置身']),
    ('军事行动', ['打击', '空袭', '导弹', '航母', '反击', '防御']),
    ('人道灾难', ['平民', '伤亡', '难民', '儿童', '医院', '人道']),
    ('媒体舆论', ['报道', '媒体', '新闻', '视频', '截图', '真实性']),
]

def rule_based_label(text: str) -> str:
    #基于关键词的规则分类
    for label, keywords in RULE_MAP:
        if any(k in text for k in keywords):
            return label
    return '其他'

def clustering_labels(texts, tokens_series, n_clusters=6):
    #基于TF-IDF+KMeans的聚类，并给出每类 top 词
    #用已分词的tokens列作为输入
    docs = [' '.join(tokens) if isinstance(tokens, list) else tokens for tokens in tokens_series]

    vec = TfidfVectorizer(max_features=5000, token_pattern=r'(?u)\b\w+\b')
    X = vec.fit_transform(docs)

    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    clusters = kmeans.fit_predict(X)

    #每类关键词
    order_centroids = kmeans.cluster_centers_.argsort()[:, ::-1]
    terms = vec.get_feature_names_out()
    cluster_keywords = {}
    for i in range(n_clusters):
        top_words = [terms[ind] for ind in order_centroids[i, :10]]
        cluster_keywords[i] = top_words

    #计算每类的文本数量
    cluster_counts = pd.Series(clusters).value_counts()
    print("\nKMeans 聚类主题自动发现：")
    for cid in range(n_clusters):
        print(f"  主题 {cid+1} ({cluster_counts.get(cid,0)} 条): {', '.join(cluster_keywords[cid])}")
    return clusters, cluster_keywords

def topic_classification():
    print("开始主题分类与聚类...")
    input_path = PROCESSED_DIR / "cleaned_data.csv"
    if not input_path.exists():
        print(f"文件不存在：{input_path}")
        return None

    df = pd.read_csv(input_path, encoding='utf-8-sig')
    #确保有'tokens'列，若有则转为列表
    if 'tokens' in df.columns:
        df['tokens'] = df['tokens'].apply(lambda x: eval(x) if isinstance(x, str) else x)
    else:
        #若没有tokens，用分词函数重新生成
        from analysis.utils import tokenize, load_stopwords
        stop = load_stopwords()
        df['tokens'] = df['cleaned_text'].apply(lambda x: tokenize(str(x), stop))

    #1.规则分类
    df['rule_topic'] = df['cleaned_text'].apply(rule_based_label)
    print("\n规则分类结果：")
    print(df['rule_topic'].value_counts())

    #2.聚类辅助分类
    if len(df) >= 20:
        clusters, kw_dict = clustering_labels(df['cleaned_text'], df['tokens'])
        #将聚类编号转为标签
        df['cluster'] = clusters
    else:
        print("评论数不足，跳过聚类")

    #输出汇总报告
    print("\n综合主题分析报告：")
    for topic in sorted(df['rule_topic'].unique()):
        sub = df[df['rule_topic'] == topic]
        print(f"\n【{topic}】共 {len(sub)} 条")
        #情感分布
        if 'sentiment' in sub.columns:
            print(sub['sentiment'].value_counts(normalize=True).head())

    #保存结果
    output_path = PROCESSED_DIR / "topic_results.csv"
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"\n结果已保存至：{output_path}")
    return df

if __name__ == "__main__":
    topic_classification()