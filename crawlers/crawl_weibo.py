import csv
import random
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlparse

import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    StaleElementReferenceException,
)
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ==================================================
# 1. 基本配置
# ==================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_PATH = RAW_DIR / "微博_raw.csv"

KEYWORDS = [
    "伊朗 以色列 美国",
    "以色列 袭击 伊朗",
    "伊朗 反击 以色列",
    "美国 空袭 伊朗",
    "中东局势 伊朗 以色列",
]

# 搜索和采集数量控制
MAX_SEARCH_PAGES_PER_KEYWORD = 3
MAX_POSTS_PER_KEYWORD = 10
MAX_COMMENTS_PER_POST = 200
MAX_COMMENTS_TOTAL = 1500

# 每个帖子评论区滚动轮数
SCROLL_ROUNDS_PER_POST = 25

# 每轮最多尝试点击“更多评论”的次数
MAX_MORE_BUTTON_CLICKS_PER_POST = 10

# 连续多少轮没有新增评论就停止当前帖子
MAX_NO_NEW_ROUNDS = 6

MIN_DELAY = 2
MAX_DELAY = 5

STANDARD_COLUMNS = [
    "platform",
    "keyword",
    "comment_id",
    "user_name",
    "content",
    "publish_time",
    "like_count",
    "language",
    "source_url",
    "crawl_time",
]


# ==================================================
# 2. 通用工具函数
# ==================================================

def ensure_dirs():
    RAW_DIR.mkdir(parents=True, exist_ok=True)


def random_sleep(min_delay=MIN_DELAY, max_delay=MAX_DELAY):
    sleep_time = random.uniform(min_delay, max_delay)
    print(f"等待 {sleep_time:.1f} 秒...")
    time.sleep(sleep_time)


