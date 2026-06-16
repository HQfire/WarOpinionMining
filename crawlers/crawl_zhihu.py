import csv
import time
import random
import requests
from datetime import datetime
from urllib.parse import urlencode, urlparse, parse_qs

# ==================== 配置区域 ====================

# 搜索关键词列表，围绕 "美以伊战争"
SEARCH_KEYWORDS = [
    "美以伊战争",
    "伊朗反击美以",
    "美以打伊朗",
    "美以伊战争 中国网友",
    "美以伊 战争 看法"
]

# 每个关键词搜索的问题数量（搜索API每页约20条）
QUESTIONS_PER_KEYWORD = 3

# 每个问题获取的回答数量（每页20条）
ANSWERS_PER_QUESTION = 2

# 每个回答获取的评论页数（每页约20条）
COMMENT_PAGES_PER_ANSWER = 3

# 输出文件名
OUTPUT_CSV = "zhihu_comments.csv"

# 请求延迟（秒）
REQUEST_DELAY_MIN = 1.5
REQUEST_DELAY_MAX = 3.5

# ==================== 请求头配置 ====================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.zhihu.com/",
    "Origin": "https://www.zhihu.com",
    "Connection": "keep-alive",
}

# ==================== Cookie 配置（重要！） ====================

# TODO: 请替换为你的知乎 Cookie
# 获取方式：登录 zhihu.com → F12 → 应用程序(Application) → Cookies → 复制 "z_c0" 的值
COOKIES = {
    "z_c0": "Mi4xcDlUNVVRQUFBQUJlaGxUUExWbndHeVlBQUFCZ0FsVk5CcTRlYXdBeEFpdHM3R2lqRENxb0JIamx6M01idl9QNUd3|182ce03affe82ab22c07ecb09ec38a20d051d9c943d0c3c318e5509b3e503070"  # 必填！否则无法获取完整数据
}


# ==================== 工具函数 ====================

def trans_date(timestamp):
    """将时间戳转换为日期字符串"""
    if not timestamp:
        return ""
    try:
        if isinstance(timestamp, int):
            time_array = time.localtime(timestamp)
            return time.strftime("%Y-%m-%d %H:%M:%S", time_array)
        return str(timestamp)
    except:
        return ""


def safe_get(data, *keys, default=""):
    """安全地从嵌套字典中获取值"""
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key, {})
        else:
            return default
    return data if data is not None else default


def request_with_retry(url, params=None, max_retries=3):
    """带重试的请求函数"""
    for attempt in range(max_retries):
        try:
            response = requests.get(
                url,
                params=params,
                headers=HEADERS,
                cookies=COOKIES,
                timeout=15
            )
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 403:
                print(f"  ⚠️ 403 禁止访问，可能是Cookie失效，请更新z_c0")
                return None
            else:
                print(f"  ⚠️ 请求失败，状态码: {response.status_code}")
                time.sleep(2 ** attempt)  # 指数退避
        except requests.exceptions.RequestException as e:
            print(f"  ⚠️ 请求异常 (尝试 {attempt + 1}/{max_retries}): {e}")
            time.sleep(2 ** attempt)
    return None


# ==================== 核心爬虫函数 ====================

def search_questions(keyword, limit=20):
    """
    搜索与关键词相关的问题
    API: https://www.zhihu.com/api/v4/search_v3
    """
    questions = []
    url = "https://www.zhihu.com/api/v4/search_v3"
    params = {
        "t": "general",
        "q": keyword,
        "correction": "1",
        "offset": 0,
        "limit": limit,
        "lc_idx": 0,
        "show_all_topics": "0",
        "search_source": "Normal"
    }

    print(f"🔍 搜索关键词: {keyword}")
    data = request_with_retry(url, params)

    if not data:
        return questions

    # 解析搜索结果
    for item in data.get("data", []):
        if item.get("type") == "search_result":
            obj = item.get("object", {})
            if obj.get("type") == "question":
                question_id = obj.get("id")
                title = obj.get("title", "")
                if question_id:
                    questions.append({
                        "id": question_id,
                        "title": title,
                        "answer_count": obj.get("answer_count", 0)
                    })

    print(f"  找到 {len(questions)} 个相关问题")
    return questions


def get_answers(question_id, limit=20):
    """
    获取某个问题的回答列表
    API: https://www.zhihu.com/api/v4/questions/{qid}/answers
    """
    answers = []
    url = f"https://www.zhihu.com/api/v4/questions/{question_id}/answers"
    params = {
        "limit": limit,
        "offset": 0,
        "order": "default"  # 按默认排序（综合）
    }

    data = request_with_retry(url, params)
    if not data:
        return answers

    for item in data.get("data", []):
        answer_id = item.get("id")
        if answer_id:
            answers.append({
                "id": answer_id,
                "question_id": question_id,
                "author_name": safe_get(item, "author", "name"),
                "content": safe_get(item, "content", "")[:100],  # 截取前100字作为上下文
                "voteup_count": item.get("voteup_count", 0),
                "comment_count": item.get("comment_count", 0)
            })

    return answers


