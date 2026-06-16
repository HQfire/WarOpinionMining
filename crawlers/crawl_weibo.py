import csv
import time
import random
from datetime import datetime
from crawl4weibo import WeiboClient

# ==================== 配置区域 ====================
# 搜索关键词列表，围绕 "美以伊战争"
SEARCH_KEYWORDS = [
    "美以伊战争",
    "美以伊战争 中国网友",
    "伊朗反击美以",
    "美国伊朗以色列 战争",
    "中东局势 中国看法"
]

# 每个关键词搜索的页数（微博搜索每页约20条帖子）
PAGES_PER_KEYWORD = 5

# 每条帖子获取的评论页数（评论每页约20条）
COMMENT_PAGES_PER_POST = 3

# 输出文件名
OUTPUT_CSV = "data/raw/weibo_posts.csv"

# 请求延迟（秒），模拟人类行为，防止被封
REQUEST_DELAY_MIN = 2
REQUEST_DELAY_MAX = 5


# ==================== 主程序 ====================

def setup_client():
    """初始化微博客户端，设置请求头和反爬策略"""
    # 创建客户端，login_cookies=False 表示不强制登录
    # 但为了获取更完整的数据，可以设置为 True 并交互登录
    client = WeiboClient(login_cookies=False)
    return client


def search_posts_by_keyword(client, keyword, pages):
    """根据关键词搜索微博帖子"""
    all_posts = []
    print(f"🔍 正在搜索关键词: {keyword}")
    for page in range(1, pages + 1):
        try:
            # search_posts 返回帖子列表和分页信息
            posts, pagination = client.search_posts(keyword, page=page)
            if not posts:
                print(f"  第 {page} 页无结果，停止搜索")
                break
            all_posts.extend(posts)
            print(f"  已获取第 {page} 页，共 {len(posts)} 条帖子")
            # 随机延迟，防止请求过快
            time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))
        except Exception as e:
            print(f"  ⚠️ 搜索第 {page} 页时出错: {e}")
            break
    print(f"✅ 关键词 '{keyword}' 共获取 {len(all_posts)} 条帖子")
    return all_posts


def get_comments_for_post(client, post, max_pages):
    """获取单条帖子的评论"""
    comments_data = []
    try:
        # get_all_comments 自动处理分页，获取所有评论
        # 这里限制最大页数，避免单条帖子评论过多
        comments, pagination = client.get_all_comments(
            post.id,
            max_pages=max_pages
        )

        if not comments:
            return comments_data

        # 提取需要的字段
        for comment in comments:
            # 处理评论内容，去除多余空白
            text = comment.text.strip() if comment.text else ""
            # 处理发布时间
            created_at = comment.created_at if hasattr(comment, 'created_at') else ""

            comments_data.append({
                "comment_text": text,
                "created_at": created_at,
                "user_screen_name": comment.user_screen_name if hasattr(comment, 'user_screen_name') else "",
                "like_count": comment.like_count if hasattr(comment, 'like_count') else 0,
                "post_id": post.id,
                "post_text": post.text[:50] + "..." if post.text else "",  # 截取帖子前50字作为上下文
                "keyword": post.text[:10] if post.text else ""  # 简单标记关键词
            })

        print(f"  帖子 {post.id} 获取 {len(comments_data)} 条评论")

    except Exception as e:
        print(f"  ⚠️ 获取帖子 {post.id} 评论时出错: {e}")

    return comments_data


def save_to_csv(data, filename):
    """保存数据到CSV文件"""
    if not data:
        print("⚠️ 没有数据可保存")
        return

    fieldnames = [
        "comment_text",
        "created_at",
        "user_screen_name",
        "like_count",
        "post_id",
        "post_text",
        "keyword"
    ]

    with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

    print(f"✅ 数据已保存到 {filename}，共 {len(data)} 条评论")


def main():
    """主函数"""
    print("=" * 50)
    print("🚀 微博评论爬虫启动")
    print(f"📅 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    # 1. 初始化客户端
    client = setup_client()
    print("✅ 客户端初始化完成")

    # 2. 存储所有评论
    all_comments = []

    # 3. 遍历关键词搜索
    for keyword in SEARCH_KEYWORDS:
        # 3.1 搜索帖子
        posts = search_posts_by_keyword(client, keyword, PAGES_PER_KEYWORD)

        if not posts:
            print(f"⚠️ 关键词 '{keyword}' 没有获取到帖子，跳过")
            continue

        # 3.2 遍历每条帖子获取评论
        for idx, post in enumerate(posts):
            print(f"\n📝 处理帖子 [{idx + 1}/{len(posts)}]: {post.text[:30] if post.text else '无文本'}...")

            # 随机延迟，模拟人类浏览行为
            time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))

            # 获取评论
            comments = get_comments_for_post(client, post, COMMENT_PAGES_PER_POST)
            all_comments.extend(comments)

            # 每处理10条帖子输出一次进度
            if (idx + 1) % 10 == 0:
                print(f"  当前已收集 {len(all_comments)} 条评论")

            # 如果已经达到目标数量，可以提前结束（但这里不强制）
            # if len(all_comments) >= 1000:
            #     break

        # 如果已经达到目标数量，跳出外层循环
        if len(all_comments) >= 1000:
            print(f"\n🎯 已达到目标数量 {len(all_comments)} 条评论，停止爬取")
            break

    # 4. 保存结果
    print("\n" + "=" * 50)
    print(f"📊 共收集 {len(all_comments)} 条评论")

    if all_comments:
        save_to_csv(all_comments, OUTPUT_CSV)
    else:
        print("⚠️ 没有收集到任何评论数据")

    print(f"🏁 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)


if __name__ == "__main__":
    main()