def clean_text(text):
    if text is None:
        return ""

    text = str(text)
    text = text.replace("\u200b", "")
    text = text.replace("\xa0", " ")
    text = text.replace("\n", " ")
    text = text.replace("\r", " ")
    text = text.replace("\t", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def create_driver():
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")

    driver = webdriver.Edge(options=options)
    return driver


def build_search_url(keyword, page):
    base_url = "https://s.weibo.com/weibo"
    query = quote(keyword)
    return f"{base_url}?q={query}&page={page}"


def normalize_url(url):
    if not url:
        return ""

    if url.startswith("//"):
        return "https:" + url

    if url.startswith("/"):
        return "https://weibo.com" + url

    return url


def convert_to_mobile_detail_url(url):
    """
    将 PC 微博详情页尽量转换为 m.weibo.cn/detail/xxx。
    例如：
    https://weibo.com/7488137069/R3nGo44YV?xxx
    -> https://m.weibo.cn/detail/R3nGo44YV
    """
    url = normalize_url(url)

    if not url:
        return ""

    if "m.weibo.cn/detail/" in url:
        return url.split("?")[0]

    parsed = urlparse(url)
    path = parsed.path.strip("/")

    # 常见 PC 链接：/用户id/微博短码
    parts = path.split("/")
    if len(parts) >= 2:
        possible_mblog_id = parts[-1]
        if re.fullmatch(r"[A-Za-z0-9]+", possible_mblog_id):
            return f"https://m.weibo.cn/detail/{possible_mblog_id}"

    return url


def contains_chinese(text):
    return re.search(r"[\u4e00-\u9fff]", str(text)) is not None


def parse_like_count(text):
    if not text:
        return 0

    text = clean_text(text)
    text = text.replace(",", "")

    try:
        match_wan = re.search(r"(\d+(\.\d+)?)\s*万", text)
        if match_wan:
            return int(float(match_wan.group(1)) * 10000)

        match_k = re.search(r"(\d+(\.\d+)?)\s*[kK]", text)
        if match_k:
            return int(float(match_k.group(1)) * 1000)

        if re.fullmatch(r"\d+", text):
            return int(text)

        return 0
    except ValueError:
        return 0


def is_time_text(text):
    text = clean_text(text)

    patterns = [
        r"\d{2}月\d{2}日\s+\d{2}:\d{2}",
        r"\d{1,2}月\d{1,2}日\s+\d{1,2}:\d{2}",
        r"\d{2}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2}",
        r"\d{4}-\d{2}-\d{2}",
        r"\d+分钟前",
        r"\d+小时前",
        r"刚刚",
        r"昨天\s+\d{1,2}:\d{2}",
        r"今天\s+\d{1,2}:\d{2}",
    ]

    return any(re.search(pattern, text) for pattern in patterns)


def relevance_score(text):
    text = clean_text(text)

    country_terms = [
        "美国", "美军", "以色列", "伊朗", "中东",
        "巴以", "以军", "德黑兰", "华盛顿", "以色列国防军"
    ]

    conflict_terms = [
        "战争", "冲突", "袭击", "空袭", "打击", "轰炸",
        "导弹", "反击", "军事行动", "开战", "局势", "停火",
        "报复", "防空", "核设施", "爆炸", "袭击"
    ]

    country_count = sum(1 for word in country_terms if word in text)
    conflict_count = sum(1 for word in conflict_terms if word in text)

    return country_count * 2 + conflict_count


def is_related_to_topic(text):
    text = clean_text(text)

    if not text:
        return False

    if relevance_score(text) >= 3:
        return True

    # 搜索词本身已经比较精准，放宽一点，避免收集不到帖子
    if "伊朗" in text and "以色列" in text:
        return True

    if "美国" in text and "伊朗" in text:
        return True

    return False


# ==================================================
# 3. 评论识别规则
# ==================================================

INVALID_UI_EXACT = {
    "评论",
    "转发",
    "赞",
    "点赞",
    "分享",
    "收藏",
    "登录",
    "发布",
    "写评论",
    "查看更多",
    "展开",
    "收起",
    "快来抢沙发",
    "还没有人评论",
    "热门",
    "认证用户",
    "关注的人",
    "投诉",
    "回复",
    "全部评论",
    "按热度",
    "按时间",
    "加载中",
    "查看更多评论",
}

INVALID_UI_PHRASES = [
    "微博正文",
    "相关推荐",
    "热门微博",
    "同时转发",
    "查看更多评论",
    "展开更多评论",
    "加载中",
    "暂无评论",
    "登录后查看更多",
    "客户端下载",
    "微博热搜",
    "广告",
    "举报",
    "转发理由",
    "后面还有",
    "点击查看",
    "条评论",
    "同时转发到我的微博",
    "认证用户",
    "关注的人",
    "只看博主",
    "相关讨论",
    "打开微博",
    "用微博扫码",
]


def is_ui_or_noise(text):
    text = clean_text(text)

    if not text:
        return True

    if text in INVALID_UI_EXACT:
        return True

    for phrase in INVALID_UI_PHRASES:
        if phrase in text:
            return True

    if is_time_text(text):
        return True

    # 过滤来源行，比如“06月08日 09:19 来自湖北”
    if "来自" in text and re.search(r"\d{1,2}[:：]\d{2}", text):
        return True

    if re.fullmatch(r"来自[\u4e00-\u9fff]{2,8}", text):
        return True

    if re.fullmatch(r"\d+", text):
        return True

    return False


def looks_like_user_name(text):
    text = clean_text(text)

    if not text:
        return False

    if len(text) > 30:
        return False

    if is_ui_or_noise(text):
        return False

    if re.search(r"\d{1,2}[-/]\d{1,2}", text):
        return False

    if re.search(r"\d{1,2}[:：]\d{2}", text):
        return False

    if re.fullmatch(r"\d+", text):
        return False

    invalid_prefixes = [
        "突发",
        "快讯",
        "消息",
        "报道称",
        "据悉",
        "外媒",
        "央视新闻",
        "环球网",
        "观察者网",
        "人民日报",
        "微博正文",
        "编辑",
        "来源",
        "主持人",
    ]

    for word in invalid_prefixes:
        if text == word or text.startswith(word):
            return False

    bad_chars = ["，", "。", "！", "？", "；", "、"]
    if any(ch in text for ch in bad_chars):
        return False

    return True


def is_valid_comment_content(text):
    text = clean_text(text)

    if not text:
        return False

    if len(text) < 3:
        return False

    if len(text) > 220:
        return False

    if not contains_chinese(text):
        return False

    if is_ui_or_noise(text):
        return False

    useful_text = re.sub(r"[\W_]+", "", text, flags=re.UNICODE)
    if len(useful_text) < 3:
        return False

    return True


def split_colon_comment(line):
    """
    解析“用户名：评论内容”格式。
    """
    line = clean_text(line)

    if "：" in line:
        parts = line.split("：", 1)
    elif ":" in line:
        parts = line.split(":", 1)
    else:
        return "", ""

    user_name = clean_text(parts[0])
    content = clean_text(parts[1])

    if not looks_like_user_name(user_name):
        return "", ""

    if not is_valid_comment_content(content):
        return "", ""

    return user_name, content


def is_similar_to_post_content(content, post_content):
    content = clean_text(content)
    post_content = clean_text(post_content)

    if not content or not post_content:
        return False

    if content in post_content:
        return True

    if post_content in content:
        return True

    if len(content) >= 20 and content[:20] in post_content:
        return True

    if len(post_content) >= 20 and post_content[:20] in content:
        return True

    return False


# ==================================================
# 4. 搜索页收集帖子链接
# ==================================================

def get_weibo_cards(driver):
    selectors = [
        "div.card-wrap[action-type='feed_list_item']",
        "div[action-type='feed_list_item']",
        "div.card-wrap",
    ]

    for selector in selectors:
        try:
            cards = driver.find_elements(By.CSS_SELECTOR, selector)
            if cards:
                return cards
        except Exception:
            continue

    return []


def extract_post_content(card):
    selectors = [
        "p.txt",
        ".txt",
        "div[node-type='feed_list_content']",
    ]

    for selector in selectors:
        try:
            nodes = card.find_elements(By.CSS_SELECTOR, selector)
            if nodes:
                return clean_text(nodes[-1].text)
        except Exception:
            continue

    return ""


def extract_post_url(card):
    selectors = [
        "p.from a",
        ".from a",
        "a[action-type='feed_list_item_date']",
    ]

    for selector in selectors:
        try:
            node = card.find_element(By.CSS_SELECTOR, selector)
            url = node.get_attribute("href")
            if url:
                return normalize_url(url)
        except Exception:
            continue

    return ""


def collect_post_links_from_search(driver, keyword):
    post_infos = []
    seen_urls = set()

    for page in range(1, MAX_SEARCH_PAGES_PER_KEYWORD + 1):
        search_url = build_search_url(keyword, page)

        print("=" * 60)
        print(f"打开搜索页：{search_url}")

        try:
            driver.get(search_url)
        except WebDriverException as e:
            print(f"搜索页打开失败：{e}")
            continue

        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
            )
        except TimeoutException:
            print("搜索页加载超时，跳过。")
            continue

        random_sleep()

        cards = get_weibo_cards(driver)
        print(f"搜索页检测到微博卡片：{len(cards)} 条")

        candidate_posts = []

        for card in cards:
            try:
                post_content = extract_post_content(card)
                post_url = extract_post_url(card)
            except StaleElementReferenceException:
                continue

            if not post_content or not post_url:
                continue

            if post_url in seen_urls:
                continue

            score = relevance_score(post_content)

            candidate_posts.append({
                "keyword": keyword,
                "post_url": post_url,
                "mobile_url": convert_to_mobile_detail_url(post_url),
                "post_content": post_content,
                "score": score,
            })

        # 优先选择相关性高的帖子
        candidate_posts.sort(key=lambda x: x["score"], reverse=True)

        for post in candidate_posts:
            if len(post_infos) >= MAX_POSTS_PER_KEYWORD:
                break

            if not is_related_to_topic(post["post_content"]):
                continue

            seen_urls.add(post["post_url"])
            post_infos.append(post)

            print(f"收集到相关帖子：{post['post_url']}")
            print(f"移动端链接：{post['mobile_url']}")
            print(f"正文摘要：{post['post_content'][:80]}...")

        if len(post_infos) >= MAX_POSTS_PER_KEYWORD:
            break

    return post_infos


