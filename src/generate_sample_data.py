"""
サンプルデータ生成スクリプト
APIキーがなくても可視化のデモを実行できるようにする
"""
import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data"

random.seed(42)

PARTIES = ["自由民主党", "日本維新の会", "立憲民主党", "国民民主党", "日本共産党", "れいわ新選組", "参政党"]
ISSUES = ["消費税・物価高", "安全保障", "移民・外国人", "経済政策", "社会保障", "政治改革", "その他"]

SAMPLE_TITLES = [
    "【衆院選2026】各党の消費税政策を徹底比較",
    "高市首相が語る経済政策のビジョン",
    "中道改革連合 野田代表の街頭演説",
    "衆議院選挙 争点まとめ 2026年2月",
    "消費税ゼロは実現可能か？専門家が分析",
    "自民・維新連立の行方と選挙戦略",
    "物価高対策 各党の公約を比較してみた",
    "台湾有事と日本の安全保障 衆院選の争点",
    "外国人政策 各党のスタンスは？",
    "【緊急解説】国会冒頭解散の真意とは",
    "若者が語る 今回の選挙で大事なこと",
    "選挙区情勢 激戦区を徹底解説",
    "賃上げ政策 どの党が一番現実的？",
    "社会保障の未来 年金・医療はどうなる",
    "政治とカネ問題 有権者の声は",
    "比例代表 各党の議席予測",
    "初めての選挙 投票の仕方ガイド",
    "大雪で投票率に影響？真冬選挙の課題",
    "開票速報に向けて注目ポイント解説",
    "れいわ新選組 山本太郎の訴え",
]


def generate_video_details():
    """動画詳細のサンプルデータ"""
    rows = []
    base_date = datetime(2026, 1, 1)

    for i in range(200):
        pub_date = base_date + timedelta(
            days=random.randint(0, 38),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )

        # 選挙公示後（1/27以降）は投稿数が増加
        days_from_start = (pub_date - base_date).days
        view_multiplier = 1.0 + max(0, (days_from_start - 26)) * 0.3

        views = int(random.lognormvariate(10, 1.5) * view_multiplier)
        likes = int(views * random.uniform(0.01, 0.08))
        comments = int(views * random.uniform(0.002, 0.02))

        party = random.choice(PARTIES + ["個人"] * 5)
        title = random.choice(SAMPLE_TITLES)
        if party != "個人":
            title = f"【{party}】{title}"

        rows.append({
            "video_id": f"sample_{i:04d}",
            "title": title,
            "channel_id": f"ch_{i % 50:03d}",
            "channel_title": f"チャンネル{i % 50}",
            "published_at": pub_date.isoformat() + "Z",
            "tags": [],
            "category_id": "25",
            "duration": f"PT{random.randint(3, 120)}M{random.randint(0,59)}S",
            "view_count": views,
            "like_count": likes,
            "comment_count": comments,
        })

    return pd.DataFrame(rows)


def generate_comments():
    """コメントのサンプルデータ"""
    positive_templates = [
        "この政策に期待しています", "応援しています！", "素晴らしい演説でした",
        "とても分かりやすい解説", "投票の参考になりました",
    ]
    negative_templates = [
        "この政策には反対です", "信用できない", "もっと具体的な政策を",
        "国民をバカにしている", "失望しました",
    ]
    neutral_templates = [
        "他の党の政策も知りたい", "投票日は2月8日ですね", "情報ありがとうございます",
        "もう少し詳しく聞きたい", "選挙区はどこですか？",
    ]

    rows = []
    for i in range(500):
        templates = random.choices(
            [positive_templates, negative_templates, neutral_templates],
            weights=[0.3, 0.3, 0.4],
        )[0]

        pub_date = datetime(2026, 1, 15) + timedelta(
            days=random.randint(0, 24),
            hours=random.randint(0, 23),
        )

        rows.append({
            "video_id": f"sample_{random.randint(0, 19):04d}",
            "comment_id": f"comment_{i:05d}",
            "author": f"ユーザー{i}",
            "text": random.choice(templates),
            "like_count": random.randint(0, 200),
            "published_at": pub_date.isoformat() + "Z",
        })

    return pd.DataFrame(rows)


