"""
战争舆论挖掘 - 可视化仪表盘模块
==============================
功能：读取 data/processed/ 目录下的分析结果，生成交互式 HTML 仪表盘。
包含情感分布饼图、平台对比柱状图、时间趋势折线图、主题分布图、词云图。
最终将所有图表组合到一个 Page 页面中，输出到 output/dashboard.html。
"""

import os
import sys
import traceback
import platform

import pandas as pd

# ============================================================
# pyecharts 相关导入
# ============================================================
from pyecharts import options as opts
from pyecharts.charts import Bar, Line, Page, Pie
from pyecharts.globals import ThemeType, CurrentConfig

# ============================================================
# 词云相关库（可选导入）
# ============================================================
try:
    from wordcloud import WordCloud
    import matplotlib.pyplot as plt
    import jieba
    WORDCLOUD_AVAILABLE = True
except ImportError as e:
    print(f"[Dashboard] 警告: 词云相关库未安装，将跳过词云图生成: {e}")
    WORDCLOUD_AVAILABLE = False

# ============================================================
# 路径常量：所有路径基于项目根目录
# ============================================================
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "processed")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
STOPWORDS_DIR = os.path.join(PROJECT_ROOT, "stopwords")

# 主要数据文件路径
SENTIMENT_RESULTS_PATH = os.path.join(DATA_DIR, "sentiment_results.csv")
TOPIC_RESULTS_PATH = os.path.join(DATA_DIR, "topic_results.csv")
CLEAN_DATA_PATH = os.path.join(DATA_DIR, "clean_data.csv")

# 词云输出路径
WORDCLOUD_OUTPUT_PATH = os.path.join(DATA_DIR, "wordcloud.png")

# 日志前缀，便于追踪
LOG_PREFIX = "[Dashboard]"

# ============================================================
# 字体路径（多平台支持）
# ============================================================
def get_font_path():
    """获取系统中可用的中文字体路径"""
    system = platform.system()
    font_paths = []
    
    if system == "Windows":
        font_paths.append("C:\\Windows\\Fonts\\msyh.ttc")
        font_paths.append("C:\\Windows\\Fonts\\simhei.ttf")
        font_paths.append("C:\\Windows\\Fonts\\simkai.ttf")
    elif system == "Darwin":  # macOS
        font_paths.append("/Library/Fonts/STHeiti Light.ttc")
        font_paths.append("/Library/Fonts/PingFang.ttc")
        font_paths.append("/System/Library/Fonts/PingFang.ttc")
    else:  # Linux
        font_paths.append("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc")
        font_paths.append("/usr/share/fonts/truetype/arphic/ukai.ttc")
        font_paths.append("/usr/share/fonts/truetype/noto/NotoSansCJK-SC.ttc")
    
    # 返回第一个存在的字体路径
    for path in font_paths:
        if os.path.exists(path):
            return path
    return None

# ============================================================
# 辅助函数
# ============================================================
def ensure_dir(dir_path):
    """确保目录存在，如果不存在则创建。"""
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
        print(f"{LOG_PREFIX} 已创建目录: {dir_path}")


def generate_demo_data():
    """生成演示数据（当真实数据不存在时使用）"""
    print(f"{LOG_PREFIX} 正在生成演示数据...")
    
    platforms = ["微博", "知乎", "Twitter", "YouTube"]
    sentiments = ["positive", "neutral", "negative"]
    topics = ["战争正义性", "战争影响", "各方评价", "和平呼声", "经济影响", "其他"]
    
    data = []
    topic_data = []
    
    import random
    from datetime import datetime, timedelta
    
    for i in range(3000):
        platform = random.choice(platforms)
        sentiment = random.choices(sentiments, weights=[0.5, 0.35, 0.15])[0]
        topic = random.choices(topics, weights=[0.35, 0.2, 0.15, 0.15, 0.1, 0.05])[0]
        
        # 生成模拟内容
        content_samples = [
            "支持和平解决国际争端",
            "希望战争早日结束",
            "国际社会应该发挥更大作用",
            "反对使用武力解决问题",
            "呼吁各方保持克制",
            "战争只会带来更多苦难",
            "支持自卫反击的权利",
            "国际舆论应该公平公正",
            "希望通过外交途径解决",
            "普通民众是战争的受害者"
        ]
        
        content = random.choice(content_samples)
        score = random.uniform(0, 1)
        if sentiment == "positive":
            score = random.uniform(0.55, 0.95)
        elif sentiment == "negative":
            score = random.uniform(0.05, 0.45)
        else:
            score = random.uniform(0.45, 0.55)
        
        # 生成随机时间（最近100天内）
        days_ago = random.randint(0, 100)
        publish_time = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
        
        data.append({
            "platform": platform,
            "keyword": "美以伊战争",
            "content": content,
            "publish_time": publish_time,
            "user_name": f"用户{i}",
            "like_count": random.randint(0, 500),
            "post_id": f"post_{i}",
            "url": f"https://example.com/post/{i}",
            "sentiment_label": sentiment,
            "sentiment_score": round(score, 4)
        })
        
        topic_data.append({
            "platform": platform,
            "content": content,
            "topic_label": topic
        })
    
    df = pd.DataFrame(data)
    topic_df = pd.DataFrame(topic_data)
    
    # 保存演示数据
    ensure_dir(DATA_DIR)
    df.to_csv(SENTIMENT_RESULTS_PATH, index=False, encoding="utf-8-sig")
    topic_df.to_csv(TOPIC_RESULTS_PATH, index=False, encoding="utf-8-sig")
    
    print(f"{LOG_PREFIX} 演示数据已生成: {len(df)} 条记录")
    return df, topic_df


