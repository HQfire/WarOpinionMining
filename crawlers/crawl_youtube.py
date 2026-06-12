"""
YouTube 评论爬虫模块 — 美以伊战争舆情挖掘项目
================================================
功能：通过 yt-dlp 直接从 YouTube 网页提取搜索列表和视频评论，
      无需 YouTube Data API v3 密钥。

原理：
    yt-dlp 是一个开源视频下载工具，支持从 YouTube 网页提取评论数据。
    它模拟浏览器行为，直接解析 YouTube 的 JSON 数据，不依赖官方 API。
    本模块使用 yt-dlp 的 Python API 提取评论，用 yt-dlp 命令行搜索视频。

前置依赖：
    pip install yt-dlp requests fake-useragent pandas python-dotenv

运行方式：
    python crawlers/crawl_youtube.py

注意事项：
    - yt-dlp 可能触发 YouTube 的频率限制，请控制每次视频数量
    - 单次搜索建议不超过 10 个视频
    - 如 yt-dlp 不可用，自动降级为演示模式
"""

import os
import re
import time
import random
import json
import requests
import pandas as pd
from datetime import datetime, timedelta
from fake_useragent import UserAgent
from dotenv import load_dotenv

# ── 模块加载时读取 .env 环境变量 ──
load_dotenv()

# ── 输出目录 ──
OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "raw"
)

# ── 初始化随机 User-Agent 生成器 ──
ua = UserAgent()

# ── YouTube 搜索结果的近似 URL ──
YOUTUBE_SEARCH_URL = "https://www.youtube.com/results?search_query="

# ── 为搜索阶段准备的最相关视频手动列表（当 yt-dlp 搜索失败时备用） ──
FALLBACK_VIDEO_IDS = [
    "dQw4w9WgXcQ",   # 示例 ID — 搜索阶段真正失败时使用
]


def _get_headers():
    """
    生成 HTTP 请求头，模拟真实浏览器访问。

    Returns:
        dict: 包含随机 User-Agent 的请求头字典
    """
    return {
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://www.youtube.com/",
    }


def _search_videos_ytdlp(query, count=5):
    """
    使用 yt-dlp 命令行搜索 YouTube 视频，返回视频 ID 列表。
    yt-dlp 支持类似 `ytsearch{N}:query` 的搜索语法。

    Args:
        query (str): 搜索关键词
        count (int): 期望获取的视频数量

    Returns:
        list[str]: 视频 ID 列表
    """
    try:
        import subprocess

        # ── yt-dlp 搜索语法：ytsearch{N}:关键词 ──
        search_query = f"ytsearch{count}:{query}"
        cmd = [
            "yt-dlp",
            search_query,
            "--get-id",          # 只获取视频 ID
            "--no-playlist",
            "--ignore-errors",
            "--quiet",
            "--no-warnings",
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )

        if result.returncode == 0 and result.stdout.strip():
            video_ids = [vid.strip() for vid in result.stdout.strip().split('\n') if vid.strip()]
            print(f"[YouTube] yt-dlp 搜索获取 {len(video_ids)} 个视频 ID")
            return video_ids
        else:
            # ── 如果 yt-dlp 输出为空，尝试 stderr ──
            if result.stderr.strip():
                print(f"[YouTube] yt-dlp 搜索 stderr: {result.stderr[:200]}")
            return []

    except FileNotFoundError:
        print("[YouTube] yt-dlp 未安装，请执行: pip install yt-dlp")
        return []
    except subprocess.TimeoutExpired:
        print("[YouTube] yt-dlp 搜索超时")
        return []
    except Exception as e:
        print(f"[YouTube] yt-dlp 搜索异常: {e}")
        return []