def get_comments(answer_id, max_pages=3):
    """
    获取某个回答的评论（包含根评论和子评论）
    API: https://www.zhihu.com/api/v4/answers/{aid}/root_comments
    """
    all_comments = []
    offset = 0
    limit = 20

    for page in range(max_pages):
        url = f"https://www.zhihu.com/api/v4/answers/{answer_id}/root_comments"
        params = {
            "order": "normal",
            "limit": limit,
            "offset": offset,
            "status": "open"
        }

        data = request_with_retry(url, params)
        if not data:
            break

        comments = data.get("data", [])
        if not comments:
            break

        # 处理每条根评论
        for comment in comments:
            # 提取根评论信息
            author = comment.get("author", {})
            comment_info = {
                "comment_text": comment.get("content", ""),
                "created_at": trans_date(comment.get("created_time")),
                "user_nickname": author.get("name", ""),
                "like_count": comment.get("vote_count", 0),
                "reply_to": "",  # 根评论没有回复对象
                "is_child": False
            }
            all_comments.append(comment_info)

            # 处理子评论（二级评论）
            child_comments = comment.get("child_comments", [])
            for child in child_comments:
                child_author = child.get("author", {})
                child_info = {
                    "comment_text": child.get("content", ""),
                    "created_at": trans_date(child.get("created_time")),
                    "user_nickname": child_author.get("name", ""),
                    "like_count": child.get("vote_count", 0),
                    "reply_to": safe_get(child, "reply_to_author", "name") or "",
                    "is_child": True
                }
                all_comments.append(child_info)

        # 更新分页参数
        paging = data.get("paging", {})
        next_url = paging.get("next")
        if not next_url:
            break
        parsed = urlparse(next_url)
        offset = int(parse_qs(parsed.query).get("offset", [0])[0])

        # 随机延迟
        time.sleep(random.uniform(0.5, 1.5))

    return all_comments


# ==================== 主程序 ====================

def main():
    print("=" * 60)
    print("🚀 知乎评论爬虫启动 - 美以伊战争专题")
    print(f"📅 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 检查Cookie是否配置
    if COOKIES.get("z_c0") == "你的z_c0值":
        print("\n⚠️ 警告: 未配置有效的 z_c0 Cookie！")
        print("   请打开 zhihu.com，按 F12 → Application → Cookies → 复制 z_c0 的值")
        print("   然后粘贴到代码中 COOKIES 字典的 'z_c0' 字段\n")
        response = input("是否继续尝试？（可能无法获取数据）[y/N]: ")
        if response.lower() != 'y':
            print("已退出")
            return

    all_comments = []
    processed_answers = set()  # 避免重复处理同一个回答

    # 遍历关键词
    for keyword in SEARCH_KEYWORDS:
        print(f"\n{'=' * 50}")
        print(f"📌 处理关键词: {keyword}")

        # 1. 搜索问题
        questions = search_questions(keyword, QUESTIONS_PER_KEYWORD * 20)
        if not questions:
            print(f"  ⚠️ 未找到相关问题，跳过")
            continue

        # 2. 遍历问题
        for q_idx, question in enumerate(questions[:QUESTIONS_PER_KEYWORD]):
            qid = question["id"]
            qtitle = question["title"][:40] if question["title"] else f"问题{qid}"
            print(f"\n  📝 问题 [{q_idx + 1}/{min(len(questions), QUESTIONS_PER_KEYWORD)}]: {qtitle}")

            # 3. 获取回答
            answers = get_answers(qid, ANSWERS_PER_QUESTION * 20)
            if not answers:
                print(f"    该问题暂无回答")
                continue

            # 4. 遍历回答
            for a_idx, answer in enumerate(answers[:ANSWERS_PER_QUESTION]):
                aid = answer["id"]

                # 避免重复处理
                if aid in processed_answers:
                    continue
                processed_answers.add(aid)

                author = answer["author_name"]
                print(
                    f"    回答 [{a_idx + 1}/{min(len(answers), ANSWERS_PER_QUESTION)}] 作者: {author} (评论数: {answer['comment_count']})")

                # 5. 获取评论
                comments = get_comments(aid, COMMENT_PAGES_PER_ANSWER)

                if comments:
                    # 添加回答和问题的上下文信息
                    for c in comments:
                        c["answer_id"] = aid
                        c["answer_author"] = author
                        c["question_title"] = qtitle
                        c["keyword"] = keyword

                    all_comments.extend(comments)
                    print(f"      获取 {len(comments)} 条评论 (累计: {len(all_comments)})")
                else:
                    print(f"      该回答暂无评论")

                # 随机延迟，模拟人类浏览
                time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))

                # 达到目标数量提前结束
                if len(all_comments) >= 1000:
                    print(f"\n🎯 已达到目标数量 {len(all_comments)} 条评论，停止爬取")
                    break

            if len(all_comments) >= 1000:
                break

        if len(all_comments) >= 1000:
            break

    # 6. 保存结果
    print("\n" + "=" * 60)
    print(f"📊 共收集 {len(all_comments)} 条评论")

    if all_comments:
        # 保存为CSV
        fieldnames = [
            "comment_text", "created_at", "user_nickname", "like_count",
            "reply_to", "is_child", "answer_id", "answer_author",
            "question_title", "keyword"
        ]

        with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_comments)

        print(f"✅ 数据已保存至: {OUTPUT_CSV}")

        # 统计信息
        root_count = sum(1 for c in all_comments if not c.get("is_child"))
        child_count = len(all_comments) - root_count
        print(f"   - 一级评论: {root_count} 条")
        print(f"   - 二级评论: {child_count} 条")
    else:
        print("⚠️ 未收集到任何评论数据")

    print(f"🏁 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


if __name__ == "__main__":
    main()