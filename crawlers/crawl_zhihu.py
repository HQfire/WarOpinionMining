"""
知乎爬虫模块 — 美以伊战争舆情挖掘项目
==================================
功能：
    通过 Selenium 模拟 Edge 浏览器访问知乎搜索页面，
    爬取“美以伊战争”相关内容，并保存为单独 CSV 文件。

输出：
    data/raw/知乎_posts.csv

运行：
    python crawlers/crawl_zhihu.py
"""

import os
import time
import random
import pandas as pd
from urllib.parse import quote

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from webdriver_manager.microsoft import EdgeChromiumDriverManager


# 项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 输出目录
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "raw")


def create_driver():
    """创建 Edge 浏览器。"""
    options = Options()

    # 建议先不要开启无头模式，方便手动登录、查看页面情况
    # options.add_argument("--headless=new")

    options.add_argument("--window-size=1400,900")
    options.add_argument("--disable-gpu")

    service = Service(EdgeChromiumDriverManager().install())
    driver = webdriver.Edge(service=service, options=options)

    return driver


def safe_find_text(parent, selectors):
    """
    按多个 CSS 选择器依次尝试提取文本。

    Args:
        parent: Selenium 元素
        selectors: CSS 选择器列表

    Returns:
        str: 提取到的文本
    """
    for selector in selectors:
        try:
            elem = parent.find_element(By.CSS_SELECTOR, selector)
            text = elem.text.strip()
            if text:
                return text
        except Exception:
            pass

    return ""


def safe_find_attr(parent, selectors, attr):
    """
    按多个 CSS 选择器依次尝试提取属性。

    Args:
        parent: Selenium 元素
        selectors: CSS 选择器列表
        attr: 属性名，例如 href

    Returns:
        str: 属性值
    """
    for selector in selectors:
        try:
            elem = parent.find_element(By.CSS_SELECTOR, selector)
            value = elem.get_attribute(attr)
            if value:
                return value.strip()
        except Exception:
            pass

    return ""


def clean_text(text):
    """清洗文本。"""
    if not text:
        return ""

    text = text.replace("\n", " ")
    text = text.replace("\r", " ")
    text = text.replace("阅读全文", " ")
    text = text.replace("显示全部", " ")

    while "  " in text:
        text = text.replace("  ", " ")

    return text.strip()


def parse_like_count(text):
    """
    解析知乎赞同数。

    示例：
        12 -> 12
        1.2 万 -> 12000
        赞同 36 -> 36
    """
    if not text:
        return 0

    text = text.replace("赞同", "")
    text = text.replace("赞", "")
    text = text.replace(",", "")
    text = text.strip()

    try:
        if "万" in text:
            return int(float(text.replace("万", "").strip()) * 10000)

        return int(text)

    except Exception:
        return 0


def get_post_id_from_url(url):
    """从知乎 URL 中简单提取 ID。"""
    if not url:
        return ""

    url = url.split("?")[0]
    parts = [p for p in url.rstrip("/").split("/") if p]

    if not parts:
        return ""

    return parts[-1]


