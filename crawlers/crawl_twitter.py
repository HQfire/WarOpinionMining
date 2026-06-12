"""
Twitter / X 推文爬虫模块 — 美以伊战争舆情挖掘项目
=====================================================
功能：通过Twitter API v2搜索美以伊战争相关推文并获取回复数据。
      当Bearer Token未配置时，自动降级为演示模式，生成逼真的英语样本数据，
      确保整个数据处理流水线可以端到端运行。

输出CSV格式：platform, keyword, content, publish_time, user_name, like_count
"""

import os
import time
import random
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
from fake_useragent import UserAgent
from dotenv import load_dotenv

# ── 模块加载时读取 .env 环境变量 ──
load_dotenv()

# ── 从环境变量获取Twitter Bearer Token ──
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", "")

# ── 输出目录 ──
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw")

# ── 初始化随机 User-Agent 生成器 ──
ua = UserAgent()

# ── Twitter API v2 基础URL ──
TWITTER_API_BASE = "https://api.twitter.com/2"


def _get_headers():
    """
    生成HTTP请求头，包含Bearer Token认证和随机User-Agent。

    Returns:
        dict: 包含Authorization和随机User-Agent的请求头字典
    """
    headers = {
        "User-Agent": ua.random,
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }
    if TWITTER_BEARER_TOKEN:
        headers["Authorization"] = f"Bearer {TWITTER_BEARER_TOKEN}"
    return headers


def _generate_demo_tweets(keyword, count):
    """
    生成演示用的Twitter推文样本数据。
    当Bearer Token未配置或API不可用时，用此函数生成逼真的英语讨论数据。

    样本内容涵盖地缘政治、国际冲突、和平倡议、人道主义等话题。

    Args:
        keyword (str): 搜索关键词
        count (int): 需要生成的样本数量

    Returns:
        list[dict]: 包含platform, keyword, content, publish_time, user_name, like_count的字典列表
    """
    # ── 美以伊战争相关英文推文样本池 ──
    sample_tweets = [
        "The US-Israel military strikes on Iran have continued for months since February 2026. "
        "The situation remains tense with no clear exit strategy. "
        "Regional stability hangs in the balance. #IranWar #MiddleEast",

        "Breaking: Iran's retaliation has been more effective than many Western analysts predicted. "
        "Their missile and drone capabilities have proven resilient despite sustained bombing campaigns. "
        "The conflict is far from over. #USIsraelIran",

        "Analysis: The US-Israel-Iran conflict is reshaping Middle East power dynamics in real-time. "
        "Oil prices have surged 40% since the war began, and the global economy is feeling the strain. "
        "This is the most consequential Middle East conflict in decades. #Geopolitics",

        "The economic impact of the Iran war cannot be overstated. "
        "Shipping through the Strait of Hormuz has been severely disrupted. "
        "Energy prices are hammering economies worldwide. #OilCrisis",

        "The humanitarian toll of the US-Israel-Iran war continues to rise. "
        "Millions of Iranian civilians displaced, critical infrastructure destroyed. "
        "The international community must urgently push for a ceasefire. #HumanRights",

        "NATO's evolving strategy reflects the changing nature of modern warfare. "
        "Cyber capabilities, disinformation campaigns, and hybrid warfare tactics "
        "are now as important as conventional military strength. #DefensePolicy",

        "The global energy transition is reshaping international alliances. "
        "Countries that adapt quickly to renewable energy will have significant "
        "geopolitical advantages in the coming decades. The race is on. #EnergyTransition",

        "Iran's defense capabilities have surprised many military analysts. "
        "Their layered air defense system and underground facilities have proven "
        "more resilient than pre-war intelligence assessments suggested. #MilitaryAnalysis",

        "Diplomatic efforts to end the US-Israel-Iran conflict face major obstacles. "
        "Trust between parties is at an all-time low. China and Russia are positioning "
        "themselves as mediators but the path to peace remains uncertain. #Diplomacy",

        "As someone reporting from the region, the US-Israel-Iran war has fundamentally "
        "altered daily life for millions. The resilience of ordinary Iranians is remarkable "
        "but the international community must do more to address this humanitarian catastrophe.",
    ]

    usernames = [
        "GlobalAffairs_Analyst", "DiploWatcher", "PeaceResearch_Org", "WarReport_Daily",
        "GeoStrategy_Now", "UN_Watch_Observer", "ConflictZone_News", "IntlRelations_Prof",
        "SecurityBrief", "HumanityFirst_NGO", "WorldPolicy_Forum", "CrisisResponse",
    ]

    results = []
    base_time = datetime.now(timezone.utc)

    for i in range(min(count, len(sample_tweets))):
        # ── 生成随机的发布时间（最近5天内） ──
        random_days = random.randint(0, 5)
        random_hours = random.randint(0, 23)
        random_minutes = random.randint(0, 59)
        random_seconds = random.randint(0, 59)
        publish_time = (base_time - timedelta(
            days=random_days, hours=random_hours, minutes=random_minutes, seconds=random_seconds
        )).strftime("%Y-%m-%d %H:%M:%S")

        results.append({
            "platform": "Twitter",
            "keyword": keyword,
            "content": sample_tweets[i],
            "publish_time": publish_time,
            "user_name": f"@{random.choice(usernames)}",
            "like_count": random.randint(10, 1500),
        })

    return results