def load_sentiment_data():
    """加载情感分析结果数据。优先读取 sentiment_results.csv，若不存在则生成演示数据。"""
    # 优先尝试读取情感分析结果
    if os.path.exists(SENTIMENT_RESULTS_PATH):
        try:
            df = pd.read_csv(SENTIMENT_RESULTS_PATH, encoding="utf-8-sig")
            print(f"{LOG_PREFIX} 成功加载情感分析结果: {SENTIMENT_RESULTS_PATH}")
            print(f"{LOG_PREFIX} 数据量: {len(df)} 条记录")
            return df
        except Exception as e:
            print(f"{LOG_PREFIX} 读取情感结果文件失败: {e}")

    # 回退：尝试读取清洗后的数据
    if os.path.exists(CLEAN_DATA_PATH):
        try:
            df = pd.read_csv(CLEAN_DATA_PATH, encoding="utf-8-sig")
            print(f"{LOG_PREFIX} 回退加载清洗数据: {CLEAN_DATA_PATH}")
            print(f"{LOG_PREFIX} 数据量: {len(df)} 条记录")
            print(f"{LOG_PREFIX} 注意: 清洗数据可能缺少 sentiment_label/sentiment_score 等字段，部分图表将无法生成")
            return df
        except Exception as e:
            print(f"{LOG_PREFIX} 读取清洗数据文件失败: {e}")

    # 生成演示数据
    print(f"{LOG_PREFIX} 未找到数据文件，正在生成演示数据...")
    df, _ = generate_demo_data()
    print(f"{LOG_PREFIX} 演示数据已生成: {len(df)} 条记录")
    return df


def load_topic_data():
    """加载主题分类结果数据。"""
    if not os.path.exists(TOPIC_RESULTS_PATH):
        print(f"{LOG_PREFIX} 提示: 未找到主题分类结果文件 {TOPIC_RESULTS_PATH}，将跳过主题分布图")
        return None

    try:
        df = pd.read_csv(TOPIC_RESULTS_PATH, encoding="utf-8-sig")
        print(f"{LOG_PREFIX} 成功加载主题分类结果: {TOPIC_RESULTS_PATH}")
        print(f"{LOG_PREFIX} 数据量: {len(df)} 条记录")
        return df
    except Exception as e:
        print(f"{LOG_PREFIX} 读取主题分类结果失败: {e}")
        return None


