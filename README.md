# WarOpinionMining — 美以伊战争舆情挖掘系统

多平台社交网络评论数据采集 · 中英双语深度清洗 · 情感修正分析 · 主题分类 · 交互式可视化

---

## 项目简介

以美以对伊朗军事打击事件为背景，对 **微博、B站、YouTube** 三大平台的公众评论进行系统化采集、清洗、分析与可视化展示，构建从原始数据到交互式分析报告的全流程 Python 数据科学流水线。

通过定量分析方法，揭示不同文化背景下的公众对同一国际军事冲突的情感倾向与讨论主题差异，为国际舆情研究提供数据支撑。

---

## 项目结构

```
WarOpinionMining/
├── config.py                  # 全局配置（路径、停用词、领域词、实体屏蔽词）
├── requirements.txt           # Python 依赖清单（18 项）
├── run_pipeline.bat           # 一键全流程启动脚本（5 步自动执行）
├── analysis/                  # 分析模块层
│   ├── utils.py               #   公共工具：文本清洗 / 停用词加载 / 中英分流分词 / 列名标准化
│   ├── clean_data.py          #   数据清洗主模块：多源 CSV 加载 → 清洗 → 分词 → 去重
│   ├── sentiment_analysis.py  #   情感分析：SnowNLP + TextBlob 中英分流 + 修正词典
│   ├── keyword_extract.py     #   关键词提取：逐条汇总 + opinion_boost + 三层过滤
│   └── topic_classification.py#   主题分类：规则匹配 + TF-IDF + KMeans 双标签
├── crawlers/                  # 爬虫模块层
│   ├── crawl_weibo.py         #   微博评论爬虫（Edge + Selenium）
│   ├── crawl_bilibili.py      #   B站评论爬虫（API 三层回退 + WBI 签名）
│   └── crawl_youtube.py       #   YouTube 评论爬虫（Data API v3）
├── visualization/             # 可视化模块层
│   └── dashboard.py           #   pyecharts 交互式仪表盘 + 词云 + 自动结论生成
├── stopwords/                 # 自定义停用词表
│   ├── chinese_stopwords.txt
│   └── english_stopwords.txt
├── data/                      # 数据目录（自动生成）
│   ├── raw/                   #   原始采集数据（CSV）
│   └── processed/             #   清洗与分析结果（CSV）
├── output/                    # 输出目录（自动生成）
│   └── dashboard.html         #   交互式可视化仪表盘
└── docs/                      # 文档
    ├── project_flowchart.html #   项目流程图
    ├── generate_ppt.py        #   PPT 生成脚本
    ├── generate_report.py     #   大作业报告生成脚本
    └── speech_script.md       #   演讲稿
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 数据采集（按需运行）

```bash
# 微博（需要 Edge 浏览器 + 手动登录）
python crawlers/crawl_weibo.py

# B站（需要 Edge 浏览器 + 手动登录）
python crawlers/crawl_bilibili.py

# YouTube（需要 Google API Key 和代理）
python crawlers/crawl_youtube.py
```

### 3. 一键全流程分析

双击 **`run_pipeline.bat`** 或在项目根目录执行：

```bash
# Step 1: 数据清洗与预处理
python analysis/clean_data.py

# Step 2: 情感分析（SnowNLP + TextBlob 中英分流 + 修正词典）
python analysis/sentiment_analysis.py

# Step 3: 关键词提取（逐条汇总 + opinion_boost + 三层过滤）
python analysis/keyword_extract.py

# Step 4: 主题分类（规则匹配 + KMeans 聚类）
python analysis/topic_classification.py

# Step 5: 生成可视化仪表盘
python visualization/dashboard.py
```

### 4. 查看结果

用浏览器打开 `output/dashboard.html` 查看交互式分析仪表盘。

---

## 数据处理流程

```
run_pipeline.bat（一键启动）
        │
        ▼
