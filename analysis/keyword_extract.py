"""
关键词提取模块
===========
从清洗后的评论数据中提取关键词，支持TF-IDF和TextRank两种算法。
自动识别中英文文本，分别使用jieba和nltk进行分词处理，
使用自定义停用词表过滤无意义词汇。

提取流程：
1. 加载停用词表（中/英）
2. 检测每条评论的语言
3. 根据语言选择分词器进行分词
4. 使用TF-IDF或TextRank算法提取关键词
5. 将关键词及其权重保存到输出文件
"""

import os
import re
import pandas as pd
import numpy as np
from collections import Counter


def load_stopwords(lang):
    """
    加载指定语言的停用词表。

    参数:
        lang: str, 语言代码 'zh'（中文）或 'en'（英文）

    返回:
        set, 停用词集合
    """
    # 基于当前文件位置定位项目根目录下的stopwords文件夹
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if lang == 'zh':
        stopwords_path = os.path.join(base_dir, "stopwords", "chinese_stopwords.txt")
    elif lang == 'en':
        stopwords_path = os.path.join(base_dir, "stopwords", "english_stopwords.txt")
    else:
        raise ValueError(f"不支持的语言代码: {lang}，请使用 'zh' 或 'en'")

    if not os.path.exists(stopwords_path):
        print(f"[警告] 停用词文件不存在: {stopwords_path}，将使用空集合")
        return set()

    with open(stopwords_path, 'r', encoding='utf-8') as f:
        stopwords = set(line.strip() for line in f if line.strip())

    print(f"[停用词] 加载 {lang} 停用词 {len(stopwords)} 个")
    return stopwords


def detect_language(text):
    """
    使用langdetect库检测文本语言。
    由于langdetect对短文本准确率较低，对于极短文本直接判断字符集。

    参数:
        text: str, 输入文本

    返回:
        str, 'zh' 表示中文, 'en' 表示英文
    """
    if not text or not isinstance(text, str) or len(text.strip()) == 0:
        return 'zh'

    text = text.strip()

    # 统计中文字符数量——用于辅助判断
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    # 统计英文字母数量
    english_chars = len(re.findall(r'[a-zA-Z]', text))

    # 如果中文字符明显多于英文字符，直接返回zh（处理langdetect对短文本误判的情况）
    if chinese_chars > english_chars * 2 and chinese_chars > 2:
        return 'zh'

    # 尝试使用langdetect库进行语言检测
    try:
        from langdetect import detect
        lang = detect(text)
        if lang.startswith('zh'):
            return 'zh'
        else:
            return 'en'
    except ImportError:
        # 如果langdetect不可用，回退到基于字符比例的简单判断
        if chinese_chars > english_chars:
            return 'zh'
        else:
            return 'en'
    except Exception:
        # langdetect可能对某些文本抛出异常，回退到字符判断
        if chinese_chars > english_chars:
            return 'zh'
        else:
            return 'en'


def segment_chinese(text, stopwords):
    """
    使用jieba对中文文本进行分词，并过滤停用词和单字词。

    参数:
        text: str, 中文文本
        stopwords: set, 停用词集合

    返回:
        list, 分词后的词语列表
    """
    import jieba

    # 使用jieba精确模式分词
    words = jieba.lcut(text)

    # 过滤：去除停用词、单字词、纯数字、纯标点符号
    filtered = []
    for w in words:
        w = w.strip()
        # 跳过空字符串
        if not w:
            continue
        # 跳过停用词
        if w in stopwords:
            continue
        # 跳过单字词（单个汉字意义不大）
        if len(w) <= 1:
            continue
        # 跳过纯数字或纯标点
        if re.match(r'^[\d\.\,\-\+]+$', w):
            continue
        # 确保包含至少一个中文字符
        if re.search(r'[\u4e00-\u9fff]', w):
            filtered.append(w)

    return filtered


def segment_english(text, stopwords):
    """
    使用nltk对英文文本进行分词，并过滤停用词，仅保留纯字母词。

    参数:
        text: str, 英文文本
        stopwords: set, 停用词集合

    返回:
        list, 分词后的词语列表
    """
    try:
        import nltk
        try:
            nltk.data.find('tokenizers/punkt_tab')
        except LookupError:
            try:
                nltk.download('punkt_tab', quiet=True)
            except Exception:
                try:
                    nltk.download('punkt', quiet=True)
                except Exception:
                    raise ImportError("nltk download blocked")

        tokens = nltk.word_tokenize(text)
    except (ImportError, Exception):
        tokens = re.findall(r'[a-zA-Z]+', text.lower())

    # 过滤：仅保留纯字母词、非停用词、长度大于2
    filtered = []
    for token in tokens:
        token = token.strip().lower()
        if not token:
            continue
        if token in stopwords:
            continue
        if not token.isalpha():
            continue
        if len(token) <= 2:
            continue
        filtered.append(token)

    return filtered