# ==================================================
# 5. 页面操作
# ==================================================

def click_comment_tab_if_possible(driver):
    xpaths = [
        "//*[normalize-space()='评论']",
        "//*[contains(text(), '评论') and string-length(normalize-space()) <= 10]",
        "//*[contains(text(), '全部评论')]",
    ]

    for xpath in xpaths:
        try:
            elements = driver.find_elements(By.XPATH, xpath)
            for element in elements:
                try:
                    if element.is_displayed():
                        driver.execute_script(
                            "arguments[0].scrollIntoView({block: 'center'});",
                            element
                        )
                        random_sleep(1, 2)
                        driver.execute_script("arguments[0].click();", element)
                        random_sleep(1, 2)
                        return True
                except Exception:
                    continue
        except Exception:
            continue

    return False


def click_more_buttons(driver):
    """
    尝试点击当前页面中所有可能的“更多评论”按钮。
    """
    keywords = [
        "后面还有",
        "点击查看",
        "查看更多评论",
        "展开更多评论",
        "查看全部评论",
        "更多评论",
        "加载更多",
        "展开",
    ]

    clicked_count = 0
    old_handles = set(driver.window_handles)

    for word in keywords:
        try:
            elements = driver.find_elements(By.XPATH, f"//*[contains(text(), '{word}')]")
        except Exception:
            continue

        for element in elements:
            try:
                text = clean_text(element.text)

                if not text:
                    continue

                if not element.is_displayed():
                    continue

                if text in ["展开", "展开全文"] and clicked_count >= 2:
                    continue

                print(f"尝试点击按钮：{text[:40]}")

                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});",
                    element
                )
                random_sleep(1, 2)
                driver.execute_script("arguments[0].click();", element)
                random_sleep(2, 4)

                new_handles = set(driver.window_handles)
                if len(new_handles) > len(old_handles):
                    new_window = list(new_handles - old_handles)[0]
                    driver.switch_to.window(new_window)
                    print("检测到新窗口，已切换。")
                    old_handles = new_handles

                clicked_count += 1

            except Exception:
                continue

    return clicked_count