┌──────────────────────────────────────────┐
│  数据采集层 (crawlers/)                    │
│  微博 · Selenium  │  B站 · API 三层回退   │
│  YouTube · Data API v3                    │
│        │  data/raw/*.csv                  │
└────────┼─────────────────────────────────┘
         ▼
┌──────────────────────────────────────────┐
│  数据清洗层 (analysis/clean_data.py)       │
│  Step 1: 多源加载 + 列名标准化              │
│  Step 2: 四层正则清洗（URL→HTML→@→Emoji）  │
│  Step 3: 中英分流分词                      │
│  Step 4: 去重 + 短文本过滤 + 停用词         │
│        │  cleaned_data.csv                │
└────────┼─────────────────────────────────┘
         ▼
┌──────────────────────────────────────────┐
│  NLP 分析层 (analysis/)                   │
│  情感分析  │  关键词提取  │  主题分类      │
│  SnowNLP   │  逐条汇总    │  规则+KMeans  │
│  +TextBlob │  +三层过滤   │  双标签互补    │
└────────────┬─────────────────────────────┘
         ▼
┌──────────────────────────────────────────┐
│  可视化层 (visualization/dashboard.py)    │
│  饼图 · 柱状图 · 折线图 · 词云 · 自动结论  │
│        │  output/dashboard.html          │
└──────────────────────────────────────────┘
```

---

## 核心功能

### 数据采集
- **微博**：Edge + Selenium 模拟浏览器，含反检测脚本，支持双格式评论解析
- **B站**：API 三层回退（旧版 API → WBI 签名新版 → Selenium DOM 兜底）
- **YouTube**：Google Data API v3 直连，支持代理配置

### 数据清洗
- 四层有序正则清洗（方括号标记 → URL/HTML/@ → Emoji → 字符过滤）
- `detect_language()` 中英自动分流
- 中文：`jieba.posseg` 词性过滤（仅保留 n/v/a/ad/an/vn/d/vd）
- 英文：正则分词 + 英文停用词过滤
- 多源 CSV 列名自动标准化 + 去重 + 短文本过滤

### 情感分析
- 中文：`SnowNLP` 基础评分 + 中文修正词典
- 英文：`TextBlob` 极性计算 + 英文修正词典
- 修正规则：正向词 +0.2 / 负向词 -0.3 / 否定词 ×0.7
- 三分类阈值：正面 >0.7 / 负面 <0.3 / 中性

### 关键词提取
- 重用清洗 tokens，避免重复分词
- 逐条评论独立统计 + 全局权重汇总
- `opinion_boost` 观点词增强（×1.5 权重）
- 三层过滤：停用词 → `ENTITY_STOP` 实体屏蔽 → `vague_filter` 空泛虚词

### 主题分类
- 7 类中英双语关键词规则匹配
- TF-IDF + KMeans 无监督聚类（6 簇）
- `rule_topic` + `cluster` 双标签互补验证

### 可视化
- 情感分布饼图 · 平台对比柱状图 · 时间趋势折线图 · 主题分布图
- matplotlib 词云图（含 700+ 定制停用词）
- 7 维度自动结论生成
- 响应式 HTML 页面布局（统计卡片 + 结论区 + 图表区 + 页脚）

---

## 技术栈

| 类别 | 技术 |
|------|------|
| 数据采集 | Selenium、requests、YouTube Data API v3、WBI 签名 |
| 数据清洗 | pandas、正则表达式、jieba（词性标注 + 自定义词典） |
| 情感分析 | SnowNLP（中文）、TextBlob（英文） |
| 关键词 | jieba.analyse、defaultdict 权重汇总 |
| 主题分类 | scikit-learn（TF-IDF + KMeans） |
| 可视化 | pyecharts、matplotlib、wordcloud、HTML/CSS |
| 文档生成 | python-docx、python-pptx |

---

## 团队成员

| 成员 | 分工 |
|------|------|
| 熊倡 | 项目结构设计、数据清洗配合、情感分析配合、可视化仪表盘、报告撰写 |
| 吴裕勇 | clean_data.py / utils.py / sentiment_analysis.py / 情感修正词典构建 / keyword_extract.py / topic_classification.py |
| 刘子懿 | crawl_weibo.py / crawl_bilibili.py / crawl_youtube.py 三平台爬虫全覆盖 |
| 王旭坤 | 爬虫模块配合、数据采集协助 |

---

## License

For educational purposes only.
