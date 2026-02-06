"""
YouTube Data API v3 を使ったデータ収集スクリプト
第51回衆議院議員総選挙（2026年2月8日）関連動画の収集
"""
import json
import os
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from googleapiclient.discovery import build
from tqdm import tqdm

from config import (
    YOUTUBE_API_KEY,
    SEARCH_QUERIES,
    PARTY_CHANNELS,
    ISSUE_KEYWORDS,
    DATE_RANGE,
    MAX_RESULTS_PER_QUERY,
)

DATA_DIR = Path(__file__).parent.parent / "data"


def get_youtube_client():
    """YouTube API クライアントを取得"""
    if not YOUTUBE_API_KEY:
        raise ValueError(
            "YOUTUBE_API_KEY が設定されていません。.env ファイルを確認してください。"
        )
    return build("youtube", "v3", developerKey=YOUTUBE_API_KEY)


def search_videos(youtube, query, max_results=MAX_RESULTS_PER_QUERY):
    """キーワードで動画を検索"""
    videos = []
    next_page_token = None

    while len(videos) < max_results:
        request = youtube.search().list(
            q=query,
            part="snippet",
            type="video",
            order="relevance",
            publishedAfter=DATE_RANGE["start"],
            publishedBefore=DATE_RANGE["end"],
            regionCode="JP",
            relevanceLanguage="ja",
            maxResults=min(50, max_results - len(videos)),
            pageToken=next_page_token,
        )
        response = request.execute()

        for item in response.get("items", []):
            videos.append(
                {
                    "video_id": item["id"]["videoId"],
                    "title": item["snippet"]["title"],
                    "description": item["snippet"]["description"],
                    "channel_id": item["snippet"]["channelId"],
                    "channel_title": item["snippet"]["channelTitle"],
                    "published_at": item["snippet"]["publishedAt"],
                    "search_query": query,
                }
            )

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    return videos


def get_video_details(youtube, video_ids):
    """動画の詳細統計情報を取得"""
    details = []

    # APIは最大50件ずつ
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        request = youtube.videos().list(
            part="statistics,contentDetails,snippet",
            id=",".join(batch),
        )
        response = request.execute()

        for item in response.get("items", []):
            stats = item.get("statistics", {})
            details.append(
                {
                    "video_id": item["id"],
                    "title": item["snippet"]["title"],
                    "channel_id": item["snippet"]["channelId"],
                    "channel_title": item["snippet"]["channelTitle"],
                    "published_at": item["snippet"]["publishedAt"],
                    "tags": item["snippet"].get("tags", []),
                    "category_id": item["snippet"].get("categoryId", ""),
                    "duration": item["contentDetails"]["duration"],
                    "view_count": int(stats.get("viewCount", 0)),
                    "like_count": int(stats.get("likeCount", 0)),
                    "comment_count": int(stats.get("commentCount", 0)),
                }
            )

    return details


def get_video_comments(youtube, video_id, max_comments=100):
    """動画のコメントを取得"""
    comments = []
    next_page_token = None

    try:
        while len(comments) < max_comments:
            request = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                order="relevance",
                maxResults=min(100, max_comments - len(comments)),
                pageToken=next_page_token,
            )
            response = request.execute()

            for item in response.get("items", []):
                snippet = item["snippet"]["topLevelComment"]["snippet"]
                comments.append(
                    {
                        "video_id": video_id,
                        "comment_id": item["id"],
                        "author": snippet["authorDisplayName"],
                        "text": snippet["textDisplay"],
                        "like_count": snippet["likeCount"],
                        "published_at": snippet["publishedAt"],
                    }
                )

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break
    except Exception as e:
        print(f"  コメント取得エラー (video_id={video_id}): {e}")

    return comments


def get_channel_stats(youtube, channel_ids):
    """チャンネルの統計情報を取得"""
    stats = []
    for i in range(0, len(channel_ids), 50):
        batch = channel_ids[i : i + 50]
        request = youtube.channels().list(
            part="statistics,snippet",
            id=",".join(batch),
        )
        response = request.execute()

        for item in response.get("items", []):
            s = item.get("statistics", {})
            stats.append(
                {
                    "channel_id": item["id"],
                    "channel_title": item["snippet"]["title"],
                    "subscriber_count": int(s.get("subscriberCount", 0)),
                    "video_count": int(s.get("videoCount", 0)),
                    "view_count": int(s.get("viewCount", 0)),
                    "collected_at": datetime.now().isoformat(),
                }
            )

    return stats


def collect_all_data():
    """全データを収集するメインフロー"""
    youtube = get_youtube_client()

    print("=" * 60)
    print("第51回衆議院議員総選挙 YouTube データ収集")
    print("=" * 60)

    # 1. キーワード検索で動画を収集
    print("\n[1/4] 選挙関連動画の検索...")
    all_videos = []
    for query in tqdm(SEARCH_QUERIES, desc="検索中"):
        videos = search_videos(youtube, query)
        all_videos.extend(videos)
        time.sleep(0.5)

    # 重複を除去
    seen_ids = set()
    unique_videos = []
    for v in all_videos:
        if v["video_id"] not in seen_ids:
            seen_ids.add(v["video_id"])
            unique_videos.append(v)

    print(f"  検索結果: {len(unique_videos)} 件（重複除去後）")

    # 2. 動画の詳細情報を取得
    print("\n[2/4] 動画の詳細統計を取得中...")
    video_ids = [v["video_id"] for v in unique_videos]
    video_details = get_video_details(youtube, video_ids)
    print(f"  詳細取得: {len(video_details)} 件")

    # 3. 上位動画のコメントを取得
    print("\n[3/4] 上位動画のコメントを取得中...")
    df_details = pd.DataFrame(video_details)
    top_videos = df_details.nlargest(20, "view_count")

    all_comments = []
    for _, row in tqdm(
        top_videos.iterrows(), total=len(top_videos), desc="コメント取得"
    ):
        comments = get_video_comments(youtube, row["video_id"])
        all_comments.extend(comments)
        time.sleep(0.5)
    print(f"  コメント取得: {len(all_comments)} 件")

    # 4. 政党チャンネルの統計を取得
    print("\n[4/4] 政党チャンネルの統計を取得中...")
    channel_ids = list(PARTY_CHANNELS.values())
    channel_stats = get_channel_stats(youtube, channel_ids)
    print(f"  チャンネル統計: {len(channel_stats)} 件")

    # データ保存
    print("\n保存中...")
    raw_dir = DATA_DIR / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    pd.DataFrame(unique_videos).to_csv(
        raw_dir / f"search_results_{timestamp}.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame(video_details).to_csv(
        raw_dir / f"video_details_{timestamp}.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame(all_comments).to_csv(
        raw_dir / f"comments_{timestamp}.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame(channel_stats).to_csv(
        raw_dir / f"channel_stats_{timestamp}.csv", index=False, encoding="utf-8-sig"
    )

    print(f"\n保存完了: {raw_dir}")
    print("=" * 60)

    return {
        "videos": unique_videos,
        "details": video_details,
        "comments": all_comments,
        "channels": channel_stats,
    }


if __name__ == "__main__":
    collect_all_data()
