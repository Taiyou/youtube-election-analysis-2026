"""
データ分析スクリプト
収集したYouTubeデータを加工・分析する
"""
import re
from pathlib import Path

import pandas as pd

from config import ISSUE_KEYWORDS, PARTY_CHANNELS

DATA_DIR = Path(__file__).parent.parent / "data"


def load_latest_data(prefix):
    """最新のデータファイルを読み込む"""
    raw_dir = DATA_DIR / "raw"
    files = sorted(raw_dir.glob(f"{prefix}_*.csv"), reverse=True)
    if not files:
        raise FileNotFoundError(f"{prefix} のデータファイルが見つかりません")
    print(f"読み込み: {files[0].name}")
    return pd.read_csv(files[0])


def classify_issue(text):
    """テキストを争点カテゴリに分類"""
    text = str(text).lower()
    matched = []
    for issue, keywords in ISSUE_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                matched.append(issue)
                break
    return matched if matched else ["その他"]


def analyze_video_trends(df):
    """動画のトレンド分析"""
    df = df.copy()
    df["published_at"] = pd.to_datetime(df["published_at"])
    df["date"] = df["published_at"].dt.date

    # 日別投稿数
    daily_counts = df.groupby("date").size().reset_index(name="video_count")

    # 日別累計再生回数
    daily_views = df.groupby("date")["view_count"].sum().reset_index()

    # エンゲージメント率の計算
    df["engagement_rate"] = (df["like_count"] + df["comment_count"]) / df[
        "view_count"
    ].replace(0, 1)

    return df, daily_counts, daily_views


def analyze_by_issue(df):
    """争点別の分析"""
    df = df.copy()
    rows = []
    for _, row in df.iterrows():
        text = f"{row.get('title', '')} {row.get('description', '')}"
        issues = classify_issue(text)
        for issue in issues:
            rows.append({"issue": issue, **row.to_dict()})

    issue_df = pd.DataFrame(rows)

    # 争点別の統計
    issue_stats = (
        issue_df.groupby("issue")
        .agg(
            video_count=("video_id", "count"),
            total_views=("view_count", "sum"),
            avg_views=("view_count", "mean"),
            total_likes=("like_count", "sum"),
            total_comments=("comment_count", "sum"),
        )
        .reset_index()
        .sort_values("total_views", ascending=False)
    )

    return issue_df, issue_stats


def analyze_channels(df_details, df_channels):
    """チャンネル別の分析"""
    # 政党名のマッピングを逆引き
    id_to_party = {v: k for k, v in PARTY_CHANNELS.items()}

    df_channels = df_channels.copy()
    df_channels["party_name"] = df_channels["channel_id"].map(id_to_party)

    # 政党チャンネルの動画を抽出
    party_channel_ids = set(PARTY_CHANNELS.values())
    party_videos = df_details[df_details["channel_id"].isin(party_channel_ids)].copy()
    party_videos["party_name"] = party_videos["channel_id"].map(id_to_party)

    party_video_stats = (
        party_videos.groupby("party_name")
        .agg(
            video_count=("video_id", "count"),
            total_views=("view_count", "sum"),
            avg_views=("view_count", "mean"),
            total_likes=("like_count", "sum"),
        )
        .reset_index()
    )

    return df_channels, party_video_stats


def analyze_comments_sentiment(df_comments):
    """コメントの簡易感情分析（キーワードベース）"""
    positive_words = [
        "賛成", "支持", "応援", "頑張", "期待", "素晴らしい", "良い", "いいね",
        "正しい", "最高", "ありがとう", "共感", "納得",
    ]
    negative_words = [
        "反対", "批判", "ダメ", "最悪", "嘘", "不信", "失望", "怒り",
        "辞めろ", "無理", "ひどい", "問題", "疑問",
    ]

    def simple_sentiment(text):
        text = str(text)
        pos = sum(1 for w in positive_words if w in text)
        neg = sum(1 for w in negative_words if w in text)
        if pos > neg:
            return "positive"
        elif neg > pos:
            return "negative"
        return "neutral"

    df_comments = df_comments.copy()
    df_comments["sentiment"] = df_comments["text"].apply(simple_sentiment)

    sentiment_counts = df_comments["sentiment"].value_counts().reset_index()
    sentiment_counts.columns = ["sentiment", "count"]

    return df_comments, sentiment_counts


def run_analysis():
    """全分析を実行"""
    print("=" * 60)
    print("データ分析を実行中...")
    print("=" * 60)

    # データ読み込み
    df_details = load_latest_data("video_details")
    df_comments = load_latest_data("comments")
    df_channels = load_latest_data("channel_stats")

    # 分析実行
    print("\n[1/4] 動画トレンド分析...")
    df_details, daily_counts, daily_views = analyze_video_trends(df_details)

    print("[2/4] 争点別分析...")
    issue_df, issue_stats = analyze_by_issue(df_details)

    print("[3/4] チャンネル分析...")
    df_channels, party_video_stats = analyze_channels(df_details, df_channels)

    print("[4/4] コメント感情分析...")
    df_comments, sentiment_counts = analyze_comments_sentiment(df_comments)

    # 加工済みデータの保存
    processed_dir = DATA_DIR / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    daily_counts.to_csv(processed_dir / "daily_video_counts.csv", index=False)
    daily_views.to_csv(processed_dir / "daily_views.csv", index=False)
    issue_stats.to_csv(
        processed_dir / "issue_stats.csv", index=False, encoding="utf-8-sig"
    )
    df_channels.to_csv(
        processed_dir / "channel_analysis.csv", index=False, encoding="utf-8-sig"
    )
    party_video_stats.to_csv(
        processed_dir / "party_video_stats.csv", index=False, encoding="utf-8-sig"
    )
    sentiment_counts.to_csv(processed_dir / "sentiment_counts.csv", index=False)
    df_comments.to_csv(
        processed_dir / "comments_with_sentiment.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print(f"\n分析結果を保存: {processed_dir}")
    print("=" * 60)

    return {
        "daily_counts": daily_counts,
        "daily_views": daily_views,
        "issue_stats": issue_stats,
        "channel_stats": df_channels,
        "party_video_stats": party_video_stats,
        "sentiment_counts": sentiment_counts,
    }


if __name__ == "__main__":
    run_analysis()
