"""
Bilibili 评论爬虫（Selenium 手动登录 + 评论 API 优先版）

修复点：
1. 补齐 urllib.parse 导入，避免搜索 URL 构造时报 NameError。
2. 搜索页改用 video 搜索，并更稳健地提取 BV 视频链接。
3. 评论不再依赖页面 CSS 类名，优先通过 B 站评论 API 抓取。
4. API 失败时保留 Selenium DOM 兜底，方便定位风控或页面结构变化。

使用：
    python crawlers/crawl_bilibili.py

依赖：
    pip install selenium requests
"""

import csv
import hashlib
import json
import random
import re
import time
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

import requests
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


# ==================================================
# 1. 基本配置
# ==================================================

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent if HERE.name.lower() == "crawlers" else HERE

RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_PATH = RAW_DIR / "bilibili_raw.csv"

KEYWORDS = [
    "伊朗 以色列 美国",
    "以色列 袭击 伊朗",
    "伊朗 反击 以色列",
    "美国 空袭 伊朗",
    "中东局势 伊朗 以色列",
]

MAX_SEARCH_PAGES_PER_KEYWORD = 2
MAX_VIDEOS_PER_KEYWORD = 8
MAX_COMMENTS_PER_VIDEO = 200
MAX_COMMENTS_TOTAL = 1500

SCROLL_ROUNDS_PER_VIDEO = 20
MAX_NO_NEW_ROUNDS = 5

MIN_DELAY = 2
MAX_DELAY = 5

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

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

# WBI 签名用混淆表，用于新版评论接口兜底
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32,
    15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19,
    29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61,
    26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63,
    57, 62, 11, 36, 20, 34, 44, 52,
]


# ==================================================
# 2. 通用工具函数
# ==================================================

def ensure_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)


def random_sleep(min_delay: float = MIN_DELAY, max_delay: float = MAX_DELAY) -> None:
    sleep_time = random.uniform(min_delay, max_delay)
    print(f"  等待 {sleep_time:.1f} 秒...")
    time.sleep(sleep_time)


def clean_text(text: object) -> str:
    if text is None:
        return ""

    text = str(text)
    text = text.replace("\u200b", "").replace("\xa0", " ")
    text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def detect_language(text: str) -> str:
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh"
    if re.match(r"^[a-zA-Z\s\d.,!?;:'\"()\-_/]+$", text):
        return "en"
    return "other"


def make_comment_id(video_id: str, cid: object) -> str:
    raw = f"bilibili_{video_id}_{cid}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def timestamp_to_str(ts: object) -> str:
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return clean_text(ts)


def extract_bvid(url_or_text: str) -> Optional[str]:
    match = re.search(r"BV[0-9A-Za-z]+", url_or_text or "")
    return match.group(0) if match else None


def normalize_video_url(raw_url: str) -> Optional[str]:
    if not raw_url:
        return None

    if raw_url.startswith("//"):
        raw_url = "https:" + raw_url

    bvid = extract_bvid(raw_url)
    if not bvid:
        return None

    return f"https://www.bilibili.com/video/{bvid}"


