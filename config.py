# config.py
"""
项目全局配置：路径、常量、领域词等
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent        # 此文件位于根目录
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
STOPWORDS_DIR = PROJECT_ROOT / "stopwords"
DEBUG_DIR = PROJECT_ROOT / "output" / "debug"
DOCS_DIR = PROJECT_ROOT / "docs"

#确保关键目录存在
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

#中文默认停用词
DEFAULT_STOPWORDS_ZHS = {
    '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一',
    '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着',
    '没有', '看', '好', '自己', '这', '他', '她', '它', '们', '那', '还',
    '但', '被', '让', '比', '等', '吧', '吗', '啊', '呢', '呀', '哦',
    '所以', '如果', '因为', '虽然', '但是', '然而', '而且', '之',
    '一些', '这个', '那个', '什么', '怎么', '为什么', '可以', '应该',
    '觉得', '感觉', '知道', '不能', '可能', '时候', '已经', '现在',
    '还是', '只是', '然后', '以为', '真的', '其实', '太', '非常', '最',
    '更', '过', '啦', '哈', '嘛', '噢', '嗯', '哎', '哼', '呵', '嘻嘻',
    '哈哈', '无语', '哦', '噗', '呵呵', '嘿嘿', '咳咳', '嗷', '嘤',
    '啊这', '卧槽', '牛逼', '666', '点', '回复', '赞', '举报', '举报者',
    '来自', '网页', '链接', 'http', 'https', 'httpstco', '转发',
    #可根据需要继续扩充
}

#领域词字典
USER_DICT_WORDS = [
    '特朗普', '内塔尼亚胡', '以色列', '伊朗', '中东', '反战', '停火',
    '石油', '航母', '导弹', '消耗战', '认怂', '无能', '正义',
    '自卫', '反击', '合法', '和平解决', '世界和平', '不支持',
]

#实体屏蔽词
ENTITY_STOP = {
    '中国', '世界', '伊朗', '以色列', '美国', '特朗普', '拜登',
    '内塔尼亚胡', '鱿鱼', '导弹', '航母', '消耗战', '中东', '全球',
    '石油', '军事', '打击', '国家', '报道', '敌人', '神棍', '生活',
    '全世界', '时候', '继续', '进入', '出来', '打工', '要钱',
    '击', '打成', '轰炸', '攻击', '袭击', '战争', '局势',
    '视频', '评论', '感觉', '真的', '已经', '现在', '这个', '那个',
    '他们', '我们', '你们', '东西', '问题', '事情', '认为',
    'usa', 'us', 'america', 'american', 'americans',
    'iran', 'iranian', 'iranians',
    'israel', 'israeli', 'israelis',
    'china', 'chinese',
    'middle', 'east', 'middleeast',
    'trump', 'biden', 'netanyahu',
    'government', 'country', 'countries',
    'world', 'global', 'international',
    'war', 'conflict', 'battle', 'fight',
    'military', 'army', 'navy', 'airforce',
    'missile', 'missiles', 'drone', 'drones',
    'bomb', 'bombs', 'bombing',
    'attack', 'attacks', 'attacked',
    'strike', 'strikes',
    'news', 'media', 'report', 'reports', 'reported',
    'video', 'comment', 'comments',
}