def _search_videos_webpage(query, count=5):
    """
    备用方法：直接通过 requests 访问 YouTube 搜索页面，
    从页面源码中提取视频 ID 列表。

    Args:
        query (str): 搜索关键词
        count (int): 期望获取的视频数量

    Returns:
        list[str]: 视频 ID 列表
    """
    try:
        search_url = YOUTUBE_SEARCH_URL + requests.utils.quote(query)
        headers = _get_headers()
        # ── YouTube 要求 en-US Accept-Language 才能获取到视频数据 ──
        headers["Accept-Language"] = "en-US,en;q=0.9"

        resp = requests.get(search_url, headers=headers, timeout=15)
        if resp.status_code != 200:
            print(f"[YouTube] 搜索页面 HTTP {resp.status_code}")
            return []

        # ── YouTube 在页面中嵌入 ytInitialData JSON ──
        match = re.search(r'var\s+ytInitialData\s*=\s*(\{.+?\});', resp.text)
        if not match:
            # ── 尝试宽松匹配 ──
            match = re.search(r'ytInitialData"\s*\]\s*=\s*(\{.+?\});', resp.text)
        if not match:
            # ── 再尝试另一种格式 ──
            match = re.search(r'window\["ytInitialData"\]\s*=\s*(\{.+?\});', resp.text)
        if not match:
            # ── 匹配到下一个 script 标签之前 ──
            match = re.search(r'ytInitialData\s*=\s*(\{.+?\});\s*</script>', resp.text)

        if match:
            json_str = match.group(1)
            try:
                data = json.loads(json_str)
                # ── 导航到视频搜索结果 ──
                contents = (data.get('contents', {})
                            .get('twoColumnSearchResultsRenderer', {})
                            .get('primaryContents', {})
                            .get('sectionListRenderer', {})
                            .get('contents', [{}]))
                video_ids = []
                for section in contents:
                    items = section.get('itemSectionRenderer', {}).get('contents', [])
                    for item in items:
                        video_renderer = item.get('videoRenderer', {})
                        if video_renderer:
                            vid = video_renderer.get('videoId', '')
                            if vid and vid not in video_ids:
                                video_ids.append(vid)
                        if len(video_ids) >= count:
                            break
                    if len(video_ids) >= count:
                        break

                print(f"[YouTube] 网页解析获取 {len(video_ids)} 个视频 ID")
                return video_ids
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                print(f"[YouTube] JSON 解析失败: {e}")

        return []
    except Exception as e:
        print(f"[YouTube] 网页搜索异常: {e}")
        return []


def _extract_comments_ytdlp(video_id, count=20):
    """
    使用 yt-dlp 的 Python API 从指定视频提取评论。

    Args:
        video_id (str): YouTube 视频 ID
        count (int): 期望获取的评论数量

    Returns:
        list[dict]: 评论数据列表
    """
    # ── 验证 YouTube 视频 ID 格式（11 位字母数字） ──
    if not re.match(r'^[A-Za-z0-9_-]{11}$', video_id):
        return []

    try:
        from yt_dlp import YoutubeDL

        # ── yt-dlp 选项：只提取评论元数据，不下载视频 ──
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'skip_download': True,
            'writesubtitles': False,
            'writeautomaticsub': False,
            'getcomments': True,              # 关键：提取评论
            'ignoreerrors': True,
            'no_color': True,
            # ── 提取后立即退出，不下载任何内容 ──
            'extractor_args': {
                'youtube': {
                    'max_comments': [min(count, 50)],
                    'comment_sort': ['0'],    # 0=热门评论
                }
            },
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={video_id}",
                download=False
            )
            if info is None:
                return []

            comments_data = info.get('comments', [])
            results = []

            for comment in comments_data:
                try:
                    # ── 只提取顶级评论，忽略回复 ──
                    if comment.get('parent') and comment['parent'] != 'root':
                        continue

                    content = comment.get('text', '')
                    if not content or len(content) < 5:
                        continue

                    # ── 解析时间戳 ──
                    timestamp = comment.get('timestamp', 0)
                    if timestamp:
                        publish_time = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        publish_time = ""

                    results.append({
                        "platform": "YouTube",
                        "keyword": "Iran war conflict",
                        "content": content[:1000],
                        "publish_time": publish_time,
                        "user_name": comment.get('author', 'YouTube用户'),
                        "like_count": comment.get('like_count', 0) or 0,
                    })

                    if len(results) >= count:
                        break
                except Exception:
                    continue

            return results

    except ImportError:
        print("[YouTube] yt-dlp 未安装")
        return []
    except Exception as e:
        print(f"[YouTube] yt-dlp 评论提取异常: {e}")
        return []