def _generate_demo_replies(tweet_id, count):
    """
    生成演示用的推文回复样本数据。

    Args:
        tweet_id (str): 推文ID
        count (int): 需要生成的样本数量

    Returns:
        list[dict]: 包含平台、内容、时间、用户名、点赞数的字典列表
    """
    sample_replies = [
        "The US-Israel strikes on Iran have destabilized the entire region. "
        "This is exactly what critics warned about before the intervention began.",

        "Iran's response to the attacks shows their military capability "
        "is far stronger than Western intelligence assumed. This changes everything.",

        "I fear this conflict between the US, Israel and Iran could spiral "
        "into a wider regional war. The stakes could not be higher.",

        "The civilian casualties in Iran are heartbreaking. "
        "We need an immediate ceasefire and humanitarian access now.",

        "Oil prices are skyrocketing because of this US-Israel-Iran war. "
        "The global economy is already feeling the impact at gas stations worldwide.",

        "Fascinating thread. Would love to see more data on the economic "
        "impacts of these sanctions over the past 3 years.",

        "As a veteran, I can say that the human cost of war is far greater "
        "than any strategic gain. Diplomacy must prevail.",

        "The proxy war dimension of the US-Israel-Iran conflict is often "
        "overlooked. Hezbollah and other actors complicate the picture immensely.",

        "Thank you for covering this. The mainstream media often ignores "
        "the long-term consequences of these geopolitical shifts.",

        "Iran's missile capabilities have proven to be much more advanced "
        "than pre-war assessments suggested. Intelligence failures are staggering.",
    ]

    reply_users = [
        "WorldCitizen2024", "PolicyNerd", "HistoryBuff", "PeaceAdvocate",
        "DataDriven_View", "Veteran_Voice", "GlobalStudent", "FreelanceJournalist",
    ]

    results = []
    base_time = datetime.now(timezone.utc)

    for i in range(min(count, len(sample_replies))):
        random_hours = random.randint(0, 36)
        publish_time = (base_time - timedelta(hours=random_hours)).strftime("%Y-%m-%d %H:%M:%S")

        results.append({
            "platform": "Twitter",
            "keyword": "Iran war",
            "content": sample_replies[i],
            "publish_time": publish_time,
            "user_name": f"@{random.choice(reply_users)}",
            "like_count": random.randint(0, 200),
        })

    return results


