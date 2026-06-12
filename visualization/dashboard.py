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

import pandas as pd

# ============================================================
# pyecharts 相关导入
# ============================================================
from pyecharts import options as opts
from pyecharts.charts import Bar, Line, Page, Pie
from pyecharts.globals import ThemeType, CurrentConfig

# ============================================================
# 词云相关库
# ============================================================
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import jieba

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
# 词云 HTML 片段输出路径
WORDCLOUD_HTML_PATH = os.path.join(OUTPUT_DIR, "wordcloud.html")

# 日志前缀，便于追踪
LOG_PREFIX = "[Dashboard]"


def ensure_dir(dir_path):
    """
    确保目录存在，如果不存在则创建。

    Args:
        dir_path: 目标目录的绝对路径
    """
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
        print(f"{LOG_PREFIX} 已创建目录: {dir_path}")


def load_sentiment_data():
    """
    加载情感分析结果数据。
    优先读取 sentiment_results.csv，若不存在则回退到 clean_data.csv。

    Returns:
        pd.DataFrame: 情感分析数据，如果没有任何数据则返回 None
    """
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
            print(f"{LOG_PREFIX} 注意: 清洗数据可能缺少 sentiment_label/sentiment_score 等字段，"
                  f"部分图表将无法生成")
            return df
        except Exception as e:
            print(f"{LOG_PREFIX} 读取清洗数据文件失败: {e}")

    # 两个文件都不存在
    print(f"{LOG_PREFIX} 错误: 未找到任何可用的数据文件")
    print(f"{LOG_PREFIX}   期望路径1: {SENTIMENT_RESULTS_PATH}")
    print(f"{LOG_PREFIX}   期望路径2: {CLEAN_DATA_PATH}")
    return None


def load_topic_data():
    """
    加载主题分类结果数据。

    Returns:
        pd.DataFrame 或 None: 主题分类数据
    """
    if not os.path.exists(TOPIC_RESULTS_PATH):
        print(f"{LOG_PREFIX} 提示: 未找到主题分类结果文件 {TOPIC_RESULTS_PATH}，"
              f"将跳过主题分布图")
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
    """
    基于分析数据生成美以伊战争舆论结论。
    分析情感分布、平台对比、主题讨论、时间趋势等多个维度，
    生成5-7条数据驱动的中文结论。

    Args:
        df:       情感分析主数据 DataFrame，需包含 sentiment_label、sentiment_score 等列
        topic_df: 主题分类数据 DataFrame（可选）

    Returns:
        list[str]: 结论字符串列表
    """
    conclusions = []
    total = len(df)

    # ---------- 结论1: 整体情感分布 ----------
    if "sentiment_label" in df.columns:
        sentiment_counts = df["sentiment_label"].value_counts().to_dict()
        # 统一标签名称（兼容中英文）
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

        # 判断舆论倾向
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

    # ---------- 结论2: 平台情感倾向对比 ----------
    if "platform" in df.columns and "sentiment_label" in df.columns:
        cross = pd.crosstab(df["platform"], df["sentiment_label"])
        if not cross.empty:
            # 计算每个平台的正面占比
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

    # ---------- 结论3: 情感得分均值 ----------
    if "sentiment_score" in df.columns:
        mean_score = df["sentiment_score"].mean()
        mean_score = round(mean_score, 4)
        # 得分范围假设为0-1，0.5为中性线
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

    # ---------- 结论4: 时间趋势 ----------
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
            pass  # 时间分析失败不影响其他结论

    # ---------- 结论5: 评论数量最多的平台 ----------
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

    # ---------- 结论6: 主题分布（如果可用） ----------
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

    # ---------- 结论7: 综合总结 ----------
    if len(conclusions) >= 3:
        conclusions.append(
            "综合以上分析，美以伊战争的网络舆论呈现出多元化的特征，"
            "不同平台、不同时间段的舆论倾向各有差异。"
            "建议持续关注舆情变化，尤其是关键事件节点对情感走向的冲击。"
        )

    # 保存结论到文件
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
    """
    将结论列表渲染为自包含的 HTML div 块，用于嵌入仪表盘页面。

    Args:
        conclusions: 结论字符串列表

    Returns:
        str: HTML 格式的结论展示块
    """
    if not conclusions:
        return ""

    items_html = ""
    for i, c in enumerate(conclusions, 1):
        items_html += f"""
            <div style="display:flex;align-items:flex-start;margin-bottom:14px;
                        padding:12px 16px;background:#f8f9fa;border-radius:8px;
                        border-left:4px solid #5470c6;">
                <span style="flex-shrink:0;display:inline-flex;align-items:center;
                             justify-content:center;width:28px;height:28px;
                             background:#5470c6;color:#fff;border-radius:50%;
                             font-size:14px;font-weight:bold;margin-right:14px;
                             margin-top:2px;">{i}</span>
                <span style="font-size:15px;line-height:1.8;color:#333;">{c}</span>
            </div>"""

    html = f"""
    <div style="max-width:1100px;margin:20px auto 40px auto;padding:0 20px;">
        <div style="background:#ffffff;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,0.08);
                    padding:30px 36px;">
            <h2 style="font-size:22px;font-weight:bold;color:#333;margin:0 0 8px 0;
                       text-align:center;">
                📊 美以伊战争舆论分析结论
            </h2>
            <p style="text-align:center;color:#888;font-size:13px;margin:0 0 24px 0;">
                基于数据分析自动生成的关键结论
            </p>
            {items_html}
        </div>
    </div>"""
    return html