def extract_tfidf(texts, top_k=20):
    """
    使用sklearn的TfidfVectorizer提取TF-IDF关键词。

    算法原理：
    - TF-IDF通过词频(TF)和逆文档频率(IDF)的乘积来衡量词语重要性
    - max_df=0.85: 出现在超过85%文档中的词被视为过于常见，忽略
    - min_df=2: 只出现在少于2篇文档中的词被视为过于罕见，忽略

    参数:
        texts: list of str, 分词后的文档列表（每篇文档为空格分隔的词串）
        top_k: int, 返回前k个关键词

    返回:
        list of tuples, [(关键词, TF-IDF分数), ...]
    """
    from sklearn.feature_extraction.text import TfidfVectorizer

    # 过滤空文档
    valid_texts = [t for t in texts if t.strip()]
    if not valid_texts:
        print("[TF-IDF] 警告: 没有有效的分词文本")
        return []

    # 构建TF-IDF向量化器
    # max_df=0.85: 过滤掉在超过85%文档中出现的超高频词
    # min_df=2: 过滤掉只在少于2篇文档中出现的超低频词
    # token_pattern: 匹配至少2个字符的token
    vectorizer = TfidfVectorizer(
        max_df=0.85,
        min_df=2,
        token_pattern=r'(?u)\b\w+\b'
    )

    try:
        tfidf_matrix = vectorizer.fit_transform(valid_texts)
    except ValueError:
        print("[TF-IDF] 警告: 词汇量不足，无法提取有意义的TF-IDF关键词")
        return []

    # 获取特征名称（词汇表）
    feature_names = vectorizer.get_feature_names_out()

    # 计算每个词在所有文档中的平均TF-IDF分数
    mean_tfidf = np.array(tfidf_matrix.mean(axis=0)).flatten()

    # 按分数降序排序，取top_k
    top_indices = mean_tfidf.argsort()[::-1][:top_k]
    keywords = [(feature_names[i], float(mean_tfidf[i])) for i in top_indices if mean_tfidf[i] > 0]

    return keywords


