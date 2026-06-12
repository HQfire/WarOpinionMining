# analysis/utils.py
"""
公共工具：文本清洗、停用词加载、分词、列标准化
"""
import re
import pandas as pd
from pathlib import Path
import jieba
import jieba.posseg as pseg
from typing import List, Set

# 统一导入项目配置
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import STOPWORDS_DIR, DEFAULT_STOPWORDS_ZHS, USER_DICT_WORDS, ENTITY_STOP


def load_stopwords(stopwords_dir: Path = STOPWORDS_DIR) -> Set[str]:
    """
    加载合并停用词：文件 + 内置默认词表
    避免因文件为空导致无过滤
    """
    stopwords = set(DEFAULT_STOPWORDS_ZHS)          # 先用内置兜底
    for file in stopwords_dir.glob("*.txt"):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                words = {line.strip() for line in f if line.strip()}
            if words:                               # 文件非空则更新
                stopwords.update(words)
        except:
            pass
    # 可选：加入英文停用词（当前未使用）
    try:
        import nltk
        from nltk.corpus import stopwords as nltk_stop
        stopwords.update(nltk_stop.words('english'))
    except:
        pass
    return stopwords


def add_jieba_userdict(words: List[str] = USER_DICT_WORDS):
    """向 jieba 添加用户词典，防止专有名词切错"""
    for word in words:
        jieba.add_word(word, freq=1000, tag='n')   # 标为名词


def advanced_clean_text(text: str) -> str:
    """
    增强版文本清洗，处理网络噪声、多语言、表情等
    """
    if not isinstance(text, str) or pd.isna(text):
        return ""
    # 去除URL、@提及、HTML、表情、特殊符号
    text = re.sub(r'http\S+|@\w+|【.*?】|《.*?》|<.*?>', '', text)
    text = re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF]+', '', text)
    # 只保留中英文、数字、基本标点
    text = re.sub(r'[^\w\u4e00-\u9fff.,!?，。！？]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def tokenize(text: str, stopwords: Set[str] = None) -> List[str]:
    """
    分词+词性过滤：仅保留名词、动词、形容词、副词等观点性词性
    返回清洗后的词列表
    """
    if not stopwords:
        stopwords = load_stopwords()
    if not isinstance(text, str) or not text.strip():
        return []
    words = pseg.cut(text)
    # 允许的词性前缀集合（可根据需要调整）
    allowed_pos = {'n', 'v', 'a', 'ad', 'an', 'vn', 'd', 'vd'}
    tokens = []
    for word, flag in words:
        w = word.strip()
        if len(w) <= 1:
            continue
        if w in stopwords or w in ENTITY_STOP:
            continue
        # 词性过滤
        if flag and any(flag.startswith(pos) for pos in allowed_pos):
            tokens.append(w)
    return tokens


def standardize_columns(df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """将不同来源的DataFrame列名统一"""
    col_map = {
        'content': ['text', 'comment', 'body', 'message'],
        'timestamp': ['time', 'date', 'created_at'],
        'user': ['username', 'nick', 'author'],
        'likes': ['like', '点赞', 'fav'],
    }
    for target, candidates in col_map.items():
        for cand in candidates:
            if cand in df.columns:
                df = df.rename(columns={cand: target})
                break
    # 确保必要列存在
    for col in ['content', 'timestamp']:
        if col not in df.columns:
            df[col] = ""
    df['platform'] = platform
    return df