def generate_channel_stats():
    """チャンネル統計のサンプルデータ"""
    data = {
        "自由民主党": {"subscribers": 280000, "videos": 3200, "views": 150000000},
        "日本維新の会": {"subscribers": 120000, "videos": 1800, "views": 60000000},
        "立憲民主党": {"subscribers": 95000, "videos": 2500, "views": 45000000},
        "国民民主党": {"subscribers": 180000, "videos": 1200, "views": 80000000},
        "日本共産党": {"subscribers": 65000, "videos": 4500, "views": 35000000},
        "れいわ新選組": {"subscribers": 350000, "videos": 2800, "views": 200000000},
        "参政党": {"subscribers": 220000, "videos": 1500, "views": 110000000},
    }

    rows = []
    for party, stats in data.items():
        rows.append({
            "channel_id": f"ch_{party}",
            "channel_title": f"{party}公式チャンネル",
            "party_name": party,
            "subscriber_count": stats["subscribers"] + random.randint(-5000, 5000),
            "video_count": stats["videos"] + random.randint(-50, 50),
            "view_count": stats["views"] + random.randint(-1000000, 1000000),
            "collected_at": datetime.now().isoformat(),
        })

    return pd.DataFrame(rows)


def generate_all_sample_data():
    """全サンプルデータを生成"""
    print("サンプルデータを生成中...")

    # raw ディレクトリ
    raw_dir = DATA_DIR / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    timestamp = "sample"

    df_details = generate_video_details()
    df_details.to_csv(
        raw_dir / f"video_details_{timestamp}.csv", index=False, encoding="utf-8-sig"
    )

    df_comments = generate_comments()
    df_comments.to_csv(
        raw_dir / f"comments_{timestamp}.csv", index=False, encoding="utf-8-sig"
    )

    df_channels = generate_channel_stats()
    df_channels.to_csv(
        raw_dir / f"channel_stats_{timestamp}.csv", index=False, encoding="utf-8-sig"
    )

    # processed ディレクトリ用のデータも作成
    processed_dir = DATA_DIR / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    # 日別投稿数
    df_details["published_at"] = pd.to_datetime(df_details["published_at"])
    df_details["date"] = df_details["published_at"].dt.date
    daily_counts = df_details.groupby("date").size().reset_index(name="video_count")
    daily_counts.to_csv(processed_dir / "daily_video_counts.csv", index=False)

    # 日別再生回数
    daily_views = df_details.groupby("date")["view_count"].sum().reset_index()
    daily_views.to_csv(processed_dir / "daily_views.csv", index=False)

    # 争点別統計
    issue_data = []
    for issue in ISSUES:
        n = random.randint(10, 50)
        views = random.randint(50000, 2000000)
        issue_data.append({
            "issue": issue,
            "video_count": n,
            "total_views": views,
            "avg_views": views // n,
            "total_likes": int(views * 0.03),
            "total_comments": int(views * 0.005),
        })
    issue_stats = pd.DataFrame(issue_data).sort_values("total_views", ascending=False)
    issue_stats.to_csv(
        processed_dir / "issue_stats.csv", index=False, encoding="utf-8-sig"
    )

    # チャンネル分析
    df_channels.to_csv(
        processed_dir / "channel_analysis.csv", index=False, encoding="utf-8-sig"
    )

    # 政党動画統計
    party_video_data = []
    for party in PARTIES:
        n = random.randint(5, 30)
        views = random.randint(30000, 500000)
        party_video_data.append({
            "party_name": party,
            "video_count": n,
            "total_views": views,
            "avg_views": views // n,
            "total_likes": int(views * 0.04),
        })
    pd.DataFrame(party_video_data).to_csv(
        processed_dir / "party_video_stats.csv", index=False, encoding="utf-8-sig"
    )

    # 感情分析
    sentiment_data = pd.DataFrame([
        {"sentiment": "positive", "count": 148},
        {"sentiment": "neutral", "count": 210},
        {"sentiment": "negative", "count": 142},
    ])
    sentiment_data.to_csv(processed_dir / "sentiment_counts.csv", index=False)

    print(f"サンプルデータ生成完了!")
    print(f"  raw: {raw_dir}")
    print(f"  processed: {processed_dir}")


if __name__ == "__main__":
    generate_all_sample_data()
