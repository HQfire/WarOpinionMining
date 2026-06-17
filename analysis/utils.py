#公共工具：文本清洗、停用词加载、分词、列标准化
import re
import pandas as pd
from pathlib import Path
import jieba
import jieba.posseg as pseg
from typing import List, Set

#统一导入项目配置
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import STOPWORDS_DIR, DEFAULT_STOPWORDS_ZHS, USER_DICT_WORDS, ENTITY_STOP
from config import STOPWORDS_DIR, DEFAULT_STOPWORDS_ZHS, USER_DICT_WORDS, ENTITY_STOP

# 英文停用词兜底，避免 YouTube 英文评论进入 jieba 中文分词后效果很差
DEFAULT_STOPWORDS_EN = {
    "a", "an", "the", "and", "or", "but", "if", "while", "with", "without",
    "of", "to", "in", "on", "for", "from", "by", "at", "as", "is", "are",
    "was", "were", "be", "been", "being", "am", "do", "does", "did", "doing",
    "have", "has", "had", "having", "it", "its", "this", "that", "these", "those",
    "i", "you", "he", "she", "we", "they", "them", "his", "her", "their", "our",
    "my", "your", "me", "him", "who", "what", "when", "where", "why", "how",
    "not", "no", "so", "very", "just", "can", "could", "should", "would", "will",
    "all", "any", "some", "more", "most", "many", "much", "about", "into", "over",
    "also", "than", "then", "there", "here", "out", "up", "down",
    "video", "news", "people"
}

PLATFORM_MAP = {
    "bilibili_raw": "bilibili",
    "weibo_raw": "weibo",
    "youtube_comments": "youtube",
    "知乎_posts": "zhihu",
    "zhihu_posts": "zhihu",
}


def detect_language(text: str) -> str:
    """
    简单判断文本语言：
    zh = 中文
    en = 英文
    other = 其他
    """
    if not isinstance(text, str) or not text.strip():
        return "other"

    chinese_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    english_words = re.findall(r"[A-Za-z]{2,}", text)
    english_count = sum(len(w) for w in english_words)

    if chinese_count >= 2 and chinese_count >= english_count * 0.3:
        return "zh"
    if english_count >= 8 and len(english_words) >= 2:
        return "en"

    return "other"


def normalize_platform(platform: str) -> str:
    """
    把文件名平台统一成可读平台名。
    例如 youtube_comments -> youtube
    """
    key = str(platform).strip()
    return PLATFORM_MAP.get(key, key)

def load_stopwords(stopwords_dir: Path = STOPWORDS_DIR) -> Set[str]:
    """
    加载合并停用词：中文默认词 + 英文默认词 + stopwords/*.txt
    """
    stopwords = set(DEFAULT_STOPWORDS_ZHS)
    stopwords.update(DEFAULT_STOPWORDS_EN)

    for file in stopwords_dir.glob("*.txt"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                words = {line.strip().lower() for line in f if line.strip()}
            if words:
                stopwords.update(words)
        except:
            pass

    try:
        from nltk.corpus import stopwords as nltk_stop
        stopwords.update(w.lower() for w in nltk_stop.words("english"))
    except:
        pass

    return stopwords

def add_jieba_userdict(words: List[str] = USER_DICT_WORDS):
   #向 jieba 添加用户词典，防止专有名词切错
    for word in words:
        jieba.add_word(word, freq=1000, tag='n')   #标为名词

def advanced_clean_text(text: str) -> str:
    if not isinstance(text, str) or pd.isna(text):
        return ""
    text = re.sub(r'\[[^\[\]\n]*?\]', '', text)
    #去除URL、@提及、HTML、书名号/中文方括号内容、emoji表情、特殊符号
    text = re.sub(r'http\S+|@\w+|【.*?】|《.*?》|<.*?>', '', text)
    text = re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF]+', '', text)
    #只保留中英文、数字、基本标点
    text = re.sub(r'[^\w\u4e00-\u9fff.,!?，。！？]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def tokenize(text: str, stopwords: Set[str] = None, language: str = "auto") -> List[str]:
    """
    中英文分流分词：
    中文：jieba + 词性过滤
    英文：正则切词 + 英文停用词过滤
    """
    if not stopwords:
        stopwords = load_stopwords()
    if not isinstance(text, str) or not text.strip():
        return []

    if language == "auto":
        language = detect_language(text)

    # 英文评论：不要走 jieba，直接英文分词
    if language == "en":
        words = re.findall(r"[A-Za-z][A-Za-z'\-]{1,}", text.lower())
        tokens = []
        for word in words:
            word = word.strip("'-_").lower()
            if len(word) <= 2:
                continue
            if word in stopwords or word in ENTITY_STOP:
                continue
            tokens.append(word)
        return tokens

    #中文评论：保持你原来的 jieba 词性过滤逻辑
    words = pseg.cut(text)
    allowed_pos = {'n', 'v', 'a', 'ad', 'an', 'vn', 'd', 'vd'}
    tokens = []

    for word, flag in words:
        w = word.strip()
        if len(w) <= 1:
            continue
        if w in stopwords or w in ENTITY_STOP:
            continue
        if flag and any(flag.startswith(pos) for pos in allowed_pos):
            tokens.append(w)

    return tokens

def standardize_columns(df: pd.DataFrame, platform: str) -> pd.DataFrame:
    #将不同来源的DataFrame列名统一
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
    #确保必要列存在
    for col in ['content', 'timestamp']:
        if col not in df.columns:
            df[col] = ""
    df['platform'] = normalize_platform(platform)

    #增加 language 字段，后续 clean_data.py 会重新识别
    if 'language' not in df.columns:
        df['language'] = "auto"

    return df