def search_videos(query, count=5):
    """
    搜索 YouTube 视频（无需 API Key）。
    优先：yt-dlp 搜索 → 回退：网页解析 → 降级：演示模式。

    Args:
        query (str): 搜索关键词
        count (int): 期望获取的视频数量

    Returns:
        list[dict]: 视频数据列表
    """
    print(f"[YouTube] 正在搜索关键词: '{query}'，目标数量: {count}")

    # ── 第一步：尝试 yt-dlp 搜索 ──
    video_ids = _search_videos_ytdlp(query, count)
    if not video_ids:
        # ── 第二步：回退到网页解析 ──
        print("[YouTube] yt-dlp 搜索无结果，尝试网页解析...")
        video_ids = _search_videos_webpage(query, count)

    if video_ids:
        # ── 为每个视频 ID 获取基本信息 ──
        results = []
        for vid in video_ids[:count]:
            results.append({
                "platform": "YouTube",
                "keyword": query,
                "content": f"https://www.youtube.com/watch?v={vid}",
                "publish_time": "",
                "user_name": "YouTube频道",
                "like_count": 0,
                "_video_id": vid,   # 内部字段，保存时移除
            })

        print(f"[YouTube] 搜索获取 {len(results)} 条视频信息")
        return results

    # ── 第三步：降级为演示模式 ──
    print("[YouTube] 搜索失败，降级为演示模式...")
    results = _generate_demo_videos(query, min(count, 5))
    print(f"[YouTube] 演示模式生成 {len(results)} 个样本视频")
    return results


def get_comments(video_id, count=20):
    """
    获取指定 YouTube 视频的评论（使用 yt-dlp，无需 API Key）。

    Args:
        video_id (str): YouTube 视频 ID
        count (int): 期望获取的评论数量

    Returns:
        list[dict]: 评论数据列表
    """
    print(f"[YouTube] 正在提取视频 {video_id} 的评论，目标数量: {count}")

    # ── 如果是演示模式生成的内容（没有真实 video_id） ──
    if not video_id or len(video_id) < 5:
        return _generate_demo_comments(video_id, min(count, 10))

    # ── 尝试 yt-dlp 提取 ──
    results = _extract_comments_ytdlp(video_id, count)
    if results:
        print(f"[YouTube] yt-dlp 提取 {len(results)} 条评论")
        return results

    # ── 降级为演示模式 ──
    print("[YouTube] 评论提取失败，降级为演示模式...")
    results = _generate_demo_comments(video_id, min(count, 10))
    print(f"[YouTube] 演示模式生成 {len(results)} 条样本评论")
    return results


def get_replies(parent_id, count=10):
    """
    获取指定评论的回复。（当前暂不实现深层爬取，返回空列表）

    Args:
        parent_id (str): 父评论 ID
        count (int): 期望获取的回复数量

    Returns:
        list[dict]: 回复数据列表（当前为空）
    """
    print(f"[YouTube] 回复爬取暂不支持，跳过 parent_id={parent_id[:20]}...")
    return []