def extract_textrank(texts, top_k=20):
    """
    基于词共现的自定义TextRank关键词提取算法。

    算法原理：
    1. 使用滑动窗口（window=5）构建词共现矩阵
    2. 将每个词视为图节点，共现关系视为边，边权重为共现次数
    3. 使用类似PageRank的迭代算法计算每个节点的重要性分数
    4. 收敛后按分数降序排序返回top_k关键词

    参数:
        texts: list of str, 分词后的文档列表（每篇文档为空格分隔的词串）
        top_k: int, 返回前k个关键词

    返回:
        list of tuples, [(关键词, TextRank分数), ...]
    """
    window_size = 5
    # 阻尼系数，类似PageRank中的damping factor
    d = 0.85
    # 最大迭代次数
    max_iter = 100
    # 收敛阈值
    min_diff = 1e-6

    # 第一步：统计所有词汇并建立词到索引的映射
    word_counter = Counter()
    all_words = []

    for text in texts:
        if not text.strip():
            continue
        words = text.strip().split()
        word_counter.update(words)
        all_words.append(words)

    if len(word_counter) < 2:
        print("[TextRank] 词汇量不足，无法构建图模型")
        return []

    # 建立词到索引的映射
    unique_words = list(word_counter.keys())
    word2idx = {w: i for i, w in enumerate(unique_words)}
    vocab_size = len(unique_words)

    # 第二步：使用滑动窗口构建词共现矩阵
    # co_occur[i][j] 表示词i和词j在窗口内共现的次数
    co_occur = np.zeros((vocab_size, vocab_size), dtype=np.float64)

    for words in all_words:
        # 对于每个文档，使用大小为window_size的滑动窗口
        for i in range(len(words)):
            # 窗口范围: 当前词前后各 window_size//2 个词
            start = max(0, i - window_size // 2)
            end = min(len(words), i + window_size // 2 + 1)
            for j in range(start, end):
                if i == j:
                    continue
                wi = word2idx.get(words[i])
                wj = word2idx.get(words[j])
                if wi is not None and wj is not None:
                    co_occur[wi][wj] += 1.0
                    co_occur[wj][wi] += 1.0

    # 第三步：对共现矩阵做行归一化，构建转移概率矩阵
    # 添加平滑处理，避免除零
    row_sums = co_occur.sum(axis=1)
    row_sums[row_sums == 0] = 1.0
    transition = co_occur / row_sums[:, np.newaxis]

    # 第四步：初始化分数并迭代PageRank
    scores = np.ones(vocab_size, dtype=np.float64) / vocab_size

    for iteration in range(max_iter):
        prev_scores = scores.copy()
        # PageRank迭代公式: score = (1-d)/N + d * M^T * score
        # 其中M是转移矩阵，d是阻尼系数
        scores = (1 - d) / vocab_size + d * transition.T.dot(scores)
        # 检查收敛
        diff = np.abs(scores - prev_scores).sum()
        if diff < min_diff:
            break

    # 第五步：按分数排序，返回top_k关键词
    top_indices = scores.argsort()[::-1][:top_k]
    keywords = [(unique_words[i], float(scores[i])) for i in top_indices if scores[i] > 0]

    return keywords


def extract_keywords(df, method='tfidf', top_k=20):
    """
    从DataFrame的评论中提取关键词的主函数。

    处理流程：
    1. 加载中英文停用词
    2. 对每行评论检测语言
    3. 根据语言选择分词器进行分词
    4. 将所有分词结果合并为一个文档集
    5. 使用指定方法提取关键词
    6. 将关键词信息添加到DataFrame

    参数:
        df: pd.DataFrame, 包含'content'列的评论数据
        method: str, 关键词提取方法，'tfidf' 或 'textrank'
        top_k: int, 提取的关键词数量

    返回:
        pd.DataFrame, 添加了'keywords'列的数据框
    """
    print(f"[关键词提取] 使用方法: {method}, 提取数量: top_{top_k}")

    # 加载中英文停用词
    zh_stopwords = load_stopwords('zh')
    en_stopwords = load_stopwords('en')

    # 逐行处理：检测语言 -> 分词 -> 收集
    segmented_docs = []  # 用于存储分词后的文档（空格分隔）
    lang_list = []       # 记录每行的语言

    total = len(df)
    for idx, row in df.iterrows():
        content = row.get('content', '')
        if not isinstance(content, str) or not content.strip():
            segmented_docs.append('')
            lang_list.append('zh')
            continue

        # 检测语言
        lang = detect_language(content)
        lang_list.append(lang)

        # 根据语言选择分词器
        if lang == 'zh':
            words = segment_chinese(content, zh_stopwords)
        else:
            words = segment_english(content, en_stopwords)

        # 将分词结果用空格连接，供后续TF-IDF/TextRank使用
        segmented_docs.append(' '.join(words))

        if (idx + 1) % 100 == 0 or (idx + 1) == total:
            print(f"  分词进度: {idx + 1}/{total}")

    print(f"[关键词提取] 分词完成，中文 {lang_list.count('zh')} 条，英文 {lang_list.count('en')} 条")

    # 根据指定方法提取关键词
    if method == 'tfidf':
        top_keywords = extract_tfidf(segmented_docs, top_k)
    elif method == 'textrank':
        top_keywords = extract_textrank(segmented_docs, top_k)
    else:
        print(f"[警告] 未知方法 '{method}'，使用TF-IDF作为默认方法")
        top_keywords = extract_tfidf(segmented_docs, top_k)

    # 构造关键词字符串，存入DataFrame
    # 格式: "词1:分数1; 词2:分数2; ..."
    import json
    kw_dict = {kw: round(score, 6) for kw, score in top_keywords}
    kw_json = json.dumps(kw_dict, ensure_ascii=False)

    # 添加分词结果列和关键词列
    df['segmented_content'] = segmented_docs
    df['detected_language'] = lang_list
    df['keywords'] = kw_json

    print(f"[关键词提取] 提取到 {len(top_keywords)} 个关键词:")
    for kw, score in top_keywords[:10]:
        print(f"  - {kw}: {score:.6f}")

    return df


def main():
    """
    关键词提取模块入口函数。

    从 data/processed/clean_data.csv 读取清洗后的评论数据，
    使用TF-IDF和TextRank两种方法提取关键词，
    结果保存到 data/processed/keywords.csv。
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    input_path = os.path.join(base_dir, "data", "processed", "clean_data.csv")
    output_path = os.path.join(base_dir, "data", "processed", "keywords.csv")
    output_dir = os.path.join(base_dir, "data", "processed")

    # 检查输入文件是否存在
    if not os.path.exists(input_path):
        print(f"[警告] 输入文件不存在: {input_path}")
        print("[提示] 请先运行 clean_data.py 生成清洗后的数据")
        # 尝试使用示例数据
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
        print(f"[读取] 共 {len(df)} 条数据")

        # 使用TF-IDF方法提取关键词（对混合语言效果更好）
        df = extract_keywords(df, method='tfidf', top_k=20)

        # 保存结果
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"[保存] 关键词提取结果已保存至: {output_path}")

    except Exception as e:
        print(f"[错误] 关键词提取过程中发生异常: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