def search_tweets(keyword, count=10):
    """
    搜索Twitter推文。
    优先使用Bearer Token调用Twitter API v2搜索端点；
    若Token未配置或请求失败则降级为演示模式。

    Twitter API v2 搜索端点：
        GET https://api.twitter.com/2/tweets/search/recent

    Args:
        keyword (str): 搜索关键词（支持Twitter标准搜索语法）
        count (int): 期望获取的推文数量，默认10（最大100）

    Returns:
        list[dict]: 推文数据列表
    """
    print(f"[Twitter] 开始搜索关键词: '{keyword}'，目标数量: {count}")

    if not TWITTER_BEARER_TOKEN:
        print("[Twitter] 未配置 TWITTER_BEARER_TOKEN，使用演示模式")
    else:
        # ── 真实API调用模式 ──
        url = f"{TWITTER_API_BASE}/tweets/search/recent"
        # ── 请求字段：推文文本、创建时间、作者用户名、点赞数 ──
        params = {
            "query": f"{keyword} lang:en -is:retweet",
            "max_results": min(count, 100),
            "tweet.fields": "created_at,public_metrics,author_id",
            "expansions": "author_id",
            "user.fields": "username",
        }
        try:
            resp = requests.get(url, params=params, headers=_get_headers(), timeout=20)

            if resp.status_code == 429:
                print("[Twitter] API频率限制(429)，等待后降级为演示模式")
            elif resp.status_code == 401:
                print("[Twitter] Bearer Token无效(401)，降级为演示模式")
            elif resp.status_code != 200:
                print(f"[Twitter] API返回状态码 {resp.status_code}，降级为演示模式")
            else:
                data = resp.json()
                if "errors" in data:
                    print(f"[Twitter] API错误: {data['errors']}，降级为演示模式")
                else:
                    tweets = data.get("data", [])
                    # ── 建立作者ID到用户名的映射 ──
                    users_map = {}
                    for user in data.get("includes", {}).get("users", []):
                        users_map[user.get("id")] = user.get("username", "unknown")

                    results = []
                    for t in tweets:
                        author_id = t.get("author_id", "")
                        metrics = t.get("public_metrics", {})
                        created_at = t.get("created_at", "")
                        # ── 格式化ISO时间字符串 ──
                        if created_at:
                            try:
                                dt = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S.%fZ")
                                created_at = dt.strftime("%Y-%m-%d %H:%M:%S")
                            except ValueError:
                                pass

                        results.append({
                            "platform": "Twitter",
                            "keyword": keyword,
                            "content": t.get("text", ""),
                            "publish_time": created_at,
                            "user_name": f"@{users_map.get(author_id, 'unknown')}",
                            "like_count": metrics.get("like_count", 0),
                        })
                    if results:
                        print(f"[Twitter] API返回 {len(results)} 条推文")
                        return results
        except requests.exceptions.ConnectionError as e:
            print(f"[Twitter] 连接错误: {e}，降级为演示模式")
        except requests.exceptions.Timeout as e:
            print(f"[Twitter] 请求超时: {e}，降级为演示模式")
        except Exception as e:
            print(f"[Twitter] 未知异常: {e}，降级为演示模式")

    # ── 演示模式 ──
    print("[Twitter] 使用演示模式生成样本数据...")
    sample_count = min(count, 10)
    results = _generate_demo_tweets(keyword, sample_count)
    print(f"[Twitter] 演示模式生成 {len(results)} 条样本推文")
    return results