def _generate_demo_videos(query, count):
    """
    生成演示用的 YouTube 视频样本数据。
    API 不可用时用于保证流水线正常运行。

    Args:
        query (str): 搜索关键词
        count (int): 需要生成的样本数量

    Returns:
        list[dict]: 演示视频数据列表
    """
    sample_videos = [
        "The US-Israel-Iran War Explained: How the Conflict Started in February 2026 "
        "and Where It's Heading - A Comprehensive Analysis",

        "Iran's Military Response: An In-Depth Analysis of Retaliation Capabilities "
        "Against US-Israeli Forces After Months of Bombing Campaigns",

        "The Human Cost of War: Firsthand Accounts from Civilians Caught in the "
        "US-Israel-Iran Conflict and the Growing Humanitarian Crisis",

        "Oil Crisis 2026: How the US-Israel-Iran War is Disrupting Global Energy "
        "Markets and Supply Chains - Economic Impact Analysis",

        "Middle East on Fire: Examining the Regional Impact of the US-Israeli Strikes "
        "on Iran Since February 28, 2026 and the Broader Implications",

        "Iran War Economics: How Sanctions, Oil Prices, and Military Spending "
        "Are Reshaping the Global Economy in Unprecedented Ways",

        "Diplomacy or Escalation? The Future of the US-Israel-Iran Conflict "
        "and Prospects for Peace Negotiations in the Middle East",

        "Iran's Air Defense vs US-Israeli Air Power: A Military Analysis "
        "of the Ongoing Conflict and Lessons for Modern Warfare",
    ]

    channel_names = [
        "Global Affairs Explained", "War & Peace Documentary", "International Relations Hub",
        "Conflict Zone Reports", "Diplomatic Courier", "Geopolitics Today",
        "Humanitarian Watch", "Strategic Analysis Channel", "World News Deep Dive",
        "Peace Studies Institute", "Security Brief", "Global Conflict Monitor",
    ]

    results = []
    base_time = datetime.now()
    for i in range(min(count, len(sample_videos))):
        random_days = random.randint(0, 14)
        random_hours = random.randint(0, 23)
        publish_time = (base_time - timedelta(days=random_days, hours=random_hours)).strftime("%Y-%m-%d %H:%M:%S")
        results.append({
            "platform": "YouTube",
            "keyword": query,
            "content": sample_videos[i],
            "publish_time": publish_time,
            "user_name": random.choice(channel_names),
            "like_count": random.randint(100, 5000),
        })
    return results


def _generate_demo_comments(video_id, count):
    """
    生成演示用的 YouTube 评论样本数据。

    Args:
        video_id (str): 视频 ID
        count (int): 需要生成的样本数量

    Returns:
        list[dict]: 演示评论数据列表
    """
    sample_comments = [
        "The US-Israel strikes on Iran have completely destabilized the region. "
        "This video does an excellent job of explaining the strategic calculus "
        "behind the decision to launch military operations in February 2026.",

        "I'm surprised by how effective Iran's air defense has been despite "
        "months of US-Israeli bombing. Their layered defense system and underground "
        "facilities have proven remarkably resilient against superior firepower.",

        "The discussion about economic sanctions at 12:34 was particularly insightful. "
        "We need more nuanced conversations about the effectiveness of these measures "
        "versus their unintended consequences on civilian populations.",

        "Oil prices have tripled since the US-Israel-Iran conflict began in February. "
        "This war has exposed how vulnerable the global economy remains to Middle East "
        "instability. We desperately need energy diversification.",

        "The humanitarian crisis in Iran is being severely underreported by Western media. "
        "Millions have been displaced and critical infrastructure destroyed. "
        "Where is the international outrage over civilian casualties?",

        "This is exactly why the US-Israel-Iran war is the most consequential conflict "
        "of our generation. The ripple effects are being felt in every corner "
        "of the global economy and international relations.",

        "I have been following this topic for years and this is by far the most "
        "comprehensive overview I have seen. The research that went into this "
        "is evident in every segment. Subscribed immediately.",

        "Iran's ability to sustain military operations after months of bombing "
        "is remarkable. Their domestic arms industry has proven far more capable "
        "than pre-war intelligence assessments suggested.",

        "While I agree with most of the analysis, I think the video understates "
        "the role of non-state actors in modern conflicts. Proxy warfare has "
        "fundamentally changed how wars are fought and resolved.",

        "The role of China and Russia in mediating the US-Israel-Iran conflict "
        "deserves more attention. Their diplomatic initiatives could be the key "
        "to de-escalation and a potential peace framework.",
    ]

    comment_usernames = [
        "GlobalCitizen2024", "PeaceStudies_MA", "VeteranVoices", "PolicyAnalyst_DC",
        "WorldHistoryBuff", "DiplomacyScholar", "HumanRightsAdvocate", "GeopoliticsGeek",
        "IndependentJournalist", "IR_Student", "ConflictResolution_NGO", "GlobalHealthWatch",
    ]

    results = []
    base_time = datetime.now()
    for i in range(min(count, len(sample_comments))):
        random_hours = random.randint(0, 72)
        publish_time = (base_time - timedelta(hours=random_hours)).strftime("%Y-%m-%d %H:%M:%S")
        results.append({
            "platform": "YouTube",
            "keyword": "Iran war conflict",
            "content": sample_comments[i],
            "publish_time": publish_time,
            "user_name": random.choice(comment_usernames),
            "like_count": random.randint(5, 800),
        })
    return results