def load_existing_comment_ids() -> Set[str]:
    ids: Set[str] = set()

    if not OUTPUT_PATH.exists():
        return ids

    try:
        with open(OUTPUT_PATH, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cid = row.get("comment_id")
                if cid:
                    ids.add(cid)
    except Exception as exc:
        print(f"读取已有 CSV 失败，将继续追加：{exc}")

    return ids


def save_to_csv(comments: List[Dict[str, object]], append: bool = True) -> None:
    if not comments:
        return

    mode = "a" if append and OUTPUT_PATH.exists() else "w"

    with open(OUTPUT_PATH, mode, newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=STANDARD_COLUMNS)

        if mode == "w":
            writer.writeheader()

        writer.writerows(comments)

    print(f"已保存 {len(comments)} 条评论至 {OUTPUT_PATH}")

# ==================================================
# 3. 浏览器和 requests 会话
# ==================================================

def create_driver() -> webdriver.Edge:
    options = Options()

    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_argument(f"--user-agent={USER_AGENT}")

    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Edge(options=options)
    driver.set_page_load_timeout(45)

    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                    Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
                """
            },
        )
    except Exception:
        pass

    return driver


def build_session_from_driver(driver: webdriver.Edge) -> requests.Session:
    session = requests.Session()

    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Origin": "https://www.bilibili.com",
            "Referer": "https://www.bilibili.com/",
            "Connection": "keep-alive",
        }
    )

    for cookie in driver.get_cookies():
        try:
            session.cookies.set(
                cookie["name"],
                cookie["value"],
                domain=cookie.get("domain") or ".bilibili.com",
                path=cookie.get("path") or "/",
            )
        except Exception:
            continue

    return session


# ==================================================
# 4. 搜索视频
# ==================================================

def open_url_with_retry(driver: webdriver.Edge, url: str, retry: int = 2) -> bool:
    for i in range(retry + 1):
        try:
            driver.get(url)
            return True

        except TimeoutException:
            print(f"  页面加载超时，第 {i + 1} 次重试：{url}")
            try:
                driver.execute_script("window.stop();")
            except Exception:
                pass

        except WebDriverException as exc:
            print(f"  页面打开失败：{exc}")
            random_sleep(2, 4)

    return False


def collect_video_urls_from_search(driver: webdriver.Edge, keyword: str) -> List[str]:
    video_urls: List[str] = []
    seen: Set[str] = set()

    for page in range(1, MAX_SEARCH_PAGES_PER_KEYWORD + 1):
        search_url = (
            "https://search.bilibili.com/video?"
            + urllib.parse.urlencode({"keyword": keyword, "page": page})
        )

        print(f"  打开搜索页 {page}: {search_url}")

        if not open_url_with_retry(driver, search_url):
            continue

        random_sleep(3, 5)

        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "a[href*='/video/'], a[href*='BV']")
                )
            )
        except TimeoutException:
            print("  搜索页没有等到视频链接")

        for _ in range(3):
            driver.execute_script("window.scrollBy(0, document.body.scrollHeight / 3);")
            random_sleep(1, 2)

        hrefs = driver.execute_script(
            """
            return Array.from(document.querySelectorAll('a[href]'))
                .map(a => a.href || a.getAttribute('href'))
                .filter(Boolean);
            """
        )

        for href in hrefs:
            normalized = normalize_video_url(href)

            if normalized and normalized not in seen:
                seen.add(normalized)
                video_urls.append(normalized)

                if len(video_urls) >= MAX_VIDEOS_PER_KEYWORD:
                    return video_urls

        print(f"  当前累计视频链接：{len(video_urls)}")

    return video_urls


# ==================================================
# 5. B 站接口：视频 aid 和评论
# ==================================================

def get_aid_by_bvid(session: requests.Session, bvid: str) -> Optional[int]:
    url = "https://api.bilibili.com/x/web-interface/view"

    try:
        resp = session.get(url, params={"bvid": bvid}, timeout=15)
        data = resp.json()
    except Exception as exc:
        print(f"    获取 aid 失败：{exc}")
        return None

    if data.get("code") != 0:
        print(
            f"    获取 aid 接口异常：code={data.get('code')} "
            f"message={data.get('message')}"
        )
        return None

    aid = (data.get("data") or {}).get("aid")

    try:
        return int(aid)
    except Exception:
        print(f"    aid 为空或格式异常：{aid}")
        return None


def parse_reply_item(
    reply: Dict[str, object],
    *,
    keyword: str,
    video_id: str,
    video_url: str,
    crawl_time: str,
) -> Optional[Dict[str, object]]:
    content_obj = reply.get("content") or {}
    member_obj = reply.get("member") or {}

    content = clean_text(
        content_obj.get("message") if isinstance(content_obj, dict) else ""
    )

    if len(content) < 2:
        return None

    rpid = (
        reply.get("rpid_str")
        or reply.get("rpid")
        or reply.get("id")
        or hashlib.md5(content.encode("utf-8")).hexdigest()
    )

    uname = member_obj.get("uname") if isinstance(member_obj, dict) else ""
    like = reply.get("like") or 0
    ctime = reply.get("ctime")

    return {
        "platform": "bilibili",
        "keyword": keyword,
        "comment_id": make_comment_id(video_id, rpid),
        "user_name": clean_text(uname),
        "content": content,
        "publish_time": timestamp_to_str(ctime),
        "like_count": int(like or 0),
        "language": detect_language(content),
        "source_url": video_url,
        "crawl_time": crawl_time,
    }


def flatten_replies(
    replies: Iterable[Dict[str, object]],
    *,
    keyword: str,
    video_id: str,
    video_url: str,
    crawl_time: str,
    max_count: int,
) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    seen: Set[str] = set()

    def add_one(reply: Dict[str, object]) -> None:
        if len(rows) >= max_count:
            return

        row = parse_reply_item(
            reply,
            keyword=keyword,
            video_id=video_id,
            video_url=video_url,
            crawl_time=crawl_time,
        )

        if not row:
            return

        if row["comment_id"] in seen:
            return

        seen.add(str(row["comment_id"]))
        rows.append(row)

    for reply in replies or []:
        if len(rows) >= max_count:
            break

        add_one(reply)

        child_replies = reply.get("replies") if isinstance(reply, dict) else None

        if isinstance(child_replies, list):
            for child in child_replies:
                if len(rows) >= max_count:
                    break
                add_one(child)

    return rows


def fetch_comments_by_old_api(
    session: requests.Session,
    *,
    aid: int,
    bvid: str,
    keyword: str,
    video_url: str,
    crawl_time: str,
    max_comments: int,
) -> Tuple[List[Dict[str, object]], Optional[str]]:
    """
    旧评论接口优先。
    优点：简单、稳定时很好用。
    缺点：部分视频或环境下可能被限制。
    """
    all_rows: List[Dict[str, object]] = []
    seen_ids: Set[str] = set()
    last_error: Optional[str] = None

    for pn in range(1, 1000):
        if len(all_rows) >= max_comments:
            break

        params = {
            "type": 1,
            "oid": aid,
            "sort": 2,
            "pn": pn,
            "ps": 20,
        }

        try:
            resp = session.get(
                "https://api.bilibili.com/x/v2/reply",
                params=params,
                headers={"Referer": video_url},
                timeout=15,
            )
            data = resp.json()
        except Exception as exc:
            last_error = f"旧评论接口请求失败：{exc}"
            break

        if data.get("code") != 0:
            last_error = (
                f"旧评论接口异常：code={data.get('code')} "
                f"message={data.get('message')}"
            )
            break

        data_obj = data.get("data") or {}
        replies = data_obj.get("replies") or []

        if not replies:
            break

        rows = flatten_replies(
            replies,
            keyword=keyword,
            video_id=bvid,
            video_url=video_url,
            crawl_time=crawl_time,
            max_count=max_comments - len(all_rows),
        )

        for row in rows:
            cid = str(row["comment_id"])

            if cid not in seen_ids:
                seen_ids.add(cid)
                all_rows.append(row)

        page_info = data_obj.get("page") or {}
        total_count = int(page_info.get("count") or 0)
        page_size = int(page_info.get("size") or 20)

        if total_count and pn * page_size >= total_count:
            break

        random_sleep(0.8, 1.6)

    return all_rows, last_error


def get_wbi_keys(session: requests.Session) -> Optional[Tuple[str, str]]:
    try:
        resp = session.get(
            "https://api.bilibili.com/x/web-interface/nav",
            timeout=15,
        )
        data = resp.json()

        wbi_img = ((data.get("data") or {}).get("wbi_img") or {})

        img_url = wbi_img.get("img_url") or ""
        sub_url = wbi_img.get("sub_url") or ""

        img_key = Path(urllib.parse.urlparse(img_url).path).stem
        sub_key = Path(urllib.parse.urlparse(sub_url).path).stem

        if img_key and sub_key:
            return img_key, sub_key

    except Exception as exc:
        print(f"    获取 WBI keys 失败：{exc}")

    return None


def get_mixin_key(img_key: str, sub_key: str) -> str:
    raw = img_key + sub_key
    return "".join(raw[i] for i in MIXIN_KEY_ENC_TAB if i < len(raw))[:32]


def encode_wbi(
    params: Dict[str, object],
    img_key: str,
    sub_key: str,
) -> Dict[str, object]:
    mixin_key = get_mixin_key(img_key, sub_key)

    signed_params = dict(params)
    signed_params["wts"] = int(time.time())

    # B 站 WBI 签名要求过滤这些字符
    chr_filter = "!'()*"

    clean_params = {}

    for k, v in signed_params.items():
        value = str(v)
        value = "".join(ch for ch in value if ch not in chr_filter)
        clean_params[k] = value

    query = urllib.parse.urlencode(sorted(clean_params.items()))

    clean_params["w_rid"] = hashlib.md5(
        (query + mixin_key).encode("utf-8")
    ).hexdigest()

    return clean_params


def fetch_comments_by_wbi_api(
    session: requests.Session,
    *,
    aid: int,
    bvid: str,
    keyword: str,
    video_url: str,
    crawl_time: str,
    max_comments: int,
) -> Tuple[List[Dict[str, object]], Optional[str]]:
    keys = get_wbi_keys(session)

    if not keys:
        return [], "无法获取 WBI keys"

    img_key, sub_key = keys

    all_rows: List[Dict[str, object]] = []
    seen_ids: Set[str] = set()
    offset = ""
    last_error: Optional[str] = None

    for _ in range(100):
        if len(all_rows) >= max_comments:
            break

        pagination_str = json.dumps(
            {"offset": offset},
            ensure_ascii=False,
            separators=(",", ":"),
        )

        params = {
            "oid": aid,
            "type": 1,
            "mode": 3,
            "pagination_str": pagination_str,
            "plat": 1,
            "web_location": 1315875,
        }

        signed = encode_wbi(params, img_key, sub_key)

        try:
            resp = session.get(
                "https://api.bilibili.com/x/v2/reply/wbi/main",
                params=signed,
                headers={"Referer": video_url},
                timeout=15,
            )
            data = resp.json()
        except Exception as exc:
            last_error = f"WBI 评论接口请求失败：{exc}"
            break

        if data.get("code") != 0:
            last_error = (
                f"WBI 评论接口异常：code={data.get('code')} "
                f"message={data.get('message')}"
            )
            break

        data_obj = data.get("data") or {}
        replies = data_obj.get("replies") or []

        if not replies:
            break

        rows = flatten_replies(
            replies,
            keyword=keyword,
            video_id=bvid,
            video_url=video_url,
            crawl_time=crawl_time,
            max_count=max_comments - len(all_rows),
        )

        for row in rows:
            cid = str(row["comment_id"])

            if cid not in seen_ids:
                seen_ids.add(cid)
                all_rows.append(row)

        cursor = data_obj.get("cursor") or {}
        pagination_reply = cursor.get("pagination_reply") or {}

        next_offset = (
            pagination_reply.get("next_offset")
            or pagination_reply.get("offset")
            or cursor.get("next")
            or ""
        )

        is_end = bool(cursor.get("is_end"))

        if is_end or not next_offset or next_offset == offset:
            break

        offset = next_offset

        random_sleep(0.8, 1.6)

    return all_rows, last_error


def fetch_comments_by_api(
    driver: webdriver.Edge,
    *,
    bvid: str,
    keyword: str,
    video_url: str,
    crawl_time: str,
    max_comments: int,
) -> List[Dict[str, object]]:
    session = build_session_from_driver(driver)

    aid = get_aid_by_bvid(session, bvid)

    if not aid:
        return []

    print(f"    bvid={bvid}, aid={aid}，开始请求评论接口")

    rows, err = fetch_comments_by_old_api(
        session,
        aid=aid,
        bvid=bvid,
        keyword=keyword,
        video_url=video_url,
        crawl_time=crawl_time,
        max_comments=max_comments,
    )

    if rows:
        print(f"    旧评论接口采集到 {len(rows)} 条")
        return rows

    if err:
        print(f"    {err}")

    rows, err = fetch_comments_by_wbi_api(
        session,
        aid=aid,
        bvid=bvid,
        keyword=keyword,
        video_url=video_url,
        crawl_time=crawl_time,
        max_comments=max_comments,
    )

    if rows:
        print(f"    WBI 评论接口采集到 {len(rows)} 条")
        return rows

    if err:
        print(f"    {err}")

    return []


# ==================================================
# 6. Selenium DOM 兜底采集
# ==================================================

def scroll_to_comments(driver: webdriver.Edge) -> None:
    for _ in range(18):
        try:
            found = driver.execute_script(
                """
                const selectors = [
                    '#comment',
                    '.comment',
                    '.reply-list',
                    '.reply-item',
                    'bili-comments'
                ];

                return selectors.some(sel => document.querySelector(sel));
                """
            )

            if found:
                return

            driver.execute_script(
                "window.scrollBy(0, Math.floor(window.innerHeight * 0.85));"
            )

        except Exception:
            pass

        random_sleep(0.8, 1.5)


def collect_comment_texts_from_dom(
    driver: webdriver.Edge,
    limit: int,
) -> List[str]:
    """
    穿透 open shadowRoot，尽量抓取新版 B 站评论组件中的文本。
    这是兜底方案，字段没有 API 准。
    """
    script = r"""
        const limit = arguments[0];
        const results = [];
        const seen = new Set();

        const selectors = [
            '.reply-item',
            '.comment-item',
            '.reply-card',
            '.list-item',
            'bili-comment-thread-renderer',
            'bili-comment-renderer',
            '[class*=reply]',
            '[class*=comment]'
        ];

        function addText(el) {
            if (!el || results.length >= limit) return;

            let text = (el.innerText || el.textContent || '').trim();
            text = text.replace(/\s+/g, ' ');

            if (text.length < 8 || text.length > 2000) return;
            if (seen.has(text)) return;

            seen.add(text);
            results.push(text);
        }

        function walk(root) {
            if (!root || results.length >= limit) return;

            for (const sel of selectors) {
                try {
                    root.querySelectorAll(sel).forEach(addText);
                } catch (e) {}
            }

            const all = root.querySelectorAll ? root.querySelectorAll('*') : [];

            for (const el of all) {
                if (results.length >= limit) break;
                if (el.shadowRoot) walk(el.shadowRoot);
            }
        }

        walk(document);

        return results.slice(0, limit);
    """

    try:
        texts = driver.execute_script(script, limit)
    except Exception:
        return []

    if not isinstance(texts, list):
        return []

    return [clean_text(x) for x in texts if clean_text(x)]


def fetch_comments_by_dom(
    driver: webdriver.Edge,
    *,
    bvid: str,
    keyword: str,
    video_url: str,
    crawl_time: str,
    max_comments: int,
) -> List[Dict[str, object]]:
    print("    API 未采到评论，尝试 Selenium 页面兜底")

    scroll_to_comments(driver)

    rows: List[Dict[str, object]] = []
    seen_content: Set[str] = set()
    no_new_rounds = 0

    for round_num in range(SCROLL_ROUNDS_PER_VIDEO):
        texts = collect_comment_texts_from_dom(driver, max_comments * 2)
        before = len(rows)

        for text in texts:
            if len(rows) >= max_comments:
                break

            text = clean_text(text)

            if len(text) < 5:
                continue

            # 粗略过滤页面无关文本
            if any(
                bad in text
                for bad in ["相关推荐", "弹幕列表", "立即登录", "投稿", "充电"]
            ):
                continue

            if text in seen_content:
                continue

            seen_content.add(text)

            rid = hashlib.md5(text.encode("utf-8")).hexdigest()

            rows.append(
                {
                    "platform": "bilibili",
                    "keyword": keyword,
                    "comment_id": make_comment_id(bvid, rid),
                    "user_name": "",
                    "content": text,
                    "publish_time": "",
                    "like_count": 0,
                    "language": detect_language(text),
                    "source_url": video_url,
                    "crawl_time": crawl_time,
                }
            )

        if len(rows) > before:
            no_new_rounds = 0
        else:
            no_new_rounds += 1

        if len(rows) >= max_comments or no_new_rounds >= MAX_NO_NEW_ROUNDS:
            break

        try:
            driver.execute_script(
                "window.scrollBy(0, Math.floor(window.innerHeight * 0.9));"
            )
        except Exception:
            pass

        random_sleep(1.5, 3)

    if rows:
        print(f"    DOM 兜底采集到 {len(rows)} 条")
    else:
        print(f"    DOM 兜底也没有采到")

    return rows


# ==================================================
# 7. 主流程
# ==================================================

def crawl_bilibili() -> None:
    ensure_dirs()

    driver = create_driver()

    total_comments = 0
    crawl_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    existing_ids = load_existing_comment_ids()

    try:
        driver.get("https://www.bilibili.com/")

        print("🚀 浏览器已启动。请在打开的 B 站页面手动登录。")
        print("   登录完成、确认右上角显示你的头像后，回到命令行按 Enter 继续。")

        input("登录完成后按 Enter 键继续...")

        for keyword in KEYWORDS:
            if total_comments >= MAX_COMMENTS_TOTAL:
                break

            print(f"\n🔍 搜索关键词: {keyword}")

            video_urls = collect_video_urls_from_search(driver, keyword)

            print(f"  找到 {len(video_urls)} 个视频")

            if not video_urls:
                print("  没找到视频，可能是搜索页结构变化、网络慢或触发风控。")
                continue

            for video_url in video_urls:
                if total_comments >= MAX_COMMENTS_TOTAL:
                    break

                bvid = extract_bvid(video_url)

                if not bvid:
                    continue

                print(f"\n  📺 处理视频: {video_url}")

                if not open_url_with_retry(driver, video_url):
                    continue

                random_sleep(3, 5)

                # 先用接口抓评论；失败再用 DOM 兜底
                comments = fetch_comments_by_api(
                    driver,
                    bvid=bvid,
                    keyword=keyword,
                    video_url=video_url,
                    crawl_time=crawl_time,
                    max_comments=MAX_COMMENTS_PER_VIDEO,
                )

                if not comments:
                    comments = fetch_comments_by_dom(
                        driver,
                        bvid=bvid,
                        keyword=keyword,
                        video_url=video_url,
                        crawl_time=crawl_time,
                        max_comments=MAX_COMMENTS_PER_VIDEO,
                    )

                unique_comments: List[Dict[str, object]] = []

                for row in comments:
                    cid = str(row.get("comment_id", ""))

                    if not cid or cid in existing_ids:
                        continue

                    existing_ids.add(cid)
                    unique_comments.append(row)

                if unique_comments:
                    remain = MAX_COMMENTS_TOTAL - total_comments
                    unique_comments = unique_comments[:remain]

                    save_to_csv(unique_comments, append=True)

                    total_comments += len(unique_comments)

                    print(
                        f"    本视频新增 {len(unique_comments)} 条，"
                        f"总计 {total_comments}"
                    )
                else:
                    print("    本视频没有新增评论")

                random_sleep(3, 6)

    except KeyboardInterrupt:
        print("\n用户中断，准备退出。")

    except Exception as exc:
        print(f"爬取过程中断: {exc}")

    finally:
        try:
            driver.quit()
        except Exception:
            pass

        print(f"\n✅ B站爬虫完成！本次共采集 {total_comments} 条新评论")
        print(f"输出文件：{OUTPUT_PATH}")


if __name__ == "__main__":
    crawl_bilibili()