# ============================================================
# 图表1: 情感分布饼图
# ============================================================
def plot_sentiment_pie(df):
    """
    生成情感分布饼图。
    展示正面/负面/中性三类情感的占比分布。

    Args:
        df: 包含 'sentiment_label' 列的 DataFrame

    Returns:
        Pie 图表对象，如果数据不满足要求则返回 None
    """
    # 检查必需的列是否存在
    if "sentiment_label" not in df.columns:
        print(f"{LOG_PREFIX} 警告: 数据中缺少 'sentiment_label' 列，跳过情感分布饼图")
        return None

    # 统计各类情感的数量
    sentiment_counts = df["sentiment_label"].value_counts()
    print(f"{LOG_PREFIX} 情感分布统计: {dict(sentiment_counts)}")

    # 定义情感标签与颜色的映射
    # 正面 -> 绿色, 负面 -> 红色, 中性 -> 灰色
    label_color_map = {
        "positive": "green",
        "负面": "red",
        "negative": "red",
        "正面": "green",
        "中性": "gray",
        "neutral": "gray",
    }

    # 构建饼图数据对列表: [(标签, 数量), ...]
    data_pairs = []
    for label, count in sentiment_counts.items():
        data_pairs.append((str(label), int(count)))

    # 创建饼图
    pie_chart = (
        Pie(init_opts=opts.InitOpts(theme=ThemeType.ROMANTIC, width="800px", height="500px"))
        .add(
            series_name="情感分布",
            data_pair=data_pairs,
            radius=["35%", "65%"],  # 环形饼图，内径35%，外径65%
            center=["50%", "55%"],  # 圆心位置
            label_opts=opts.LabelOpts(
                position="outside",
                formatter="{b}: {c} 条\n({d}%)",  # 标签格式: 名称: 数量 (百分比)
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
        .set_series_opts(
            # 手动设置每块的颜色
            itemstyle_opts=opts.ItemStyleOpts(),
        )
    )

    return pie_chart


# ============================================================
# 图表2: 各平台情感倾向对比柱状图
# ============================================================
def plot_platform_comparison(df):
    """
    生成各平台情感倾向对比的分组柱状图。
    X 轴为平台名称，Y 轴为评论数量，按情感标签分组。

    Args:
        df: 包含 'platform' 和 'sentiment_label' 列的 DataFrame

    Returns:
        Bar 图表对象，如果数据不满足要求则返回 None
    """
    # 检查必需的列
    required_cols = ["platform", "sentiment_label"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"{LOG_PREFIX} 警告: 数据中缺少 {missing_cols} 列，跳过平台对比柱状图")
        return None

    # 构建交叉统计表: 行=平台, 列=情感标签, 值=数量
    cross_tab = pd.crosstab(df["platform"], df["sentiment_label"])
    print(f"{LOG_PREFIX} 平台-情感交叉统计:\n{cross_tab}")

    # 获取所有平台名称和各情感类别
    platforms = cross_tab.index.tolist()
    sentiment_categories = cross_tab.columns.tolist()

    # 创建柱状图
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

    # 为每种情感类别添加一个柱状系列
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
            # 设置柱子之间的间距
            gap="15%",
        )

    return bar_chart


# ============================================================
# 图表3: 舆情情感时间趋势折线图
# ============================================================
def plot_time_trend(df):
    """
    生成舆情情感时间趋势折线图。
    按日期对数据进行分组，计算每日的平均情感得分，绘制趋势线。

    Args:
        df: 包含 'publish_time' 和 'sentiment_score' 列的 DataFrame

    Returns:
        Line 图表对象，如果数据不满足要求则返回 None
    """
    # 检查必需的列
    required_cols = ["publish_time", "sentiment_score"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"{LOG_PREFIX} 警告: 数据中缺少 {missing_cols} 列，跳过时间趋势折线图")
        return None

    try:
        # 将 publish_time 转换为日期时间类型
        df_copy = df.copy()
        df_copy["publish_time"] = pd.to_datetime(df_copy["publish_time"], errors="coerce")
        # 移除无法解析的时间记录
        df_copy = df_copy.dropna(subset=["publish_time", "sentiment_score"])

        if df_copy.empty:
            print(f"{LOG_PREFIX} 警告: 有效的时间/情感得分数据为空，跳过时间趋势折线图")
            return None

        # 按日期分组，计算每日的平均情感得分
        df_copy["date"] = df_copy["publish_time"].dt.date
        daily_sentiment = df_copy.groupby("date")["sentiment_score"].mean().reset_index()
        daily_sentiment = daily_sentiment.sort_values("date")

        print(f"{LOG_PREFIX} 时间趋势: 共 {len(daily_sentiment)} 天的数据")

        # 格式化日期为字符串，方便图表显示
        dates = [str(d) for d in daily_sentiment["date"].tolist()]
        scores = [round(s, 4) for s in daily_sentiment["sentiment_score"].tolist()]

        # 创建折线图
        line_chart = (
            Line(init_opts=opts.InitOpts(theme=ThemeType.ROMANTIC, width="1000px", height="500px"))
            .add_xaxis(dates)
            .add_yaxis(
                series_name="平均情感得分",
                y_axis=scores,
                is_smooth=True,  # 平滑曲线
                areastyle_opts=opts.AreaStyleOpts(opacity=0.3),  # 半透明填充区域
                label_opts=opts.LabelOpts(is_show=False),
                linestyle_opts=opts.LineStyleOpts(width=3, color="#5470c6"),
                markline_opts=opts.MarkLineOpts(
                    data=[
                        opts.MarkLineItem(y=0.5, name="中性线"),
                    ],
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
    """
    生成主题分类分布柱状图。
    展示各个主题的评论数量分布。

    Args:
        df: 包含 'topic_label' 列的 DataFrame；
            如果为 None 则跳过

    Returns:
        Bar 图表对象，如果数据不满足要求则返回 None
    """
    if df is None:
        print(f"{LOG_PREFIX} 提示: 主题数据为空，跳过主题分布图")
        return None

    # 检查必需的列
    if "topic_label" not in df.columns:
        print(f"{LOG_PREFIX} 警告: 主题数据缺少 'topic_label' 列，跳过主题分布图")
        return None

    # 统计各主题数量
    topic_counts = df["topic_label"].value_counts()
    print(f"{LOG_PREFIX} 主题分布统计: {dict(topic_counts)}")

    topics = topic_counts.index.tolist()
    counts = topic_counts.values.tolist()

    # 创建柱状图
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
                # 使用渐变色让柱子更好看
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
                border_radius=[8, 8, 0, 0],  # 顶部圆角
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
    """
    生成词云图。
    从评论内容中提取文本，进行中文分词后生成词云图片。

    Args:
        df: 包含 'content' 列的 DataFrame

    Returns:
        str: 词云图片的保存路径，如果生成失败则返回 None
    """
    # 检查必需的列
    if "content" not in df.columns:
        print(f"{LOG_PREFIX} 警告: 数据中缺少 'content' 列，跳过词云图")
        return None

    # 确保 data/processed/ 目录存在
    ensure_dir(DATA_DIR)

    # 加载中英文停用词表
    stopwords = set()
    # 加载中文停用词
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

    # 加载英文停用词
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

    # 添加美以伊战争相关停用词（这些词出现在几乎所有评论中，对词云无区分度）
    war_stopwords = {"war", "战争", "conflict", "冲突", "Iran", "iran",
                     "美国", "伊朗", "以色列", "US", "USA", "Israel", "israel",
                     "中东", "军事", "military", "中东战争", "波斯湾", "核", "nuclear"}
    stopwords.update(war_stopwords)
    print(f"{LOG_PREFIX} 已添加战争相关停用词 {len(war_stopwords)} 个，总停用词数 {len(stopwords)}")

    # 合并所有评论内容
    all_text = " ".join(df["content"].dropna().astype(str).tolist())

    if not all_text.strip():
        print(f"{LOG_PREFIX} 警告: 评论文本内容为空，跳过词云图")
        return None

    print(f"{LOG_PREFIX} 评论文本总长度: {len(all_text)} 字符")

    try:
        # 使用 jieba 进行中文分词
        words = jieba.cut(all_text, cut_all=False)
        # 过滤停用词和单字符词
        filtered_words = [
            w for w in words
            if len(w.strip()) > 1 and w.strip() not in stopwords
        ]

        if not filtered_words:
            print(f"{LOG_PREFIX} 警告: 分词后无有效词汇，跳过词云图")
            return None

        # 将过滤后的词汇用空格连接，用于词云生成
        text_for_wordcloud = " ".join(filtered_words)
        print(f"{LOG_PREFIX} 分词后有效词汇数: {len(filtered_words)}")

        # 配置词云参数
        wc = WordCloud(
            font_path="C:\\Windows\\Fonts\\msyh.ttc",  # 使用微软雅黑字体支持中文
            width=1200,
            height=600,
            background_color="white",
            max_words=200,  # 最多显示200个词
            max_font_size=150,
            min_font_size=12,
            collocations=False,  # 不显示词语搭配
            scale=2,  # 提高分辨率
            random_state=42,
            margin=10,
        )

        # 生成词云
        wc.generate(text_for_wordcloud)

        # 使用 matplotlib 保存为图片
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
    """
    渲染完整的交互式仪表盘。
    将所有图表组合到一个 pyecharts Page 中，使用 SimplePageLayout 布局。

    Args:
        sentiment_df: 情感分析主数据 DataFrame
        topic_df:    主题分类数据 DataFrame（可选）

    Returns:
        Page 对象，包含所有可用的图表
    """
    print(f"\n{LOG_PREFIX} {'=' * 50}")
    print(f"{LOG_PREFIX} 开始渲染仪表盘...")
    print(f"{LOG_PREFIX} {'=' * 50}")

    # 使用 Page 容器，SimplePageLayout 将所有图表按顺序垂直排列
    page = Page(
        page_title="战争舆论挖掘 - 可视化仪表盘",
        layout=Page.SimplePageLayout,
    )

    # ----- 图表1: 情感分布饼图 -----
    print(f"{LOG_PREFIX} [1/5] 生成情感分布饼图...")
    pie = plot_sentiment_pie(sentiment_df)
    if pie is not None:
        page.add(pie)
        print(f"{LOG_PREFIX} [1/5] 情感分布饼图 ✓")
    else:
        print(f"{LOG_PREFIX} [1/5] 情感分布饼图 ✗ (跳过)")

    # ----- 图表2: 平台对比柱状图 -----
    print(f"{LOG_PREFIX} [2/5] 生成各平台情感倾向对比图...")
    bar_platform = plot_platform_comparison(sentiment_df)
    if bar_platform is not None:
        page.add(bar_platform)
        print(f"{LOG_PREFIX} [2/5] 平台对比柱状图 ✓")
    else:
        print(f"{LOG_PREFIX} [2/5] 平台对比柱状图 ✗ (跳过)")

    # ----- 图表3: 时间趋势折线图 -----
    print(f"{LOG_PREFIX} [3/5] 生成舆情情感时间趋势图...")
    line_trend = plot_time_trend(sentiment_df)
    if line_trend is not None:
        page.add(line_trend)
        print(f"{LOG_PREFIX} [3/5] 时间趋势折线图 ✓")
    else:
        print(f"{LOG_PREFIX} [3/5] 时间趋势折线图 ✗ (跳过)")

    # ----- 图表4: 主题分布柱状图 -----
    print(f"{LOG_PREFIX} [4/5] 生成主题分类分布图...")
    bar_topic = plot_topic_distribution(topic_df)
    if bar_topic is not None:
        page.add(bar_topic)
        print(f"{LOG_PREFIX} [4/5] 主题分布柱状图 ✓")
    else:
        print(f"{LOG_PREFIX} [4/5] 主题分布柱状图 ✗ (跳过)")

    # ----- 图表5: 词云图 -----
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
    """
    程序主入口。
    执行流程:
    1. 加载情感分析结果数据（带容错回退机制）
    2. 加载主题分类数据（可选）
    3. 确保输出目录存在
    4. 生成所有图表并渲染仪表盘
    5. 将仪表盘保存为 HTML 文件
    6. 打印输出路径
    """
    print(f"\n{LOG_PREFIX} {'#' * 50}")
    print(f"{LOG_PREFIX} 战争舆论挖掘 - 可视化仪表盘生成器")
    print(f"{LOG_PREFIX} {'#' * 50}\n")

    # ---------- 步骤1: 加载数据 ----------
    print(f"{LOG_PREFIX} 正在加载数据...")

    sentiment_df = load_sentiment_data()
    if sentiment_df is None:
        print(f"{LOG_PREFIX} 错误: 无法加载任何数据，程序退出")
        print(f"{LOG_PREFIX} 请先运行数据分析脚本生成 data/processed/sentiment_results.csv")
        sys.exit(1)

    # 显示数据的列信息，便于调试
    print(f"{LOG_PREFIX} 数据列: {list(sentiment_df.columns)}")
    print(f"{LOG_PREFIX} 数据形状: {sentiment_df.shape}")

    # ---------- 步骤2: 加载主题数据（可选） ----------
    topic_df = load_topic_data()

    # ---------- 步骤3: 确保输出目录存在 ----------
    ensure_dir(OUTPUT_DIR)
    ensure_dir(DATA_DIR)

    # ---------- 步骤4: 生成分析结论 ----------
    print(f"\n{LOG_PREFIX} 正在生成美以伊战争舆论分析结论...")
    conclusions = generate_conclusions(sentiment_df, topic_df)
    if conclusions:
        print(f"{LOG_PREFIX} 已生成 {len(conclusions)} 条结论")
        for i, c in enumerate(conclusions, 1):
            print(f"{LOG_PREFIX}   结论{i}: {c[:60]}...")
    else:
        print(f"{LOG_PREFIX} 警告: 未能生成结论")

    # ---------- 步骤5: 渲染仪表盘 ----------
    dashboard, wc_path = render_dashboard(sentiment_df, topic_df)

    # ---------- 步骤6: 保存仪表盘 HTML ----------
    output_path = os.path.join(OUTPUT_DIR, "dashboard.html")
    try:
        dashboard.render(output_path)
        print(f"\n{LOG_PREFIX} {'*' * 50}")
        print(f"{LOG_PREFIX} 仪表盘已成功保存!")
        print(f"{LOG_PREFIX} 输出路径: {os.path.abspath(output_path)}")

        # 读取已生成的 HTML 内容
        with open(output_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        # 将结论块注入到 HTML 页面的 body 开头处
        if conclusions:
            conclusions_html = render_conclusions_block(conclusions)
            html_content = html_content.replace(
                "<body>",
                "<body>\n" + conclusions_html
            )
            print(f"{LOG_PREFIX} 分析结论已注入仪表盘 HTML")

        # 将词云图片嵌入到 HTML 中（插入到文件末尾 </body> 前）
        if wc_path is not None and os.path.exists(wc_path):
            # 转换为相对路径
            rel_path = os.path.relpath(wc_path, OUTPUT_DIR)
            wordcloud_html = f"""
    <div style="max-width:1200px;margin:20px auto;padding:0 20px 40px 20px;">
        <div style="background:#ffffff;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,0.08);padding:30px;">
            <h2 style="font-size:22px;font-weight:bold;color:#333;margin:0 0 20px 0;text-align:center;">
                ☁️ 美以伊战争评论词云图
            </h2>
            <p style="text-align:center;color:#888;font-size:13px;margin:0 0 24px 0;">
                基于jieba分词与TF-IDF权重生成，剔除战争相关高频词后突出显示讨论焦点
            </p>
            <div style="text-align:center;">
                <img src="{rel_path}" alt="词云图" style="max-width:100%;height:auto;border-radius:8px;">
            </div>
        </div>
    </div>"""
            html_content = html_content.replace("</body>", wordcloud_html + "\n</body>")
            print(f"{LOG_PREFIX} 词云图已嵌入仪表盘 HTML")

        # 保存修改后的 HTML
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

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