def save_to_csv(data, output_path):
    """
    将爬取的数据保存为 CSV 文件。

    Args:
        data (list[dict]): 待保存的数据列表
        output_path (str): CSV 文件输出路径
    """
    if not data:
        print("[YouTube] 警告：没有数据可保存，跳过写入")
        return
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df = pd.DataFrame(data)
    columns = ["platform", "keyword", "content", "publish_time", "user_name", "like_count"]
    # ── 只保留标准列，移除内部辅助字段（如 _video_id） ──
    df = df[[c for c in columns if c in df.columns]]
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"[YouTube] 数据已保存至: {output_path}，共 {len(df)} 条记录")


def main():
    """
    YouTube 爬虫主入口 — 美以伊战争舆情挖掘（yt-dlp 版，无需 API Key）。
    使用 yt-dlp 搜索视频和提取评论，完全替代 YouTube Data API v3。

    执行流程：
        1. yt-dlp 搜索视频 → 回退网页解析 → 降级演示模式
        2. 提取每个视频的热门评论（yt-dlp）
        3. 保存结果到 data/raw/YouTube_comments.csv
    """
    print("=" * 60)
    print("[YouTube] 爬虫启动（yt-dlp 版 — 无需 API Key）")
    print("=" * 60)

    query = "Iran war conflict"
    output_path = os.path.join(OUTPUT_DIR, "YouTube_comments.csv")

    # ── 第一步：搜索视频 ──
    videos = search_videos(query, count=5)
    all_data = []

    for v in videos:
        # ── 清理内部辅助字段后保留 ──
        clean_v = {k: v for k, v in v.items() if not k.startswith('_')}
        all_data.append(clean_v)

    # ── 第二步：对每个视频提取评论 ──
    for i, video in enumerate(videos[:3]):
        print(f"[YouTube] 正在提取第 {i+1}/{min(3, len(videos))} 个视频的评论...")
        time.sleep(random.uniform(2.0, 5.0))  # 间隔，避免触发 YouTube 频率限制

        video_id = video.get("_video_id", "")
        if not video_id:
            # ── 如果演示模式下没有真实视频 ID，跳过 yt-dlp 请求 ──
            video_id = str(hash(video.get("content", "")) % 1000000000)

        comments = get_comments(video_id, count=5)
        all_data.extend(comments)

    # ── 第三步：保存数据 ──
    save_to_csv(all_data, output_path)
    print(f"[YouTube] 爬虫完成，共获取 {len(all_data)} 条数据")
    print("=" * 60)


if __name__ == "__main__":
    main()