def extract_posts(driver, keyword):
    """
    从当前知乎搜索页提取内容。

    重要修复：
        不再使用 ".SearchResult-Card, .ContentItem" 同时选择，
        因为知乎页面中 .ContentItem 经常嵌套在 .SearchResult-Card 中，
        同时抓会导致数据两两重复。
    """
    data = []
    seen = set()

    # 只抓外层搜索卡片，避免外层和内层重复
    cards = driver.find_elements(By.CSS_SELECTOR, ".SearchResult-Card")

    # 如果页面结构变化，没有外层卡片，再抓 ContentItem 作为备用
    if not cards:
        cards = driver.find_elements(By.CSS_SELECTOR, ".ContentItem")

    for card in cards:
        title = safe_find_text(card, [
            ".ContentItem-title",
            ".QuestionItem-title",
            "h2",
            "h3",
        ])

        content = safe_find_text(card, [
            ".RichContent-inner",
            ".RichText",
            ".SearchResult-snippet",
            ".ContentItem-excerpt",
        ])

        title = clean_text(title)
        content = clean_text(content)

        if not title and not content:
            continue

        if title and content and content not in title:
            full_content = title + " " + content
        else:
            full_content = title or content

        full_content = clean_text(full_content)

        if len(full_content) < 5:
            continue

        user_name = safe_find_text(card, [
            ".AuthorInfo-name",
            ".UserLink-link",
            ".Popover",
        ])

        publish_time = safe_find_text(card, [
            ".ContentItem-time",
            ".ContentItem-status",
            ".SearchResult-meta",
        ])

        like_text = safe_find_text(card, [
            ".VoteButton",
            "button[aria-label*='赞同']",
        ])

        url = safe_find_attr(card, [
            "a[href*='/question/']",
            "a[href*='/answer/']",
            "a[href*='/p/']",
        ], "href")

        post_id = get_post_id_from_url(url)

        # 当前页内部去重
        unique_key = url or full_content[:120]

        if unique_key in seen:
            continue

        seen.add(unique_key)

        data.append({
            "platform": "知乎",
            "keyword": keyword,
            "content": full_content,
            "publish_time": publish_time,
            "user_name": user_name or "知乎用户",
            "like_count": parse_like_count(like_text),
            "post_id": post_id,
            "url": url,
        })

    return data


def search_posts(keyword, count=800, max_pages=50):
    """
    搜索知乎内容。

    Args:
        keyword: 搜索关键词
        count: 目标数量
        max_pages: 最大翻页数

    Returns:
        list[dict]: 爬取结果
    """
    driver = create_driver()

    results = []
    seen = set()

    try:
        driver.get("https://www.zhihu.com/")

        print("[知乎] 如果页面要求登录，请先在浏览器里扫码登录")
        input("[知乎] 登录完成后按回车继续；如果已经登录，也直接按回车：")

        for page in range(1, max_pages + 1):
            if len(results) >= count:
                break

            url = f"https://www.zhihu.com/search?type=content&q={quote(keyword)}&page={page}"

            print(f"[知乎] 正在打开第 {page} 页：{url}")
            driver.get(url)

            time.sleep(random.uniform(4, 6))

            # 滚动页面，让搜索结果加载完整
            for _ in range(4):
                driver.execute_script("window.scrollBy(0, 900);")
                time.sleep(random.uniform(1, 2))

            page_data = extract_posts(driver, keyword)

            print(f"[知乎] 第 {page} 页提取到 {len(page_data)} 条")

            # 跨页去重
            for item in page_data:
                unique_key = item.get("url") or item.get("content", "")[:120]

                if unique_key in seen:
                    continue

                seen.add(unique_key)
                results.append(item)

                if len(results) >= count:
                    break

            time.sleep(random.uniform(2, 4))

    finally:
        driver.quit()

    return results[:count]


def save_to_csv(data, output_path):
    """保存 CSV 文件。"""
    if not data:
        print("[知乎] 没有抓到数据，不保存 CSV")
        return

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    df = pd.DataFrame(data)

    columns = [
        "platform",
        "keyword",
        "content",
        "publish_time",
        "user_name",
        "like_count",
        "post_id",
        "url",
    ]

    for col in columns:
        if col not in df.columns:
            df[col] = ""

    df = df[columns]

    # 保存前再去重一遍，防止页面懒加载重复
    df = df.drop_duplicates(subset=["content"], keep="first")

    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"[知乎] 已保存：{output_path}")
    print(f"[知乎] 共 {len(df)} 条")


def main():
    """知乎爬虫主入口。"""
    keyword = "美以伊战争"
    output_path = os.path.join(OUTPUT_DIR, "知乎_posts.csv")

    print("=" * 60)
    print("[知乎] 简化版爬虫启动")
    print("=" * 60)

    data = search_posts(
        keyword=keyword,
        count=800,
        max_pages=50,
    )

    save_to_csv(data, output_path)

    print("[知乎] 完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
