import requests
import csv
import html

API_KEY = "AIzaSyDb8TxSEDfJ54y7TpzOZDI4Iwqtvzob2IM"

proxies = {
    "http": "http://127.0.0.1:33210",
    "https": "http://127.0.0.1:33210",
}

# ======================
# 搜索视频
# ======================
search_url = "https://www.googleapis.com/youtube/v3/search"

search_params = {
    "key": API_KEY,
    "q": "Israel Iran war",
    "part": "snippet",
    "maxResults": 10,
    "type": "video"
}

search_data = requests.get(search_url, params=search_params, proxies=proxies, timeout=30).json()

# ======================
# 准备CSV文件
# ======================
csv_file = open("youtube_comments.csv", "w", newline="", encoding="utf-8-sig")
writer = csv.writer(csv_file)

# 表头
writer.writerow(["video_title", "video_id", "comment"])

# ======================
# 3️⃣ 获取评论
# ======================
comment_url = "https://www.googleapis.com/youtube/v3/commentThreads"

for item in search_data.get("items", []):

    video_id = item["id"]["videoId"]
    title = html.unescape(item["snippet"]["title"])

    print("处理视频：", title)

    comment_params = {
        "key": API_KEY,
        "videoId": video_id,
        "part": "snippet",
        "maxResults": 100,
        "textFormat": "plainText"
    }

    try:
        comment_data = requests.get(comment_url, params=comment_params, proxies=proxies, timeout=30).json()

        for c in comment_data.get("items", []):

            comment = c["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
            comment = html.unescape(comment)

            print("👉", comment)

            # 写入CSV
            writer.writerow([title, video_id, comment])

    except Exception as e:
        print("评论获取失败：", e)

csv_file.close()

print("\n✅ CSV导出完成：youtube_comments.csv")