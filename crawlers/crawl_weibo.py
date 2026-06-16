import os
import time
import random
import pandas as pd
from datetime import datetime, timedelta
from urllib.parse import quote

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from webdriver_manager.microsoft import EdgeChromiumDriverManager


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "raw")


def create_driver():
    """创建 Edge 浏览器。"""
    options = Options()

    # 建议先不要无头模式，方便扫码登录、看页面是否被验证码拦截
    # options.add_argument("--headless=new")

    options.add_argument("--window-size=1400,900")
    options.add_argument("--disable-gpu")

    service = Service(EdgeChromiumDriverManager().install())
    driver = webdriver.Edge(service=service, options=options)
    return driver


def safe_find_text(parent, selectors):
    """按多个选择器依次尝试提取文本。"""
    for selector in selectors:
        try:
            elem = parent.find_element(By.CSS_SELECTOR, selector)
            text = elem.text.strip()
            if text:
                return text
        except Exception:
            pass
    return ""


def parse_like_count(text):
    """解析点赞数。"""
    if not text:
        return 0

    text = text.replace("赞", "").strip()

    try:
        if "万" in text:
            return int(float(text.replace("万", "")) * 10000)
        return int(text)
    except Exception:
        return 0


def extract_posts(driver, keyword):
    """从当前微博搜索页提取帖子。"""
    data = []

    cards = driver.find_elements(By.CSS_SELECTOR, "div[action-type='feed_list_item']")

    for card in cards:
        content = safe_find_text(card, [
            "p[node-type='feed_list_content_full']",
            "p[node-type='feed_list_content']",
            ".WB_text",
        ])

        if not content or len(content) < 5:
            continue

        user_name = safe_find_text(card, [
            "a.name",
            ".info .name",
            ".W_f14",
        ])

        publish_time = safe_find_text(card, [
            ".from a",
            ".WB_from a",
            ".from",
        ])

        like_text = safe_find_text(card, [
            "a[action-type='feed_list_like']",
            ".card-act li:nth-child(4)",
            ".WB_row_like",
        ])

        # 尝试提取微博 ID
        post_id = card.get_attribute("mid") or ""

        data.append({
            "platform": "微博",
            "keyword": keyword,
            "content": content,
            "publish_time": publish_time,
            "user_name": user_name or "微博用户",
            "like_count": parse_like_count(like_text),
            "post_id": post_id,
        })

    return data

def search_posts(keyword, count=500, max_pages=50):
    """搜索微博帖子。"""
    driver = create_driver()
    results = []

    try:
        # 先打开微博首页，方便你扫码登录
        driver.get("https://weibo.com/")
        print("[微博] 如果页面要求登录，请先在浏览器里扫码登录")
        input("[微博] 登录完成后按回车继续；如果已经登录，也直接按回车：")

        for page in range(1, max_pages + 1):
            if len(results) >= count:
                break

            url = (
                f"https://s.weibo.com/weibo?q={quote(keyword)}"
                f"&typeall=1&suball=1&page={page}"
            )

            print(f"[微博] 正在打开第 {page} 页：{url}")
            driver.get(url)

            time.sleep(random.uniform(4, 6))

            # 滚动几次，让页面内容加载出来
            for _ in range(3):
                driver.execute_script("window.scrollBy(0, 800);")
                time.sleep(random.uniform(1, 2))

            page_data = extract_posts(driver, keyword)
            print(f"[微博] 第 {page} 页提取到 {len(page_data)} 条")

            results.extend(page_data)

            time.sleep(random.uniform(2, 4))

    finally:
        driver.quit()

    return results[:count]


def save_to_csv(data, output_path):
    """保存 CSV。"""
    if not data:
        print("[微博] 没有抓到数据，不保存 CSV")
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
    ]

    df = df[columns]
    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"[微博] 已保存：{output_path}")
    print(f"[微博] 共 {len(df)} 条")


def main():
    keyword = "美以伊战争"
    output_path = os.path.join(OUTPUT_DIR, "微博_posts.csv")

    print("=" * 60)
    print("[微博] 简化版爬虫启动")
    print("=" * 60)

    data = search_posts(keyword, count=1000, max_pages=100)
    save_to_csv(data, output_path)

    print("[微博] 完成")


if __name__ == "__main__":
    main()