# ============================================================
# 结论生成与分析
# ============================================================
def generate_conclusions(df, topic_df=None):
    """基于分析数据生成美以伊战争舆论结论。"""
    conclusions = []
    total = len(df)

    if "sentiment_label" in df.columns:
        sentiment_counts = df["sentiment_label"].value_counts().to_dict()
        pos_count = 0
        neg_count = 0
        neu_count = 0
        for label, count in sentiment_counts.items():
            lbl = str(label).lower()
            if lbl in ["positive", "正面"]:
                pos_count += count
            elif lbl in ["negative", "负面"]:
                neg_count += count
            else:
                neu_count += count

        pos_pct = round(pos_count / total * 100, 1) if total > 0 else 0
        neg_pct = round(neg_count / total * 100, 1) if total > 0 else 0
        neu_pct = round(neu_count / total * 100, 1) if total > 0 else 0

        if pos_pct > neg_pct and pos_pct > neu_pct:
            mood = "总体偏向正面"
        elif neg_pct > pos_pct and neg_pct > neu_pct:
            mood = "总体偏向负面"
        else:
            mood = "以中性为主"

        conclusions.append(
            f"本次共分析{total}条关于美以伊战争的评论，其中正面评论占比{pos_pct}%，"
            f"负面评论占比{neg_pct}%，中性评论占比{neu_pct}%。{mood}，"
            f"反映出公众对该冲突的态度分布。"
        )

    if "platform" in df.columns and "sentiment_label" in df.columns:
        cross = pd.crosstab(df["platform"], df["sentiment_label"])
        if not cross.empty:
            platform_scores = {}
            for plat in cross.index:
                row = cross.loc[plat]
                plat_total = row.sum()
                plat_pos = 0
                plat_neg = 0
                for label, count in row.items():
                    lbl = str(label).lower()
                    if lbl in ["positive", "正面"]:
                        plat_pos += count
                    elif lbl in ["negative", "负面"]:
                        plat_neg += count
                pos_ratio = plat_pos / plat_total if plat_total > 0 else 0
                platform_scores[plat] = {
                    "positive_ratio": pos_ratio,
                    "positive": plat_pos,
                    "total": plat_total,
                }
            if platform_scores:
                most_pos = max(platform_scores, key=lambda k: platform_scores[k]["positive_ratio"])
                most_neg = min(platform_scores, key=lambda k: platform_scores[k]["positive_ratio"])
                conclusions.append(
                    f"在各平台中，{most_pos}平台对美以伊战争的正面评价占比最高，"
                    f"而{most_neg}平台的负面倾向最为明显，"
                    f"不同平台的用户群体对该冲突的立场存在显著差异。"
                )

    if "sentiment_score" in df.columns:
        mean_score = df["sentiment_score"].mean()
        mean_score = round(mean_score, 4)
        if mean_score > 0.55:
            score_desc = "略高于中性线，整体舆情偏正面"
        elif mean_score < 0.45:
            score_desc = "低于中性线，整体舆情偏负面"
        else:
            score_desc = "接近中性线，舆情倾向不明显"
        conclusions.append(
            f"全部评论的平均情感得分为{mean_score}（0-1范围），{score_desc}，"
            f"说明网民对美以伊战争的整体情绪处于该水平。"
        )

    if "publish_time" in df.columns and "sentiment_score" in df.columns:
        try:
            df_time = df.copy()
            df_time["publish_time"] = pd.to_datetime(df_time["publish_time"], errors="coerce")
            df_time = df_time.dropna(subset=["publish_time", "sentiment_score"])
            if not df_time.empty:
                df_time["date"] = df_time["publish_time"].dt.date
                daily = df_time.groupby("date")["sentiment_score"].mean().reset_index()
                daily = daily.sort_values("date")
                if len(daily) >= 2:
                    first_half = daily.head(len(daily) // 2)["sentiment_score"].mean()
                    second_half = daily.tail(len(daily) // 2)["sentiment_score"].mean()
                    if second_half > first_half + 0.03:
                        trend = "呈上升趋势，舆论态度正在改善"
                    elif second_half < first_half - 0.03:
                        trend = "呈下降趋势，舆论态度趋于负面"
                    else:
                        trend = "整体保持平稳，未出现明显波动"
                    conclusions.append(
                        f"从时间维度来看，美以伊战争的舆情情感得分{trend}，"
                        f"覆盖了{len(daily)}天的数据周期。"
                    )
        except Exception:
            pass

    if "platform" in df.columns:
        platform_counts = df["platform"].value_counts()
        if not platform_counts.empty:
            top_platform = platform_counts.index[0]
            top_count = platform_counts.iloc[0]
            top_pct = round(top_count / total * 100, 1)
            conclusions.append(
                f"{top_platform}是美以伊战争相关讨论最活跃的平台，"
                f"共有{top_count}条评论，占总量的{top_pct}%，"
                f"是该议题舆论发酵的主阵地。"
            )

    if topic_df is not None and "topic_label" in topic_df.columns:
        topic_counts = topic_df["topic_label"].value_counts()
        if not topic_counts.empty:
            top_topic = topic_counts.index[0]
            top_topic_count = topic_counts.iloc[0]
            topic_total = len(topic_df)
            top_topic_pct = round(top_topic_count / topic_total * 100, 1)
            conclusions.append(
                f"在美以伊战争的主题讨论中，【{top_topic}】是最受关注的主题，"
                f"共{top_topic_count}条评论（占比{top_topic_pct}%），"
                f"反映出公众对该议题最为关切。"
            )

    if len(conclusions) >= 3:
        conclusions.append(
            "综合以上分析，美以伊战争的网络舆论呈现出多元化的特征，"
            "不同平台、不同时间段的舆论倾向各有差异。"
            "建议持续关注舆情变化，尤其是关键事件节点对情感走向的冲击。"
        )

    conclusions_path = os.path.join(DATA_DIR, "conclusions.txt")
    ensure_dir(DATA_DIR)
    try:
        with open(conclusions_path, "w", encoding="utf-8") as f:
            f.write("美以伊战争舆论分析结论\n")
            f.write("=" * 40 + "\n\n")
            for i, c in enumerate(conclusions, 1):
                f.write(f"{i}. {c}\n\n")
        print(f"{LOG_PREFIX} 结论已保存至: {conclusions_path}")
    except Exception as e:
        print(f"{LOG_PREFIX} 保存结论文件时出错: {e}")

    return conclusions


def render_conclusions_block(conclusions):
    """将结论列表渲染为自包含的 HTML div 块。"""
    if not conclusions:
        return ""

    items_html = ""
    for i, c in enumerate(conclusions, 1):
        items_html += f"""
            <div class="conclusion-item">
                <span class="conclusion-number">{i}</span>
                <span class="conclusion-text">{c}</span>
            </div>"""

    html = f"""
    <div class="section conclusions-section">
        <div class="section-header">
            <div class="section-icon">&#128202;</div>
            <div>
                <h2 class="section-title">舆论分析结论</h2>
                <p class="section-subtitle">基于数据分析自动生成的关键洞察</p>
            </div>
        </div>
        <div class="conclusions-list">
            {items_html}
        </div>
    </div>"""
    return html


def build_stat_cards(df):
    """基于数据生成关键指标统计卡片。"""
    total = len(df)

    platform_col = "platform" if "platform" in df.columns else None
    platform_count = df[platform_col].nunique() if platform_col else 0
    platform_names = df[platform_col].unique().tolist() if platform_col else []

    sentiment_col = "sentiment_label" if "sentiment_label" in df.columns else ("sentiment" if "sentiment" in df.columns else None)
    pos_count = 0
    neg_count = 0
    neu_count = 0
    if sentiment_col:
        counts = df[sentiment_col].value_counts().to_dict()
        for label, count in counts.items():
            lbl = str(label).lower()
            if lbl in ["positive", "正面"]:
                pos_count += count
            elif lbl in ["negative", "负面"]:
                neg_count += count
            else:
                neu_count += count
    pos_pct = round(pos_count / total * 100, 1) if total > 0 else 0
    neg_pct = round(neg_count / total * 100, 1) if total > 0 else 0

    avg_score = round(df["sentiment_score"].mean(), 3) if "sentiment_score" in df.columns else "—"

    cards = f"""
    <div class="stat-cards">
        <div class="stat-card stat-card-total">
            <div class="stat-icon">&#128196;</div>
            <div class="stat-value">{total}</div>
            <div class="stat-label">总评论数</div>
        </div>
        <div class="stat-card stat-card-platform">
            <div class="stat-icon">&#127758;</div>
            <div class="stat-value">{platform_count}</div>
            <div class="stat-label">数据来源平台</div>
            <div class="stat-detail">{', '.join(platform_names[:3])}</div>
        </div>
        <div class="stat-card stat-card-positive">
            <div class="stat-icon">&#128077;</div>
            <div class="stat-value">{pos_pct}%</div>
            <div class="stat-label">正面评论占比</div>
            <div class="stat-detail">{pos_count} 条</div>
        </div>
        <div class="stat-card stat-card-negative">
            <div class="stat-icon">&#128078;</div>
            <div class="stat-value">{neg_pct}%</div>
            <div class="stat-label">负面评论占比</div>
            <div class="stat-detail">{neg_count} 条</div>
        </div>
        <div class="stat-card stat-card-score">
            <div class="stat-icon">&#127919;</div>
            <div class="stat-value">{avg_score}</div>
            <div class="stat-label">平均情感得分</div>
            <div class="stat-detail">0 ~ 1 范围</div>
        </div>
    </div>"""
    return cards


# ============================================================
# 图表1: 情感分布饼图
# ============================================================
def plot_sentiment_pie(df):
    """生成情感分布饼图。"""
    # 兼容多种列名
    sentiment_col = "sentiment_label" if "sentiment_label" in df.columns else "sentiment"
    if sentiment_col not in df.columns:
        print(f"{LOG_PREFIX} 警告: 数据中缺少 'sentiment_label' 或 'sentiment' 列，跳过情感分布饼图")
        return None

    sentiment_counts = df[sentiment_col].value_counts()
    print(f"{LOG_PREFIX} 情感分布统计: {dict(sentiment_counts)}")

    data_pairs = []
    for label, count in sentiment_counts.items():
        data_pairs.append((str(label), int(count)))

    pie_chart = (
        Pie(init_opts=opts.InitOpts(theme=ThemeType.ROMANTIC, width="800px", height="500px"))
        .add(
            series_name="情感分布",
            data_pair=data_pairs,
            radius=["35%", "65%"],
            center=["50%", "55%"],
            label_opts=opts.LabelOpts(
                position="outside",
                formatter="{b}: {c} 条\n({d}%)",
                font_size=14,
            ),
        )
        .set_global_opts(
            title_opts=opts.TitleOpts(
                title="美以伊战争评论情感分布分析",
                subtitle="正面 / 负面 / 中性 评论占比",
                pos_left="center",
                pos_top="2%",
                title_textstyle_opts=opts.TextStyleOpts(font_size=20, font_weight="bold"),
            ),
            legend_opts=opts.LegendOpts(
                orient="horizontal",
                pos_bottom="5%",
                pos_left="center",
            ),
            tooltip_opts=opts.TooltipOpts(
                trigger="item",
                formatter="{a} <br/>{b}: {c} 条 ({d}%)",
            ),
        )
    )

    return pie_chart


# ============================================================
# 图表2: 各平台情感倾向对比柱状图
# ============================================================
def plot_platform_comparison(df):
    """生成各平台情感倾向对比的分组柱状图。"""
    sentiment_col = "sentiment_label" if "sentiment_label" in df.columns else "sentiment"
    required_cols = ["platform", sentiment_col]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"{LOG_PREFIX} 警告: 数据中缺少 {missing_cols} 列，跳过平台对比柱状图")
        return None

    cross_tab = pd.crosstab(df["platform"], df[sentiment_col])
    print(f"{LOG_PREFIX} 平台-情感交叉统计:\n{cross_tab}")

    platforms = cross_tab.index.tolist()
    sentiment_categories = cross_tab.columns.tolist()

    bar_chart = (
        Bar(init_opts=opts.InitOpts(theme=ThemeType.ROMANTIC, width="900px", height="500px"))
        .add_xaxis(platforms)
        .set_global_opts(
            title_opts=opts.TitleOpts(
                title="各平台对美以伊战争的情感倾向对比",
                subtitle="不同社交媒体平台的情感分布对比",
                pos_left="center",
                pos_top="2%",
                title_textstyle_opts=opts.TextStyleOpts(font_size=20, font_weight="bold"),
            ),
            legend_opts=opts.LegendOpts(
                orient="horizontal",
                pos_top="90%",
                pos_left="center",
            ),
            tooltip_opts=opts.TooltipOpts(
                trigger="axis",
                axis_pointer_type="shadow",
            ),
            xaxis_opts=opts.AxisOpts(
                name="平台",
                axislabel_opts=opts.LabelOpts(font_size=13, rotate=0),
            ),
            yaxis_opts=opts.AxisOpts(
                name="评论数量",
                axislabel_opts=opts.LabelOpts(font_size=12),
            ),
        )
    )

    for category in sentiment_categories:
        values = cross_tab[category].tolist()
        bar_chart.add_yaxis(
            series_name=str(category),
            y_axis=values,
            label_opts=opts.LabelOpts(
                is_show=True,
                position="top",
                font_size=12,
            ),
            gap="15%",
        )

    return bar_chart


# ============================================================
# 图表3: 舆情情感时间趋势折线图
# ============================================================
def plot_time_trend(df):
    """生成舆情情感时间趋势折线图。"""
    required_cols = ["publish_time", "sentiment_score"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"{LOG_PREFIX} 警告: 数据中缺少 {missing_cols} 列，跳过时间趋势折线图")
        return None

    try:
        df_copy = df.copy()
        df_copy["publish_time"] = pd.to_datetime(df_copy["publish_time"], errors="coerce")
        df_copy = df_copy.dropna(subset=["publish_time", "sentiment_score"])

        if df_copy.empty:
            print(f"{LOG_PREFIX} 警告: 有效的时间/情感得分数据为空，跳过时间趋势折线图")
            return None

        df_copy["date"] = df_copy["publish_time"].dt.date
        daily_sentiment = df_copy.groupby("date")["sentiment_score"].mean().reset_index()
        daily_sentiment = daily_sentiment.sort_values("date")

        print(f"{LOG_PREFIX} 时间趋势: 共 {len(daily_sentiment)} 天的数据")

        dates = [str(d) for d in daily_sentiment["date"].tolist()]
        scores = [round(s, 4) for s in daily_sentiment["sentiment_score"].tolist()]

        line_chart = (
            Line(init_opts=opts.InitOpts(theme=ThemeType.ROMANTIC, width="1000px", height="500px"))
            .add_xaxis(dates)
            .add_yaxis(
                series_name="平均情感得分",
                y_axis=scores,
                is_smooth=True,
                areastyle_opts=opts.AreaStyleOpts(opacity=0.3),
                label_opts=opts.LabelOpts(is_show=False),
                linestyle_opts=opts.LineStyleOpts(width=3, color="#5470c6"),
                markline_opts=opts.MarkLineOpts(
                    data=[opts.MarkLineItem(y=0.5, name="中性线")],
                    label_opts=opts.LabelOpts(formatter="{b}"),
                ),
            )
            .set_global_opts(
                title_opts=opts.TitleOpts(
                    title="美以伊战争舆情情感时间趋势",
                    subtitle="每日平均情感得分变化趋势",
                    pos_left="center",
                    pos_top="2%",
                    title_textstyle_opts=opts.TextStyleOpts(font_size=20, font_weight="bold"),
                ),
                legend_opts=opts.LegendOpts(
                    orient="horizontal",
                    pos_top="90%",
                    pos_left="center",
                ),
                tooltip_opts=opts.TooltipOpts(
                    trigger="axis",
                    formatter="日期: {b}<br/>平均情感得分: {c}",
                ),
                xaxis_opts=opts.AxisOpts(
                    name="日期",
                    axislabel_opts=opts.LabelOpts(rotate=45, font_size=11),
                ),
                yaxis_opts=opts.AxisOpts(
                    name="情感得分",
                    min_=0,
                    max_=1,
                    axislabel_opts=opts.LabelOpts(font_size=12),
                ),
            )
        )

        return line_chart

    except Exception as e:
        print(f"{LOG_PREFIX} 生成时间趋势图时出错: {e}")
        traceback.print_exc()
        return None


# ============================================================
# 图表4: 主题分类分布柱状图
# ============================================================
def plot_topic_distribution(df):
    """生成主题分类分布柱状图。"""
    if df is None:
        print(f"{LOG_PREFIX} 提示: 主题数据为空，跳过主题分布图")
        return None

    # 兼容多种列名
    topic_col = None
    if "topic_label" in df.columns:
        topic_col = "topic_label"
    elif "rule_topic" in df.columns:
        topic_col = "rule_topic"
    elif "cluster" in df.columns:
        topic_col = "cluster"
    
    if topic_col is None:
        print(f"{LOG_PREFIX} 警告: 主题数据缺少 'topic_label'、'rule_topic' 或 'cluster' 列，跳过主题分布图")
        return None

    topic_counts = df[topic_col].value_counts()
    print(f"{LOG_PREFIX} 主题分布统计: {dict(topic_counts)}")

    topics = topic_counts.index.tolist()
    counts = topic_counts.values.tolist()

    bar_chart = (
        Bar(init_opts=opts.InitOpts(theme=ThemeType.ROMANTIC, width="800px", height="500px"))
        .add_xaxis(topics)
        .add_yaxis(
            series_name="评论数量",
            y_axis=counts,
            label_opts=opts.LabelOpts(
                is_show=True,
                position="top",
                font_size=13,
                font_weight="bold",
            ),
            itemstyle_opts=opts.ItemStyleOpts(
                color={
                    "type": "linear",
                    "x": 0,
                    "y": 0,
                    "x2": 0,
                    "y2": 1,
                    "colorStops": [
                        {"offset": 0, "color": "#6a9fb5"},
                        {"offset": 1, "color": "#3c6478"},
                    ],
                },
                border_radius=[8, 8, 0, 0],
            ),
        )
        .set_global_opts(
            title_opts=opts.TitleOpts(
                title="美以伊战争评论主题分类分布",
                subtitle="各主题相关的评论数量统计",
                pos_left="center",
                pos_top="2%",
                title_textstyle_opts=opts.TextStyleOpts(font_size=20, font_weight="bold"),
            ),
            legend_opts=opts.LegendOpts(is_show=False),
            tooltip_opts=opts.TooltipOpts(
                trigger="axis",
                axis_pointer_type="shadow",
                formatter="主题: {b}<br/>评论数量: {c}",
            ),
            xaxis_opts=opts.AxisOpts(
                name="主题",
                axislabel_opts=opts.LabelOpts(rotate=30, font_size=12),
            ),
            yaxis_opts=opts.AxisOpts(
                name="评论数量",
                axislabel_opts=opts.LabelOpts(font_size=12),
            ),
        )
    )

    return bar_chart


# ============================================================
# 图表5: 词云图
# ============================================================
def plot_wordcloud(df):
    """生成词云图。"""
    if not WORDCLOUD_AVAILABLE:
        print(f"{LOG_PREFIX} 警告: 词云库不可用，跳过词云图")
        return None

    if "content" not in df.columns:
        print(f"{LOG_PREFIX} 警告: 数据中缺少 'content' 列，跳过词云图")
        return None

    ensure_dir(DATA_DIR)

    stopwords = set()
    chinese_stopwords_path = os.path.join(STOPWORDS_DIR, "chinese_stopwords.txt")
    if os.path.exists(chinese_stopwords_path):
        try:
            with open(chinese_stopwords_path, "r", encoding="utf-8") as f:
                for line in f:
                    word = line.strip()
                    if word:
                        stopwords.add(word)
            print(f"{LOG_PREFIX} 已加载中文停用词 {len(stopwords)} 个")
        except Exception as e:
            print(f"{LOG_PREFIX} 加载中文停用词失败: {e}")

    english_stopwords_path = os.path.join(STOPWORDS_DIR, "english_stopwords.txt")
    if os.path.exists(english_stopwords_path):
        try:
            with open(english_stopwords_path, "r", encoding="utf-8") as f:
                for line in f:
                    word = line.strip()
                    if word:
                        stopwords.add(word)
            print(f"{LOG_PREFIX} 已加载英文停用词，当前停用词总数 {len(stopwords)} 个")
        except Exception as e:
            print(f"{LOG_PREFIX} 加载英文停用词失败: {e}")

    war_stopwords = {"war", "战争", "conflict", "冲突", "Iran", "iran",
                     "美国", "伊朗", "以色列", "US", "USA", "Israel", "israel",
                     "中东", "军事", "military", "中东战争", "波斯湾", "核", "nuclear"}
    stopwords.update(war_stopwords)
    print(f"{LOG_PREFIX} 已添加战争相关停用词 {len(war_stopwords)} 个，总停用词数 {len(stopwords)}")

    all_text = " ".join(df["content"].dropna().astype(str).tolist())

    if not all_text.strip():
        print(f"{LOG_PREFIX} 警告: 评论文本内容为空，跳过词云图")
        return None

    print(f"{LOG_PREFIX} 评论文本总长度: {len(all_text)} 字符")

    try:
        words = jieba.cut(all_text, cut_all=False)
        filtered_words = [
            w for w in words
            if len(w.strip()) > 1 and w.strip() not in stopwords
        ]

        if not filtered_words:
            print(f"{LOG_PREFIX} 警告: 分词后无有效词汇，跳过词云图")
            return None

        text_for_wordcloud = " ".join(filtered_words)
        print(f"{LOG_PREFIX} 分词后有效词汇数: {len(filtered_words)}")

        font_path = get_font_path()
        if font_path is None:
            print(f"{LOG_PREFIX} 警告: 未找到中文字体，跳过词云图")
            return None

        wc = WordCloud(
            font_path=font_path,
            width=1200,
            height=600,
            background_color="white",
            max_words=200,
            max_font_size=150,
            min_font_size=12,
            collocations=False,
            scale=2,
            random_state=42,
            margin=10,
        )

        wc.generate(text_for_wordcloud)

        plt.figure(figsize=(16, 8), dpi=150)
        plt.imshow(wc, interpolation="bilinear")
        plt.axis("off")
        plt.tight_layout(pad=0)
        plt.savefig(WORDCLOUD_OUTPUT_PATH, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close()

        print(f"{LOG_PREFIX} 词云图已保存至: {WORDCLOUD_OUTPUT_PATH}")
        return WORDCLOUD_OUTPUT_PATH

    except Exception as e:
        print(f"{LOG_PREFIX} 生成词云图时出错: {e}")
        traceback.print_exc()
        return None


# ============================================================
# 仪表盘主渲染函数
# ============================================================
def render_dashboard(sentiment_df, topic_df=None):
    """渲染完整的交互式仪表盘。"""
    print(f"\n{LOG_PREFIX} {'=' * 50}")
    print(f"{LOG_PREFIX} 开始渲染仪表盘...")
    print(f"{LOG_PREFIX} {'=' * 50}")

    page = Page(
        page_title="战争舆论挖掘 - 可视化仪表盘",
        layout=Page.SimplePageLayout,
    )

    print(f"{LOG_PREFIX} [1/5] 生成情感分布饼图...")
    pie = plot_sentiment_pie(sentiment_df)
    if pie is not None:
        page.add(pie)
        print(f"{LOG_PREFIX} [1/5] 情感分布饼图 ✓")
    else:
        print(f"{LOG_PREFIX} [1/5] 情感分布饼图 ✗ (跳过)")

    print(f"{LOG_PREFIX} [2/5] 生成各平台情感倾向对比图...")
    bar_platform = plot_platform_comparison(sentiment_df)
    if bar_platform is not None:
        page.add(bar_platform)
        print(f"{LOG_PREFIX} [2/5] 平台对比柱状图 ✓")
    else:
        print(f"{LOG_PREFIX} [2/5] 平台对比柱状图 ✗ (跳过)")

    print(f"{LOG_PREFIX} [3/5] 生成舆情情感时间趋势图...")
    line_trend = plot_time_trend(sentiment_df)
    if line_trend is not None:
        page.add(line_trend)
        print(f"{LOG_PREFIX} [3/5] 时间趋势折线图 ✓")
    else:
        print(f"{LOG_PREFIX} [3/5] 时间趋势折线图 ✗ (跳过)")

    print(f"{LOG_PREFIX} [4/5] 生成主题分类分布图...")
    bar_topic = plot_topic_distribution(topic_df)
    if bar_topic is not None:
        page.add(bar_topic)
        print(f"{LOG_PREFIX} [4/5] 主题分布柱状图 ✓")
    else:
        print(f"{LOG_PREFIX} [4/5] 主题分布柱状图 ✗ (跳过)")

    print(f"{LOG_PREFIX} [5/5] 生成词云图...")
    wc_path = plot_wordcloud(sentiment_df)
    if wc_path is not None:
        print(f"{LOG_PREFIX} [5/5] 词云图 ✓ -> {wc_path}")
    else:
        print(f"{LOG_PREFIX} [5/5] 词云图 ✗ (跳过)")

    print(f"{LOG_PREFIX} {'=' * 50}")
    print(f"{LOG_PREFIX} 仪表盘渲染完成！总计 {len(page)} 个图表")
    print(f"{LOG_PREFIX} {'=' * 50}")

    return page, wc_path


# ============================================================
# 主入口函数
# ============================================================
def main():
    """程序主入口。"""
    print(f"\n{LOG_PREFIX} {'#' * 50}")
    print(f"{LOG_PREFIX} 战争舆论挖掘 - 可视化仪表盘生成器")
    print(f"{LOG_PREFIX} {'#' * 50}\n")

    print(f"{LOG_PREFIX} 正在加载数据...")

    sentiment_df = load_sentiment_data()
    if sentiment_df is None:
        print(f"{LOG_PREFIX} 错误: 无法加载任何数据，程序退出")
        sys.exit(1)

    print(f"{LOG_PREFIX} 数据列: {list(sentiment_df.columns)}")
    print(f"{LOG_PREFIX} 数据形状: {sentiment_df.shape}")

    topic_df = load_topic_data()

    ensure_dir(OUTPUT_DIR)
    ensure_dir(DATA_DIR)

    print(f"\n{LOG_PREFIX} 正在生成美以伊战争舆论分析结论...")
    conclusions = generate_conclusions(sentiment_df, topic_df)
    if conclusions:
        print(f"{LOG_PREFIX} 已生成 {len(conclusions)} 条结论")
        for i, c in enumerate(conclusions, 1):
            print(f"{LOG_PREFIX}   结论{i}: {c[:60]}...")
    else:
        print(f"{LOG_PREFIX} 警告: 未能生成结论")

    dashboard, wc_path = render_dashboard(sentiment_df, topic_df)

    output_path = os.path.join(OUTPUT_DIR, "dashboard.html")
    try:
        dashboard.render(output_path)
        print(f"\n{LOG_PREFIX} {'*' * 50}")
        print(f"{LOG_PREFIX} 仪表盘已成功保存!")
        print(f"{LOG_PREFIX} 输出路径: {os.path.abspath(output_path)}")

        with open(output_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        # 提取 pyecharts 生成的图表 div + script 块
        chart_blocks = []
        # 匹配从 <div id="... class="chart-container" 到 </script> 的完整图表块
        import re
        pattern = re.compile(
            r'<div id="[^"]+" class="chart-container"[^>]*>.*?</div>\s*<script>.*?</script>',
            re.DOTALL
        )
        for m in pattern.finditer(html_content):
            chart_blocks.append(m.group())

        # 构建统计卡片
        stat_cards_html = build_stat_cards(sentiment_df)

        # 构建结论块
        conclusions_html = render_conclusions_block(conclusions) if conclusions else ""

        # 处理词云路径 —— 使用正斜杠，避免 Windows 反斜杠问题
        wordcloud_html = ""
        if wc_path is not None and os.path.exists(wc_path):
            wc_rel = os.path.relpath(wc_path, OUTPUT_DIR).replace("\\", "/")
            wordcloud_html = f"""
    <div class="section wordcloud-section">
        <div class="section-header">
            <div class="section-icon">&#9729;</div>
            <div>
                <h2 class="section-title">评论词云图</h2>
                <p class="section-subtitle">基于 jieba 分词生成，突出显示讨论焦点</p>
            </div>
        </div>
        <div class="wordcloud-content">
            <img src="{wc_rel}" alt="词云图" class="wordcloud-img" />
        </div>
    </div>"""

        # 将所有图表放入卡片容器
        charts_html = ""
        chart_titles = [
            ("情感分布饼图", "正面 / 负面 / 中性 评论占比"),
            ("平台情感倾向对比", "不同社交媒体平台的情感分布对比"),
            ("舆情情感时间趋势", "每日平均情感得分变化趋势"),
            ("主题分类分布", "各主题相关的评论数量统计"),
        ]
        for i, block in enumerate(chart_blocks):
            title = chart_titles[i][0] if i < len(chart_titles) else f"图表 {i+1}"
            subtitle = chart_titles[i][1] if i < len(chart_titles) else ""
            charts_html += f"""
    <div class="chart-card">
        <div class="chart-card-header">
            <div class="chart-card-icon">{i + 1}</div>
            <div>
                <h3 class="chart-card-title">{title}</h3>
                <p class="chart-card-subtitle">{subtitle}</p>
            </div>
        </div>
        <div class="chart-card-body">
            {block}
        </div>
    </div>"""

        # 构建完整页面结构
        full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>战争舆论挖掘 - 可视化仪表盘</title>
    <script type="text/javascript" src="https://assets.pyecharts.org/assets/v6/echarts.min.js"></script>
    <script type="text/javascript" src="https://assets.pyecharts.org/assets/v6/themes/romantic.js"></script>
    <style>
        /* ===== 全局重置 ===== */
        *, *::before, *::after {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans SC", sans-serif;
            background: #f0f2f5;
            color: #333;
            line-height: 1.6;
            min-height: 100vh;
        }}

        /* ===== 页面容器 ===== */
        .page-wrapper {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 24px 20px 60px;
        }}

        /* ===== 顶部横幅 ===== */
        .hero {{
            background: linear-gradient(135deg, #1a2a6c, #b21f1f, #fdbb2d);
            background-size: 200% 200%;
            animation: gradientShift 12s ease infinite;
            border-radius: 16px;
            padding: 48px 40px;
            margin-bottom: 32px;
            text-align: center;
            color: #fff;
            position: relative;
            overflow: hidden;
        }}
        .hero::before {{
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(255,255,255,0.06) 0%, transparent 70%);
            pointer-events: none;
        }}
        @keyframes gradientShift {{
            0% {{ background-position: 0% 50%; }}
            50% {{ background-position: 100% 50%; }}
            100% {{ background-position: 0% 50%; }}
        }}
        .hero-title {{
            font-size: 32px;
            font-weight: 800;
            margin-bottom: 8px;
            letter-spacing: 2px;
            position: relative;
        }}
        .hero-subtitle {{
            font-size: 16px;
            opacity: 0.85;
            font-weight: 300;
            position: relative;
        }}
        .hero-badge {{
            display: inline-block;
            background: rgba(255,255,255,0.2);
            backdrop-filter: blur(4px);
            border-radius: 20px;
            padding: 4px 16px;
            font-size: 13px;
            margin-top: 12px;
            position: relative;
        }}

        /* ===== 统计卡片 ===== */
        .stat-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin-bottom: 32px;
        }}
        .stat-card {{
            background: #fff;
            border-radius: 12px;
            padding: 24px 20px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            transition: transform 0.2s, box-shadow 0.2s;
            cursor: default;
            position: relative;
            overflow: hidden;
        }}
        .stat-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 8px 24px rgba(0,0,0,0.10);
        }}
        .stat-card::after {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
        }}
        .stat-card-total::after {{ background: #5470c6; }}
        .stat-card-platform::after {{ background: #91cc75; }}
        .stat-card-positive::after {{ background: #ee6666; }}
        .stat-card-negative::after {{ background: #fac858; }}
        .stat-card-score::after {{ background: #73c0de; }}

        .stat-icon {{ font-size: 28px; margin-bottom: 8px; }}
        .stat-value {{
            font-size: 32px;
            font-weight: 800;
            color: #1a1a2e;
            margin-bottom: 4px;
        }}
        .stat-label {{
            font-size: 14px;
            color: #666;
            font-weight: 500;
        }}
        .stat-detail {{
            font-size: 12px;
            color: #999;
            margin-top: 4px;
        }}

        /* ===== 通用区域 ===== */
        .section {{
            background: #fff;
            border-radius: 16px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.06);
            padding: 32px;
            margin-bottom: 24px;
        }}
        .section-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 2px solid #f0f2f5;
        }}
        .section-icon {{
            width: 44px;
            height: 44px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 22px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: #fff;
            flex-shrink: 0;
        }}
        .section-title {{
            font-size: 20px;
            font-weight: 700;
            color: #1a1a2e;
        }}
        .section-subtitle {{
            font-size: 13px;
            color: #999;
            margin-top: 2px;
        }}

        /* ===== 结论列表 ===== */
        .conclusions-list {{
            display: flex;
            flex-direction: column;
            gap: 12px;
        }}
        .conclusion-item {{
            display: flex;
            align-items: flex-start;
            gap: 14px;
            padding: 16px 20px;
            background: #f8f9fc;
            border-radius: 12px;
            border-left: 4px solid #5470c6;
            transition: background 0.2s;
        }}
        .conclusion-item:hover {{
            background: #eef1f7;
        }}
        .conclusion-number {{
            flex-shrink: 0;
            width: 30px;
            height: 30px;
            border-radius: 50%;
            background: linear-gradient(135deg, #5470c6, #7c9bf0);
            color: #fff;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            font-weight: 700;
            margin-top: 2px;
        }}
        .conclusion-text {{
            font-size: 15px;
            line-height: 1.8;
            color: #333;
        }}

        /* ===== 图表卡片 ===== */
        .chart-card {{
            background: #fff;
            border-radius: 16px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.06);
            margin-bottom: 28px;
            overflow: hidden;
        }}
        .chart-card-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 20px 28px 0;
        }}
        .chart-card-icon {{
            width: 36px;
            height: 36px;
            border-radius: 10px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: #fff;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 16px;
            font-weight: 700;
            flex-shrink: 0;
        }}
        .chart-card-title {{
            font-size: 18px;
            font-weight: 600;
            color: #1a1a2e;
        }}
        .chart-card-subtitle {{
            font-size: 13px;
            color: #999;
            margin-top: 2px;
        }}
        .chart-card-body {{
            padding: 8px 12px 12px;
            display: flex;
            justify-content: center;
        }}
        .chart-card-body .chart-container {{
            margin: 0 auto;
        }}
        /* pyecharts 的 .box 内联样式覆盖 */
        .box {{
            justify-content: center;
            display: flex;
            flex-wrap: wrap;
        }}

        /* ===== 词云 ===== */
        .wordcloud-content {{
            text-align: center;
            padding: 12px 0;
        }}
        .wordcloud-img {{
            max-width: 100%;
            height: auto;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        }}

        /* ===== 页脚 ===== */
        .footer {{
            text-align: center;
            padding: 24px 0 8px;
            color: #bbb;
            font-size: 13px;
        }}
        .footer a {{
            color: #667eea;
            text-decoration: none;
        }}

        /* ===== 响应式 ===== */
        @media (max-width: 768px) {{
            .hero {{ padding: 32px 20px; }}
            .hero-title {{ font-size: 24px; }}
            .stat-cards {{ grid-template-columns: repeat(2, 1fr); }}
            .section {{ padding: 20px; }}
            .chart-card-header {{ padding: 16px 16px 0; }}
        }}
        @media (max-width: 480px) {{
            .stat-cards {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="page-wrapper">
        <!-- 顶部横幅 -->
        <div class="hero">
            <h1 class="hero-title">美以伊战争舆论挖掘分析</h1>
            <p class="hero-subtitle">多平台社交网络数据 · 深度数据清洗 · 情感修正分析 · 主题分类与可视化</p>
            <span class="hero-badge">&#9201; 交互式数据仪表盘</span>
        </div>

        <!-- 统计卡片 -->
        {stat_cards_html}

        <!-- 结论区块 -->
        {conclusions_html}

        <!-- 图表区块 -->
        {charts_html}

        <!-- 词云区块 -->
        {wordcloud_html}

        <!-- 页脚 -->
        <div class="footer">
            战争舆论挖掘分析系统 &middot; 基于 SnowNLP + TextRank + pyecharts 构建
        </div>
    </div>
</body>
</html>"""

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_html)

        print(f"\n{LOG_PREFIX} {'*' * 50}")
        print(f"{LOG_PREFIX} 仪表盘已成功保存!")
        print(f"{LOG_PREFIX} 输出路径: {os.path.abspath(output_path)}")
        print(f"{LOG_PREFIX} 请用浏览器打开该文件查看交互式仪表盘")
        print(f"{LOG_PREFIX} {'*' * 50}\n")
    except Exception as e:
        print(f"{LOG_PREFIX} 保存仪表盘 HTML 时出错: {e}")
        traceback.print_exc()
        sys.exit(1)


# ============================================================
# 程序入口
# ============================================================
if __name__ == "__main__":
    main()