def scroll_down_incrementally(driver):
    """
    不直接跳到底，避免虚拟列表丢失评论。
    """
    driver.execute_script("window.scrollBy(0, Math.floor(window.innerHeight * 0.8));")


def scroll_to_comment_area(driver):
    for _ in range(5):
        scroll_down_incrementally(driver)
        random_sleep(1, 2)


# ==================================================
# 6. 评论提取
# ==================================================

def collect_visible_lines(driver):
    try:
        body_text = driver.execute_script("return document.body.innerText;")
    except Exception:
        return []

    lines = []

    for raw_line in str(body_text).splitlines():
        line = clean_text(raw_line)
        if line:
            lines.append(line)

    return lines


def find_publish_time_nearby(lines, index):
    for offset in range(1, 6):
        if index + offset >= len(lines):
            break

        candidate = clean_text(lines[index + offset])

        if is_time_text(candidate):
            return candidate

        if "来自" in candidate and re.search(r"\d{1,2}[:：]\d{2}", candidate):
            return candidate

    return ""


def find_like_count_nearby(lines, index):
    for offset in range(1, 10):
        if index + offset >= len(lines):
            break

        candidate = clean_text(lines[index + offset])

        if candidate in ["赞", "点赞", "投诉", "回复", "评论"]:
            continue

        if is_time_text(candidate):
            continue

        if re.fullmatch(r"\d+", candidate):
            return int(candidate)

        if re.fullmatch(r"\d+(\.\d+)?万", candidate):
            return parse_like_count(candidate)

    return 0


