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

PARTIES = ["自由民主党", "日本維新の会", "立憲民主党", "国民民主党", "日本共産党", "れいわ新選組", "参政党", "チームみらい"]
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
    "チームみらい安野代表 AIで変える政治の未来",
    "テクノロジーで政治は変わるか？チームみらいの挑戦",
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
        "チームみらい": {"subscribers": 63000, "videos": 450, "views": 4000000},
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


def generate_media_channels():
    """メディア・YouTuberチャンネルのサンプルデータ"""
    media_data = {
        # === テレビ・報道メディア ===
        "ANNnewsCH（テレビ朝日）": {
            "category": "テレビ報道",
            "subscribers": 4000000, "videos": 85000, "views": 8500000000,
            "election_videos": 120, "election_views": 45000000,
        },
        "TBS NEWS DIG": {
            "category": "テレビ報道",
            "subscribers": 3160000, "videos": 62000, "views": 4570000000,
            "election_videos": 95, "election_views": 38000000,
        },
        "テレ東BIZ": {
            "category": "テレビ報道",
            "subscribers": 2300000, "videos": 28000, "views": 3200000000,
            "election_videos": 85, "election_views": 32000000,
        },
        "日テレNEWS": {
            "category": "テレビ報道",
            "subscribers": 2150000, "videos": 55000, "views": 3800000000,
            "election_videos": 110, "election_views": 35000000,
        },
        "FNNプライムオンライン": {
            "category": "テレビ報道",
            "subscribers": 1200000, "videos": 40000, "views": 2100000000,
            "election_videos": 80, "election_views": 22000000,
        },
        "NHK": {
            "category": "テレビ報道",
            "subscribers": 4000000, "videos": 12000, "views": 3500000000,
            "election_videos": 60, "election_views": 28000000,
        },
        # === 政治・経済コメンテーターYouTuber ===
        "PIVOT": {
            "category": "ビジネスメディア",
            "subscribers": 3700000, "videos": 3500, "views": 1800000000,
            "election_videos": 25, "election_views": 15000000,
        },
        "堀江貴文（ホリエモン）": {
            "category": "政治コメンテーター",
            "subscribers": 2180000, "videos": 8500, "views": 2200000000,
            "election_videos": 30, "election_views": 18000000,
        },
        "高橋洋一チャンネル": {
            "category": "政治コメンテーター",
            "subscribers": 1290000, "videos": 2800, "views": 751000000,
            "election_videos": 45, "election_views": 25000000,
        },
        "ReHacQ": {
            "category": "ビジネスメディア",
            "subscribers": 1000000, "videos": 1200, "views": 450000000,
            "election_videos": 20, "election_views": 12000000,
        },
        "竹田恒泰チャンネル": {
            "category": "政治コメンテーター",
            "subscribers": 773000, "videos": 3200, "views": 520000000,
            "election_videos": 35, "election_views": 14000000,
        },
        "文化人放送局": {
            "category": "政治コメンテーター",
            "subscribers": 740000, "videos": 5500, "views": 480000000,
            "election_videos": 40, "election_views": 12000000,
        },
        "上念司チャンネル": {
            "category": "政治コメンテーター",
            "subscribers": 644000, "videos": 2400, "views": 350000000,
            "election_videos": 38, "election_views": 10000000,
        },
        "一月万冊": {
            "category": "政治コメンテーター",
            "subscribers": 480000, "videos": 6000, "views": 380000000,
            "election_videos": 28, "election_views": 8000000,
        },
        # === 選挙専門・その他 ===
        "選挙ドットコム": {
            "category": "選挙専門メディア",
            "subscribers": 85000, "videos": 800, "views": 35000000,
            "election_videos": 55, "election_views": 9000000,
        },
    }

    rows = []
    for channel, stats in media_data.items():
        rows.append({
            "channel_name": channel,
            "category": stats["category"],
            "subscriber_count": stats["subscribers"] + random.randint(-10000, 10000),
            "total_video_count": stats["videos"] + random.randint(-100, 100),
            "total_view_count": stats["views"] + random.randint(-5000000, 5000000),
            "election_video_count": stats["election_videos"] + random.randint(-5, 5),
            "election_view_count": stats["election_views"] + random.randint(-500000, 500000),
            "avg_election_views": (stats["election_views"] // stats["election_videos"])
                                  + random.randint(-10000, 10000),
            "collected_at": datetime.now().isoformat(),
        })

    return pd.DataFrame(rows)


def generate_media_video_topics():
    """メディア動画の政党言及トピック分析（どの政党がどれだけ取り上げられたか）"""
    parties = PARTIES + ["公明党"]
    # 各メディアカテゴリから政党への言及割合（再生回数ベース）
    # 与党（自民+維新）は報道で多く取り上げられる傾向
    mention_weights = {
        "自由民主党":   0.28,
        "日本維新の会":  0.14,
        "立憲民主党":    0.16,
        "国民民主党":    0.10,
        "日本共産党":    0.04,
        "れいわ新選組":  0.06,
        "参政党":        0.04,
        "チームみらい":  0.08,
        "公明党":        0.06,
        "その他":        0.04,
    }

    # 総再生回数の85.7%がサードパーティ（メディア・YouTuber）由来
    total_third_party_views = 1800000000  # 18億回中の約85%

    rows = []
    for party, weight in mention_weights.items():
        base_views = int(total_third_party_views * weight)
        rows.append({
            "party_name": party,
            "media_mention_views": base_views + random.randint(-5000000, 5000000),
            "media_mention_share": round(weight * 100, 1),
            "tv_media_views": int(base_views * 0.55) + random.randint(-2000000, 2000000),
            "youtuber_views": int(base_views * 0.30) + random.randint(-1000000, 1000000),
            "other_creator_views": int(base_views * 0.15) + random.randint(-500000, 500000),
        })

    return pd.DataFrame(rows)


def generate_news_articles():
    """ニュース記事のサンプルデータ（主要メディアの選挙報道）"""
    sources = {
        "NHK": {"type": "公共放送", "credibility": 4.5, "political_lean": 0.0},
        "朝日新聞": {"type": "全国紙", "credibility": 4.0, "political_lean": -0.3},
        "読売新聞": {"type": "全国紙", "credibility": 4.0, "political_lean": 0.2},
        "毎日新聞": {"type": "全国紙", "credibility": 3.8, "political_lean": -0.2},
        "産経新聞": {"type": "全国紙", "credibility": 3.5, "political_lean": 0.4},
        "日本経済新聞": {"type": "経済紙", "credibility": 4.2, "political_lean": 0.1},
        "東京新聞": {"type": "地方紙", "credibility": 3.5, "political_lean": -0.4},
        "共同通信": {"type": "通信社", "credibility": 4.0, "political_lean": 0.0},
        "時事通信": {"type": "通信社", "credibility": 4.0, "political_lean": 0.0},
        "Yahoo!ニュース": {"type": "ポータル", "credibility": 3.2, "political_lean": 0.0},
        "東洋経済オンライン": {"type": "経済メディア", "credibility": 3.8, "political_lean": 0.0},
        "現代ビジネス": {"type": "Webメディア", "credibility": 3.3, "political_lean": -0.1},
        "文春オンライン": {"type": "Webメディア", "credibility": 3.5, "political_lean": 0.0},
        "AERAdot.": {"type": "Webメディア", "credibility": 3.3, "political_lean": -0.2},
        "NewsPicks": {"type": "経済メディア", "credibility": 3.5, "political_lean": 0.1},
    }

    # 記事テーマ
    article_topics = [
        "衆院選情勢調査", "各党の公約比較", "消費税政策", "安全保障政策",
        "経済対策", "候補者インタビュー", "選挙区情勢分析", "投票率予測",
        "世論調査結果", "党首討論", "街頭演説ルポ", "政策分析",
        "連立政権の行方", "若者の投票行動", "SNS選挙戦略", "AI政治の可能性",
        "チームみらい特集", "裏金問題と有権者", "比例代表制度解説", "期日前投票動向",
    ]

    base_date = datetime(2026, 1, 1)
    rows = []
    for i in range(600):
        pub_date = base_date + timedelta(
            days=random.randint(0, 38),
            hours=random.randint(6, 23),
            minutes=random.randint(0, 59),
        )
        days_from_start = (pub_date - base_date).days

        # 公示日以降は記事数増加
        article_boost = 1.0 + max(0, (days_from_start - 26)) * 0.5

        source_name = random.choice(list(sources.keys()))
        source_info = sources[source_name]

        # 政党への言及（複数政党に言及可能）
        mentioned_parties = []
        for party in PARTIES + ["公明党"]:
            # 与党は言及確率が高い
            base_prob = 0.15
            if party == "自由民主党":
                base_prob = 0.45
            elif party == "日本維新の会":
                base_prob = 0.30
            elif party == "立憲民主党":
                base_prob = 0.28
            elif party == "チームみらい":
                base_prob = 0.12
            if random.random() < base_prob:
                mentioned_parties.append(party)

        if not mentioned_parties:
            mentioned_parties = [random.choice(PARTIES)]

        # 記事のトーン（-1: 批判的, 0: 中立, 1: 肯定的）
        tone = round(random.gauss(source_info["political_lean"], 0.3), 2)
        tone = max(-1, min(1, tone))

        # PV数（記事アクセス数）
        base_pv = random.lognormvariate(9, 1.2)
        pv = int(base_pv * article_boost * (1 + source_info["credibility"] / 5))

        topic = random.choice(article_topics)

        rows.append({
            "article_id": f"news_{i:04d}",
            "source": source_name,
            "source_type": source_info["type"],
            "credibility_score": source_info["credibility"],
            "title": f"{topic}：{random.choice(mentioned_parties)}の{'動向' if random.random() > 0.5 else '政策'}",
            "published_at": pub_date.isoformat(),
            "topic": topic,
            "mentioned_parties": "|".join(mentioned_parties),
            "tone": tone,
            "page_views": pv,
            "comment_count": int(pv * random.uniform(0.01, 0.05)),
            "share_count": int(pv * random.uniform(0.005, 0.03)),
        })

    return pd.DataFrame(rows)


def generate_news_polling():
    """世論調査のサンプルデータ（各社の調査結果の時系列）"""
    survey_sources = ["NHK", "朝日新聞", "読売新聞", "毎日新聞", "共同通信", "日本経済新聞"]

    # 支持率のベースライン
    support_baseline = {
        "自由民主党": 32.0, "日本維新の会": 12.0, "立憲民主党": 10.0,
        "国民民主党": 8.0, "日本共産党": 3.5, "れいわ新選組": 4.0,
        "参政党": 2.5, "公明党": 4.0, "チームみらい": 3.0, "支持なし": 21.0,
    }

    rows = []
    base_date = datetime(2026, 1, 5)
    for week in range(6):  # 6週分
        survey_date = base_date + timedelta(weeks=week)
        for source in random.sample(survey_sources, k=random.randint(2, 4)):
            for party, base_rate in support_baseline.items():
                # 週ごとにわずかに変動
                drift = random.gauss(0, 0.8) + week * random.gauss(0, 0.2)
                rate = max(0.5, base_rate + drift)
                rows.append({
                    "survey_date": survey_date.strftime("%Y-%m-%d"),
                    "source": source,
                    "party_name": party,
                    "support_rate": round(rate, 1),
                    "sample_size": random.randint(1000, 2500),
                })

    return pd.DataFrame(rows)


def generate_news_daily_coverage():
    """日別のニュース報道量データ"""
    base_date = datetime(2026, 1, 1)
    rows = []
    for day_offset in range(39):
        date = base_date + timedelta(days=day_offset)
        # 公示日前後で報道量が増加
        base_articles = 15 + random.randint(-3, 3)
        if day_offset >= 26:  # 公示日以降
            base_articles = int(base_articles * (1.5 + (day_offset - 26) * 0.1))
        if day_offset >= 35:  # 投票日直前
            base_articles = int(base_articles * 1.8)

        rows.append({
            "date": date.strftime("%Y-%m-%d"),
            "article_count": base_articles,
            "total_page_views": base_articles * random.randint(8000, 25000),
            "avg_tone": round(random.gauss(0.0, 0.15), 3),
        })

    return pd.DataFrame(rows)


# === 選挙区・候補者データ生成 ===

# 都道府県コード → (名前, 小選挙区数)
PREFECTURE_DISTRICTS = {
    1: ("北海道", 12), 2: ("青森県", 3), 3: ("岩手県", 3), 4: ("宮城県", 6),
    5: ("秋田県", 3), 6: ("山形県", 3), 7: ("福島県", 5),
    8: ("茨城県", 7), 9: ("栃木県", 5), 10: ("群馬県", 5),
    11: ("埼玉県", 15), 12: ("千葉県", 13), 13: ("東京都", 25), 14: ("神奈川県", 17),
    15: ("新潟県", 6), 16: ("富山県", 3), 17: ("石川県", 3), 18: ("福井県", 2),
    19: ("山梨県", 2), 20: ("長野県", 5), 21: ("岐阜県", 5),
    22: ("静岡県", 8), 23: ("愛知県", 15), 24: ("三重県", 5),
    25: ("滋賀県", 4), 26: ("京都府", 6), 27: ("大阪府", 19), 28: ("兵庫県", 12),
    29: ("奈良県", 4), 30: ("和歌山県", 3),
    31: ("鳥取県", 2), 32: ("島根県", 2), 33: ("岡山県", 5),
    34: ("広島県", 7), 35: ("山口県", 4),
    36: ("徳島県", 2), 37: ("香川県", 3), 38: ("愛媛県", 4), 39: ("高知県", 2),
    40: ("福岡県", 11), 41: ("佐賀県", 2), 42: ("長崎県", 3),
    43: ("熊本県", 5), 44: ("大分県", 3), 45: ("宮崎県", 3),
    46: ("鹿児島県", 4), 47: ("沖縄県", 3),
}

# 比例ブロック
PR_BLOCKS = {
    "北海道": [1],
    "東北": [2, 3, 4, 5, 6, 7],
    "北関東": [8, 9, 10, 11],
    "南関東": [12, 14, 19],
    "東京": [13],
    "北陸信越": [15, 16, 17, 18, 20],
    "東海": [21, 22, 23, 24],
    "近畿": [25, 26, 27, 28, 29, 30],
    "中国": [31, 32, 33, 34, 35],
    "四国": [36, 37, 38, 39],
    "九州": [40, 41, 42, 43, 44, 45, 46, 47],
}

# 地域別の政党勝率パラメータ（各都道府県で各政党が選挙区を取る確率）
REGIONAL_PARTY_STRENGTH = {
    # 自民が強い地域
    "rural_ldp": {
        "自由民主党": 0.60, "立憲民主党": 0.15, "日本維新の会": 0.05,
        "国民民主党": 0.05, "公明党": 0.05, "日本共産党": 0.02,
        "れいわ新選組": 0.02, "参政党": 0.02, "チームみらい": 0.01, "無所属": 0.03,
    },
    # 都市部（首都圏）
    "urban_kanto": {
        "自由民主党": 0.30, "立憲民主党": 0.28, "日本維新の会": 0.10,
        "国民民主党": 0.10, "公明党": 0.05, "日本共産党": 0.04,
        "れいわ新選組": 0.04, "参政党": 0.02, "チームみらい": 0.05, "無所属": 0.02,
    },
    # 近畿（維新が強い）
    "kansai": {
        "自由民主党": 0.20, "立憲民主党": 0.12, "日本維新の会": 0.45,
        "国民民主党": 0.05, "公明党": 0.06, "日本共産党": 0.03,
        "れいわ新選組": 0.03, "参政党": 0.02, "チームみらい": 0.02, "無所属": 0.02,
    },
    # 北海道（立憲が比較的強い）
    "hokkaido": {
        "自由民主党": 0.40, "立憲民主党": 0.30, "日本維新の会": 0.05,
        "国民民主党": 0.08, "公明党": 0.05, "日本共産党": 0.04,
        "れいわ新選組": 0.03, "参政党": 0.02, "チームみらい": 0.01, "無所属": 0.02,
    },
}

# 都道府県→地域タイプのマッピング
PREFECTURE_REGION_TYPE = {
    1: "hokkaido",
    2: "rural_ldp", 3: "rural_ldp", 4: "urban_kanto", 5: "rural_ldp",
    6: "rural_ldp", 7: "rural_ldp",
    8: "urban_kanto", 9: "urban_kanto", 10: "urban_kanto",
    11: "urban_kanto", 12: "urban_kanto", 13: "urban_kanto", 14: "urban_kanto",
    15: "rural_ldp", 16: "rural_ldp", 17: "rural_ldp", 18: "rural_ldp",
    19: "rural_ldp", 20: "rural_ldp", 21: "rural_ldp",
    22: "urban_kanto", 23: "urban_kanto", 24: "rural_ldp",
    25: "kansai", 26: "kansai", 27: "kansai", 28: "kansai",
    29: "kansai", 30: "kansai",
    31: "rural_ldp", 32: "rural_ldp", 33: "rural_ldp",
    34: "rural_ldp", 35: "rural_ldp",
    36: "rural_ldp", 37: "rural_ldp", 38: "rural_ldp", 39: "rural_ldp",
    40: "urban_kanto", 41: "rural_ldp", 42: "rural_ldp",
    43: "rural_ldp", 44: "rural_ldp", 45: "rural_ldp",
    46: "rural_ldp", 47: "rural_ldp",
}

# サンプル候補者名プール
SURNAMES = [
    "佐藤", "鈴木", "高橋", "田中", "伊藤", "渡辺", "山本", "中村", "小林", "加藤",
    "吉田", "山田", "佐々木", "松本", "井上", "木村", "林", "斎藤", "清水", "山崎",
    "森", "池田", "橋本", "阿部", "石川", "山下", "中島", "前田", "藤田", "小川",
    "岡田", "後藤", "長谷川", "石井", "村上", "近藤", "坂本", "遠藤", "青木", "藤井",
    "西村", "福田", "太田", "三浦", "岡本", "松田", "中野", "原田", "小野", "田村",
    "竹内", "金子", "和田", "中山", "石田", "上田", "森田", "原", "柴田", "酒井",
    "工藤", "横山", "宮崎", "宮本", "内田", "高木", "安藤", "谷口", "大野", "丸山",
]
GIVEN_NAMES_M = [
    "太郎", "一郎", "健一", "誠", "浩", "隆", "修", "剛", "博", "正",
    "豊", "進", "勇", "翔", "大輔", "拓也", "雄一", "直樹", "和也", "哲也",
    "秀樹", "雅彦", "義明", "信二", "敏夫", "幸夫", "正義", "慎一", "光男", "英明",
]
GIVEN_NAMES_F = [
    "花子", "美咲", "陽子", "裕子", "真理子", "由美子", "恵子", "幸子", "明美", "和子",
    "京子", "久美子", "智子", "洋子", "節子", "千恵子", "直美", "麻衣", "彩", "美穂",
]


def generate_district_candidates():
    """289小選挙区の候補者サンプルデータを生成"""
    all_parties = list(REGIONAL_PARTY_STRENGTH["rural_ldp"].keys())

    rows = []
    for pref_code, (pref_name, n_districts) in PREFECTURE_DISTRICTS.items():
        region_type = PREFECTURE_REGION_TYPE[pref_code]
        party_probs = REGIONAL_PARTY_STRENGTH[region_type]

        for dist_num in range(1, n_districts + 1):
            district_name = f"{pref_name.replace('県','').replace('府','').replace('都','').replace('道','')}{dist_num}区"
            if pref_name == "北海道":
                district_name = f"北海道{dist_num}区"
            elif pref_name == "東京都":
                district_name = f"東京{dist_num}区"

            # この選挙区の候補者数（2〜4名）
            n_candidates = random.randint(2, 4)

            # 政党を確率で選択（重複なし）
            parties_pool = list(party_probs.keys())
            weights = [party_probs[p] for p in parties_pool]
            chosen_parties = []
            for _ in range(n_candidates):
                if not parties_pool:
                    break
                w_sum = sum(weights)
                normalized = [w / w_sum for w in weights]
                idx = random.choices(range(len(parties_pool)), weights=normalized, k=1)[0]
                chosen_parties.append(parties_pool[idx])
                parties_pool.pop(idx)
                weights.pop(idx)

            # 得票率を生成（1位が最も高い）
            vote_shares = sorted(
                [random.uniform(0.15, 0.50) for _ in range(n_candidates)],
                reverse=True,
            )
            # 正規化して合計85〜95%に（残りは泡沫候補扱い）
            total_share = random.uniform(0.85, 0.95)
            raw_sum = sum(vote_shares)
            vote_shares = [v / raw_sum * total_share for v in vote_shares]

            winner_share = vote_shares[0]
            margin = winner_share - vote_shares[1] if len(vote_shares) > 1 else winner_share

            for rank, (party, share) in enumerate(zip(chosen_parties, vote_shares), 1):
                is_male = random.random() > 0.25  # 75%男性
                surname = random.choice(SURNAMES)
                given = random.choice(GIVEN_NAMES_M if is_male else GIVEN_NAMES_F)
                name = f"{surname} {given}"

                rows.append({
                    "prefecture_code": pref_code,
                    "prefecture_name": pref_name,
                    "district_number": dist_num,
                    "district_name": district_name,
                    "candidate_name": name,
                    "party": party,
                    "age": random.randint(32, 75),
                    "is_incumbent": random.random() < (0.6 if rank == 1 else 0.2),
                    "predicted_vote_share": round(share, 4),
                    "predicted_rank": rank,
                    "margin": round(margin if rank == 1 else round(winner_share - share, 4), 4),
                    "youtube_score": round(random.uniform(0.1, 1.0), 3),
                    "news_mentions": random.randint(5, 120),
                })

    return pd.DataFrame(rows)


def generate_prefecture_summary():
    """都道府県別の選挙予測集約データ"""
    rows = []
    for pref_code, (pref_name, n_districts) in PREFECTURE_DISTRICTS.items():
        region_type = PREFECTURE_REGION_TYPE[pref_code]
        party_probs = REGIONAL_PARTY_STRENGTH[region_type]

        # 各政党の予測議席数（確率に基づくランダム配分）
        party_seats = {}
        remaining = n_districts
        sorted_parties = sorted(party_probs.items(), key=lambda x: -x[1])
        for i, (party, prob) in enumerate(sorted_parties):
            if i == len(sorted_parties) - 1:
                seats = remaining
            else:
                seats = min(remaining, round(n_districts * prob + random.gauss(0, 0.5)))
                seats = max(0, seats)
            party_seats[party] = seats
            remaining -= seats
            if remaining <= 0:
                break

        # 合計調整
        total = sum(party_seats.values())
        if total != n_districts:
            dominant = max(party_seats, key=party_seats.get)
            party_seats[dominant] += (n_districts - total)

        dominant_party = max(party_seats, key=party_seats.get)

        # 比例ブロック判定
        block_name = ""
        for block, prefs in PR_BLOCKS.items():
            if pref_code in prefs:
                block_name = block
                break

        rows.append({
            "prefecture_code": pref_code,
            "prefecture_name": pref_name,
            "region_block": block_name,
            "total_smd_seats": n_districts,
            "dominant_party": dominant_party,
            "自由民主党": party_seats.get("自由民主党", 0),
            "立憲民主党": party_seats.get("立憲民主党", 0),
            "日本維新の会": party_seats.get("日本維新の会", 0),
            "国民民主党": party_seats.get("国民民主党", 0),
            "公明党": party_seats.get("公明党", 0),
            "日本共産党": party_seats.get("日本共産党", 0),
            "れいわ新選組": party_seats.get("れいわ新選組", 0),
            "参政党": party_seats.get("参政党", 0),
            "チームみらい": party_seats.get("チームみらい", 0),
            "無所属": party_seats.get("無所属", 0),
            "battleground_count": random.randint(0, max(1, n_districts // 3)),
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

    # メディアチャンネルデータ
    df_media = generate_media_channels()
    df_media.to_csv(
        raw_dir / f"media_channels_{timestamp}.csv", index=False, encoding="utf-8-sig"
    )
    df_media.to_csv(
        processed_dir / "media_channels.csv", index=False, encoding="utf-8-sig"
    )

    # メディア政党言及分析
    df_media_topics = generate_media_video_topics()
    df_media_topics.to_csv(
        processed_dir / "media_party_mentions.csv", index=False, encoding="utf-8-sig"
    )

    # 感情分析
    sentiment_data = pd.DataFrame([
        {"sentiment": "positive", "count": 148},
        {"sentiment": "neutral", "count": 210},
        {"sentiment": "negative", "count": 142},
    ])
    sentiment_data.to_csv(processed_dir / "sentiment_counts.csv", index=False)

    # ニュース記事データ
    df_news = generate_news_articles()
    df_news.to_csv(
        processed_dir / "news_articles.csv", index=False, encoding="utf-8-sig"
    )

    # 世論調査データ
    df_polling = generate_news_polling()
    df_polling.to_csv(
        processed_dir / "news_polling.csv", index=False, encoding="utf-8-sig"
    )

    # 日別報道量
    df_daily_news = generate_news_daily_coverage()
    df_daily_news.to_csv(
        processed_dir / "news_daily_coverage.csv", index=False, encoding="utf-8-sig"
    )

    # 選挙区・候補者データ
    df_districts = generate_district_candidates()
    df_districts.to_csv(
        processed_dir / "district_candidates.csv", index=False, encoding="utf-8-sig"
    )

    df_pref_summary = generate_prefecture_summary()
    df_pref_summary.to_csv(
        processed_dir / "prefecture_summary.csv", index=False, encoding="utf-8-sig"
    )

    print(f"サンプルデータ生成完了!")
    print(f"  raw: {raw_dir}")
    print(f"  processed: {processed_dir}")


if __name__ == "__main__":
    generate_all_sample_data()