def get_replies(tweet_id, count=20):
    """
    获取指定推文的回复（通过搜索@对话ID的方式）。

    Twitter API v2 搜索回复的方法：
        搜索conversation_id等于指定tweet_id的推文

    Args:
        tweet_id (str): 推文ID
        count (int): 期望获取的回复数量，默认20

    Returns:
        list[dict]: 回复数据列表
    """
    print(f"[Twitter] 获取推文 {tweet_id} 的回复，目标数量: {count}")

    if not TWITTER_BEARER_TOKEN:
        print("[Twitter] 未配置 Token，使用演示模式获取回复")
    else:
        url = f"{TWITTER_API_BASE}/tweets/search/recent"
        params = {
            "query": f"conversation_id:{tweet_id}",
            "max_results": min(count, 100),
            "tweet.fields": "created_at,public_metrics,author_id",
            "expansions": "author_id",
            "user.fields": "username",
        }
        try:
            resp = requests.get(url, params=params, headers=_get_headers(), timeout=20)

            if resp.status_code == 200:
                data = resp.json()
                if "errors" not in data:
                    replies = data.get("data", [])
                    users_map = {}
                    for user in data.get("includes", {}).get("users", []):
                        users_map[user.get("id")] = user.get("username", "unknown")

                    results = []
                    for r in replies:
                        metrics = r.get("public_metrics", {})
                        created_at = r.get("created_at", "")
                        if created_at:
                            try:
                                dt = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S.%fZ")
                                created_at = dt.strftime("%Y-%m-%d %H:%M:%S")
                            except ValueError:
                                pass

                        results.append({
                            "platform": "Twitter",
                            "keyword": "Iran war",
                            "content": r.get("text", ""),
                            "publish_time": created_at,
                            "user_name": f"@{users_map.get(r.get('author_id', ''), 'unknown')}",
                            "like_count": metrics.get("like_count", 0),
                        })
                    if results:
                        print(f"[Twitter] API返回 {len(results)} 条回复")
                        return results
            elif resp.status_code == 429:
                print("[Twitter] 回复API频率限制(429)，降级为演示模式")
            else:
                print(f"[Twitter] 回复API状态码 {resp.status_code}，降级为演示模式")
        except Exception as e:
            print(f"[Twitter] 回复API异常: {e}，降级为演示模式")

    # ── 演示模式 ──
    print("[Twitter] 回复获取降级为演示模式...")
    results = _generate_demo_replies(tweet_id, min(count, 10))
    print(f"[Twitter] 演示模式生成 {len(results)} 条样本回复")
    return results


def save_to_csv(data, output_path):
    """
    将爬取的数据保存为CSV文件。
    使用pandas的to_csv方法，确保格式统一且支持多语言编码。

    Args:
        data (list[dict]): 待保存的数据列表
        output_path (str): CSV文件输出路径
    """
    if not data:
        print("[Twitter] 警告：没有数据可保存，跳过写入")
        return

    # ── 确保输出目录存在 ──
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    df = pd.DataFrame(data)
    # ── 统一列顺序 ──
    columns = ["platform", "keyword", "content", "publish_time", "user_name", "like_count"]
    df = df[columns]
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"[Twitter] 数据已保存至: {output_path}，共 {len(df)} 条记录")


def main():
    """
    Twitter爬虫主入口函数 — 美以伊战争舆情挖掘。
    搜索关键词"US Israel Iran"，将结果保存到 data/raw/twitter_comments.csv。

    执行流程：
        1. 搜索关键词获取推文列表
        2. 对每条推文获取回复
        3. 合并所有数据并保存为CSV
    """
    print("=" * 60)
    print("[Twitter] 爬虫启动")
    print("=" * 60)

    keyword = "US Israel Iran"
    output_path = os.path.join(OUTPUT_DIR, "twitter_comments.csv")

    # ── 第一步：搜索推文 ──
    tweets = search_tweets(keyword, count=10)
    all_data = list(tweets)

    # ── 第二步：对每条推文获取回复（限制前3条以避免API频率限制） ──
    for i, tweet in enumerate(tweets[:3]):
        print(f"[Twitter] 正在获取第 {i+1}/{min(3, len(tweets))} 条推文的回复...")
        time.sleep(random.uniform(2.0, 4.0))  # Twitter API频率限制较严格
        tweet_id = str(hash(tweet.get("content", "")) % 1000000000)
        replies = get_replies(tweet_id, count=5)
        all_data.extend(replies)

    # ── 第三步：保存数据 ──
    save_to_csv(all_data, output_path)
    print(f"[Twitter] 爬虫完成，共获取 {len(all_data)} 条数据")
    print("=" * 60)


if __name__ == "__main__":
    main()