def add_comment(comments, seen_contents, keyword, post_url, user_name, content, publish_time="", like_count=0):
    content = clean_text(content)
    user_name = clean_text(user_name)

    if not content:
        return False

    if content in seen_contents:
        return False

    seen_contents.add(content)

    comments.append({
        "platform": "weibo",
        "keyword": keyword,
        "comment_id": f"weibo_comment_{abs(hash(post_url + content))}",
        "user_name": user_name if user_name else "unknown",
        "content": content,
        "publish_time": publish_time,
        "like_count": like_count,
        "language": "zh",
        "source_url": post_url,
        "crawl_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })

    return True


def extract_comments_from_lines(lines, keyword, post_url, post_content, seen_contents):
    """
    同时支持两种格式：
    1. 用户名：评论内容
    2. 用户名
       评论内容
       时间
    """
    new_comments = []

    for index, line in enumerate(lines):
        if len(seen_contents) >= MAX_COMMENTS_PER_POST:
            break

        line = clean_text(line)

        # 格式一：用户名：评论内容
        if "：" in line or ":" in line:
            user_name, content = split_colon_comment(line)

            if content and not is_similar_to_post_content(content, post_content):
                publish_time = find_publish_time_nearby(lines, index)
                like_count = find_like_count_nearby(lines, index)

                temp = []
                added = add_comment(
                    temp,
                    seen_contents,
                    keyword,
                    post_url,
                    user_name,
                    content,
                    publish_time,
                    like_count,
                )

                if added:
                    new_comments.extend(temp)

        # 格式二：用户名一行，下一行是评论内容
        if looks_like_user_name(line):
            if index + 1 < len(lines):
                possible_content = clean_text(lines[index + 1])

                if is_valid_comment_content(possible_content):
                    if not is_similar_to_post_content(possible_content, post_content):
                        publish_time = find_publish_time_nearby(lines, index + 1)
                        like_count = find_like_count_nearby(lines, index + 1)

                        temp = []
                        added = add_comment(
                            temp,
                            seen_contents,
                            keyword,
                            post_url,
                            line,
                            possible_content,
                            publish_time,
                            like_count,
                        )

                        if added:
                            new_comments.extend(temp)

    return new_comments


def scroll_and_collect_comments(driver, keyword, post_url, post_content, post_index):
    all_comments = []
    seen_contents = set()
    no_new_rounds = 0
    total_more_clicks = 0

    # 初始提取
    lines = collect_visible_lines(driver)
    new_comments = extract_comments_from_lines(
        lines,
        keyword,
        post_url,
        post_content,
        seen_contents,
    )
    all_comments.extend(new_comments)
    print(f"初始区域新增评论：{len(new_comments)} 条，累计 {len(all_comments)} 条")

    for round_index in range(1, SCROLL_ROUNDS_PER_POST + 1):
        if len(all_comments) >= MAX_COMMENTS_PER_POST:
            break

        # 每几轮尝试点击一次更多按钮
        if total_more_clicks < MAX_MORE_BUTTON_CLICKS_PER_POST:
            clicked = click_more_buttons(driver)
            total_more_clicks += clicked

        before_count = len(all_comments)

        scroll_down_incrementally(driver)
        random_sleep(2, 4)

        lines = collect_visible_lines(driver)
        new_comments = extract_comments_from_lines(
            lines,
            keyword,
            post_url,
            post_content,
            seen_contents,
        )

        all_comments.extend(new_comments)
        added = len(all_comments) - before_count

        print(
            f"第 {round_index} 轮滚动：新增 {added} 条，"
            f"累计 {len(all_comments)} 条，已点击更多 {total_more_clicks} 次"
        )

        if added == 0:
            no_new_rounds += 1
        else:
            no_new_rounds = 0

        if no_new_rounds >= MAX_NO_NEW_ROUNDS:
            print("连续多轮没有新增评论，停止当前帖子。")
            break

    return all_comments[:MAX_COMMENTS_PER_POST]


# ==================================================
# 7. 爬取单个帖子评论
# ==================================================

def crawl_comments_from_post(driver, post_info, post_index):
    keyword = post_info["keyword"]
    post_url = post_info["post_url"]
    mobile_url = post_info.get("mobile_url") or convert_to_mobile_detail_url(post_url)
    post_content = post_info.get("post_content", "")

    print("-" * 60)
    print(f"打开帖子详情页：{post_url}")
    print(f"尝试使用移动端详情页：{mobile_url}")

    try:
        driver.get(mobile_url)
    except WebDriverException as e:
        print(f"移动端详情页打开失败，改用原链接：{e}")
        try:
            driver.get(post_url)
        except WebDriverException as e2:
            print(f"帖子详情页打开失败：{e2}")
            return []

    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
        )
    except TimeoutException:
        print("帖子详情页加载超时，跳过。")
        return []

    random_sleep()

    click_comment_tab_if_possible(driver)
    scroll_to_comment_area(driver)

    comments = scroll_and_collect_comments(
        driver,
        keyword,
        mobile_url,
        post_content,
        post_index,
    )

    print(f"当前帖子最终提取评论：{len(comments)} 条")

    return comments


# ==================================================
# 8. 保存数据
# ==================================================

def save_records(records):
    df = pd.DataFrame(records, columns=STANDARD_COLUMNS)

    df.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
        quoting=csv.QUOTE_ALL,
    )

    print()
    print("微博评论采集完成！")
    print(f"共采集评论：{len(df)} 条")
    print(f"保存位置：{OUTPUT_PATH}")


# ==================================================
# 9. 主流程
# ==================================================

def crawl_weibo():
    ensure_dirs()

    driver = create_driver()
    all_records = []
    global_seen_contents = set()

    try:
        print("将使用 Edge 打开微博。")
        print("如果需要登录，请在浏览器中手动登录。")
        print("如果出现验证码或安全验证，能正常通过就继续；不能通过就停止，不要绕过。")
        print()

        first_url = build_search_url(KEYWORDS[0], 1)
        driver.get(first_url)

        input("请先在 Edge 中完成微博登录，并确认能看到搜索结果。完成后回到这里按 Enter：")

        all_post_infos = []
        seen_post_urls = set()

        for keyword in KEYWORDS:
            post_infos = collect_post_links_from_search(driver, keyword)

            for post_info in post_infos:
                post_url = post_info["post_url"]

                if post_url in seen_post_urls:
                    continue

                seen_post_urls.add(post_url)
                all_post_infos.append(post_info)

        print()
        print(f"共收集到相关帖子链接：{len(all_post_infos)} 个")

        for post_index, post_info in enumerate(all_post_infos, start=1):
            if len(all_records) >= MAX_COMMENTS_TOTAL:
                break

            comments = crawl_comments_from_post(driver, post_info, post_index)

            for comment in comments:
                if len(all_records) >= MAX_COMMENTS_TOTAL:
                    break

                content = comment["content"]

                if content in global_seen_contents:
                    continue

                global_seen_contents.add(content)
                all_records.append(comment)

            print(f"当前累计评论数量：{len(all_records)}")
            random_sleep()

    finally:
        driver.quit()

    if not all_records:
        print("没有采集到评论。")
        return

    save_records(all_records)


if __name__ == "__main__":
    crawl_weibo()