"""
議席予測スクリプト
YouTubeデータと世論調査ベースラインから4つのモデルで第51回衆院選の議席数を予測する
"""
import re
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data"
PROCESSED_DIR = DATA_DIR / "processed"
RAW_DIR = DATA_DIR / "raw"

# === 定数 ===
TOTAL_SEATS = 465
SMD_SEATS = 289  # 小選挙区
PR_SEATS = 176   # 比例代表

KNOWN_PARTIES = [
    "自由民主党", "日本維新の会", "立憲民主党", "国民民主党",
    "日本共産党", "れいわ新選組", "参政党", "チームみらい",
]

# YouTubeデータにない政党の固定配分
KOMEITO_SEATS = 24
OTHERS_SEATS = 10
FIXED_SEATS = KOMEITO_SEATS + OTHERS_SEATS  # 34

# 世論調査ベースライン（合計465）
# チームみらい: 2025年参院選で比例151万票(2.6%)、朝日新聞調査で比例最大10議席予測
POLLING_BASELINE = {
    "自由民主党":   210,
    "日本維新の会":  95,
    "立憲民主党":    60,
    "公明党":        24,
    "国民民主党":    30,
    "日本共産党":    10,
    "れいわ新選組":  10,
    "参政党":         6,
    "チームみらい":   8,
    "その他":        12,
}

# 歴史的な小選挙区比率（過去選挙から推定）
HISTORICAL_SMD_RATIO = {
    "自由民主党":   0.60,
    "日本維新の会":  0.45,
    "立憲民主党":    0.65,
    "公明党":        0.40,
    "国民民主党":    0.50,
    "日本共産党":    0.10,
    "れいわ新選組":  0.20,
    "参政党":        0.10,
    "チームみらい":  0.15,  # 主に比例中心、小選挙区3候補のみ
    "その他":        0.90,
}

# エンゲージメントスコアの重み
ENGAGEMENT_WEIGHTS = {
    "campaign_views": 0.40,
    "campaign_likes": 0.20,
    "subscribers": 0.15,
    "channel_views": 0.15,
    "avg_views": 0.10,
}

# モデル設定
CUBE_EXPONENT = 2.5       # 小選挙区のキューブ法則指数
SENTIMENT_WEIGHT = 0.3    # 感情分析の最大調整幅 ±30%
POLLING_WEIGHT = 0.70     # Model 3: 世論調査の重み
YOUTUBE_WEIGHT = 0.30     # Model 3: YouTubeの重み
MOMENTUM_CLAMP = 0.15     # 勢い補正の上限

# アンサンブル重み
ENSEMBLE_WEIGHTS = {
    "model1": 0.20,
    "model2": 0.25,
    "model3": 0.55,
}

# 統合アンサンブル重み（Model 6）
COMBINED_ENSEMBLE_WEIGHTS = {
    "model4": 0.45,  # YouTubeアンサンブル
    "model5": 0.55,  # ニュース記事モデル
}

# ニュースモデルの重み
NEWS_COVERAGE_WEIGHT = 0.30     # 報道量の重み
NEWS_TONE_WEIGHT = 0.15         # 報道トーンの重み
NEWS_POLLING_WEIGHT = 0.55      # 世論調査の重み

ALL_PARTIES = list(POLLING_BASELINE.keys())
YOUTUBE_PARTIES = KNOWN_PARTIES  # YouTubeデータがある7政党


# === データ読み込み ===

def load_prediction_data():
    """予測に必要な全データを読み込む"""
    data = {}
    data["channels"] = pd.read_csv(PROCESSED_DIR / "channel_analysis.csv")
    data["party_stats"] = pd.read_csv(PROCESSED_DIR / "party_video_stats.csv")

    raw_videos = sorted(RAW_DIR.glob("video_details_*.csv"), reverse=True)
    if raw_videos:
        data["videos"] = pd.read_csv(raw_videos[0])
    else:
        data["videos"] = pd.DataFrame()

    comments_path = PROCESSED_DIR / "comments_with_sentiment.csv"
    if comments_path.exists():
        data["comments"] = pd.read_csv(comments_path)
    else:
        raw_comments = sorted(RAW_DIR.glob("comments_*.csv"), reverse=True)
        if raw_comments:
            data["comments"] = pd.read_csv(raw_comments[0])
            # 簡易感情分類
            data["comments"]["sentiment"] = "neutral"
        else:
            data["comments"] = pd.DataFrame()

    # ニュース記事データ
    news_path = PROCESSED_DIR / "news_articles.csv"
    data["news_articles"] = pd.read_csv(news_path) if news_path.exists() else pd.DataFrame()

    polling_path = PROCESSED_DIR / "news_polling.csv"
    data["news_polling"] = pd.read_csv(polling_path) if polling_path.exists() else pd.DataFrame()

    return data


def extract_party_from_title(title):
    """動画タイトルから政党名を抽出"""
    match = re.search(r"【(.+?)】", str(title))
    if match:
        text = match.group(1)
        for party in KNOWN_PARTIES:
            if party in text:
                return party
    return None


def derive_party_sentiment(data):
    """政党別の感情スコアを算出"""
    videos = data["videos"]
    comments = data["comments"]

    if videos.empty or comments.empty:
        return {p: 0.0 for p in KNOWN_PARTIES}

    videos = videos.copy()
    videos["party"] = videos["title"].apply(extract_party_from_title)

    merged = comments.merge(
        videos[["video_id", "party"]], on="video_id", how="left"
    )
    merged = merged.dropna(subset=["party"])

    if "sentiment" not in merged.columns:
        return {p: 0.0 for p in KNOWN_PARTIES}

    sentiment_scores = {}
    for party in KNOWN_PARTIES:
        party_comments = merged[merged["party"] == party]
        if len(party_comments) < 3:
            sentiment_scores[party] = 0.0
            continue
        total = len(party_comments)
        pos = (party_comments["sentiment"] == "positive").sum()
        neg = (party_comments["sentiment"] == "negative").sum()
        sentiment_scores[party] = (pos - neg) / total

    return sentiment_scores


# === 配分アルゴリズム ===

def dhondt_allocation(scores, total_seats):
    """ドント方式による比例代表議席配分"""
    seats = {party: 0 for party in scores}
    for _ in range(total_seats):
        quotients = {
            party: scores[party] / (seats[party] + 1)
            for party in scores if scores[party] > 0
        }
        if not quotients:
            break
        winner = max(quotients, key=quotients.get)
        seats[winner] += 1
    return seats


def cube_law_allocation(shares, total_seats):
    """キューブ法則による小選挙区議席配分"""
    adjusted = {p: s ** CUBE_EXPONENT for p, s in shares.items() if s > 0}
    total_adj = sum(adjusted.values())
    if total_adj == 0:
        return {p: 0 for p in shares}

    raw_seats = {p: (v / total_adj) * total_seats for p, v in adjusted.items()}
    seats = {p: round(v) for p, v in raw_seats.items()}
    # shareが0の政党を追加
    for p in shares:
        if p not in seats:
            seats[p] = 0

    seats = adjust_to_total(seats, total_seats, raw_seats)
    return seats


def adjust_to_total(seats, target, raw_values=None):
    """合計が正確にtargetになるよう調整"""
    current = sum(seats.values())
    diff = target - current
    if diff == 0:
        return seats

    if raw_values:
        remainders = {p: raw_values.get(p, 0) - seats[p] for p in seats}
    else:
        remainders = {p: 1.0 / (seats[p] + 1) for p in seats}

    sorted_parties = sorted(
        remainders.keys(),
        key=lambda p: remainders[p],
        reverse=(diff > 0),
    )

    for i in range(abs(diff)):
        if i < len(sorted_parties):
            p = sorted_parties[i]
            seats[p] += 1 if diff > 0 else -1
            seats[p] = max(0, seats[p])

    return seats


# === エンゲージメントスコア計算 ===

def compute_engagement_scores(data):
    """各政党のエンゲージメントスコアを計算"""
    channels = data["channels"].dropna(subset=["party_name"])
    party_stats = data["party_stats"]

    scores = {}
    for party in YOUTUBE_PARTIES:
        ch = channels[channels["party_name"] == party]
        ps = party_stats[party_stats["party_name"] == party]

        if ch.empty or ps.empty:
            scores[party] = 0.0
            continue

        ch = ch.iloc[0]
        ps = ps.iloc[0]

        scores[party] = {
            "subscribers": ch["subscriber_count"],
            "channel_views": ch["view_count"],
            "campaign_views": ps["total_views"],
            "campaign_likes": ps["total_likes"],
            "avg_views": ps["avg_views"],
        }

    # 正規化してスコア算出
    metrics = ["subscribers", "channel_views", "campaign_views", "campaign_likes", "avg_views"]
    max_vals = {}
    for m in metrics:
        vals = [s[m] for s in scores.values() if isinstance(s, dict)]
        max_vals[m] = max(vals) if vals else 1

    final_scores = {}
    for party, s in scores.items():
        if isinstance(s, dict):
            composite = sum(
                ENGAGEMENT_WEIGHTS[m] * (s[m] / max_vals[m])
                for m in metrics
            )
            final_scores[party] = composite
        else:
            final_scores[party] = 0.0

    return final_scores


def scores_to_shares(scores):
    """スコアをシェア（合計1.0）に変換"""
    total = sum(scores.values())
    if total == 0:
        n = len(scores)
        return {p: 1.0 / n for p in scores}
    return {p: v / total for p, v in scores.items()}


# === Model 1: YouTubeエンゲージメントシェアモデル ===

def model1_engagement_share(data):
    """YouTubeエンゲージメント指標のみで議席を予測"""
    scores = compute_engagement_scores(data)
    shares = scores_to_shares(scores)

    # 比例代表: ドント方式
    pr_available = PR_SEATS - round(KOMEITO_SEATS * 0.6) - round(OTHERS_SEATS * 0.1)
    pr_scores = {p: shares[p] * 1000 for p in YOUTUBE_PARTIES}
    pr_seats = dhondt_allocation(pr_scores, pr_available)

    # 小選挙区: キューブ法則
    smd_available = SMD_SEATS - round(KOMEITO_SEATS * 0.4) - round(OTHERS_SEATS * 0.9)
    smd_seats = cube_law_allocation(shares, smd_available)

    results = {}
    for party in YOUTUBE_PARTIES:
        results[party] = {
            "smd": smd_seats.get(party, 0),
            "pr": pr_seats.get(party, 0),
            "total": smd_seats.get(party, 0) + pr_seats.get(party, 0),
        }

    results["公明党"] = {"smd": round(KOMEITO_SEATS * 0.4), "pr": round(KOMEITO_SEATS * 0.6), "total": KOMEITO_SEATS}
    results["その他"] = {"smd": round(OTHERS_SEATS * 0.9), "pr": round(OTHERS_SEATS * 0.1), "total": OTHERS_SEATS}

    # 合計465に調整
    results = adjust_model_total(results)
    return results, scores, shares


# === Model 2: 感情分析加重モデル ===

def model2_sentiment_weighted(data, base_scores):
    """感情分析で加重したエンゲージメントモデル"""
    sentiment_scores = derive_party_sentiment(data)

    adjusted_scores = {}
    for party in YOUTUBE_PARTIES:
        adjustment = 1.0 + (sentiment_scores.get(party, 0.0) * SENTIMENT_WEIGHT)
        adjusted_scores[party] = base_scores.get(party, 0.0) * adjustment

    shares = scores_to_shares(adjusted_scores)

    pr_available = PR_SEATS - round(KOMEITO_SEATS * 0.6) - round(OTHERS_SEATS * 0.1)
    pr_scores = {p: shares[p] * 1000 for p in YOUTUBE_PARTIES}
    pr_seats = dhondt_allocation(pr_scores, pr_available)

    smd_available = SMD_SEATS - round(KOMEITO_SEATS * 0.4) - round(OTHERS_SEATS * 0.9)
    smd_seats = cube_law_allocation(shares, smd_available)

    results = {}
    for party in YOUTUBE_PARTIES:
        results[party] = {
            "smd": smd_seats.get(party, 0),
            "pr": pr_seats.get(party, 0),
            "total": smd_seats.get(party, 0) + pr_seats.get(party, 0),
        }

    results["公明党"] = {"smd": round(KOMEITO_SEATS * 0.4), "pr": round(KOMEITO_SEATS * 0.6), "total": KOMEITO_SEATS}
    results["その他"] = {"smd": round(OTHERS_SEATS * 0.9), "pr": round(OTHERS_SEATS * 0.1), "total": OTHERS_SEATS}

    results = adjust_model_total(results)
    return results, sentiment_scores


# === Model 3: 世論調査 + YouTubeモメンタムモデル ===

def model3_polling_momentum(data, youtube_shares):
    """世論調査ベースラインにYouTubeの勢いで補正"""
    polling_shares = {p: v / TOTAL_SEATS for p, v in POLLING_BASELINE.items()}

    blended_shares = {}
    for party in ALL_PARTIES:
        if party in YOUTUBE_PARTIES and party in youtube_shares:
            momentum = youtube_shares[party] - polling_shares[party]
            momentum = max(-MOMENTUM_CLAMP, min(MOMENTUM_CLAMP, momentum))
            blended = (POLLING_WEIGHT * polling_shares[party]
                       + YOUTUBE_WEIGHT * (polling_shares[party] + momentum))
        else:
            blended = polling_shares[party]
        blended_shares[party] = blended

    # 正規化
    total = sum(blended_shares.values())
    blended_shares = {p: v / total for p, v in blended_shares.items()}

    # 歴史的なSMD比率で分割
    results = {}
    for party in ALL_PARTIES:
        total_seats = round(blended_shares[party] * TOTAL_SEATS)
        smd_ratio = HISTORICAL_SMD_RATIO.get(party, 0.5)
        smd = round(total_seats * smd_ratio)
        pr = total_seats - smd
        results[party] = {"smd": smd, "pr": pr, "total": total_seats}

    results = adjust_model_total(results)
    return results, blended_shares


# === Model 4: アンサンブル ===

def model4_ensemble(m1_results, m2_results, m3_results):
    """3モデルの加重平均"""
    results = {}
    for party in ALL_PARTIES:
        m1 = m1_results.get(party, {"total": 0, "smd": 0, "pr": 0})
        m2 = m2_results.get(party, {"total": 0, "smd": 0, "pr": 0})
        m3 = m3_results.get(party, {"total": 0, "smd": 0, "pr": 0})

        total = (ENSEMBLE_WEIGHTS["model1"] * m1["total"]
                 + ENSEMBLE_WEIGHTS["model2"] * m2["total"]
                 + ENSEMBLE_WEIGHTS["model3"] * m3["total"])
        smd = (ENSEMBLE_WEIGHTS["model1"] * m1["smd"]
               + ENSEMBLE_WEIGHTS["model2"] * m2["smd"]
               + ENSEMBLE_WEIGHTS["model3"] * m3["smd"])
        pr = (ENSEMBLE_WEIGHTS["model1"] * m1["pr"]
              + ENSEMBLE_WEIGHTS["model2"] * m2["pr"]
              + ENSEMBLE_WEIGHTS["model3"] * m3["pr"])

        results[party] = {
            "total": round(total),
            "smd": round(smd),
            "pr": round(pr),
        }

    results = adjust_model_total(results)
    # smd + pr = total を保証
    for party in results:
        diff = results[party]["total"] - (results[party]["smd"] + results[party]["pr"])
        if diff != 0:
            results[party]["pr"] += diff

    return results


# === Model 5: ニュース記事モデル ===

def compute_news_scores(data):
    """ニュース記事の報道量・トーンから政党スコアを算出"""
    articles = data.get("news_articles", pd.DataFrame())
    polling = data.get("news_polling", pd.DataFrame())

    # 報道量スコア（政党別の言及PV）
    coverage_scores = {}
    if not articles.empty:
        for _, row in articles.iterrows():
            parties = str(row.get("mentioned_parties", "")).split("|")
            for party in parties:
                if party and party != "nan":
                    coverage_scores[party] = coverage_scores.get(party, 0) + row.get("page_views", 0)

    # トーンスコア（政党別の平均報道トーン）
    tone_scores = {}
    if not articles.empty:
        party_tones = {}
        for _, row in articles.iterrows():
            parties = str(row.get("mentioned_parties", "")).split("|")
            for party in parties:
                if party and party != "nan":
                    if party not in party_tones:
                        party_tones[party] = []
                    party_tones[party].append(row.get("tone", 0))
        for party, tones in party_tones.items():
            tone_scores[party] = sum(tones) / len(tones) if tones else 0

    # 世論調査スコア（最新の支持率）
    poll_scores = {}
    if not polling.empty:
        polling["survey_date"] = pd.to_datetime(polling["survey_date"])
        latest_date = polling["survey_date"].max()
        latest = polling[polling["survey_date"] == latest_date]
        avg_polls = latest.groupby("party_name")["support_rate"].mean()
        for party, rate in avg_polls.items():
            if party != "支持なし":
                poll_scores[party] = rate

    return coverage_scores, tone_scores, poll_scores


def model5_news_prediction(data):
    """ニュース記事データのみで議席を予測"""
    coverage_scores, tone_scores, poll_scores = compute_news_scores(data)

    # 全政党のスコア統合
    all_parties_in_news = set(list(coverage_scores.keys()) + list(poll_scores.keys()))
    # ALL_PARTIES に含まれるもののみ
    parties = [p for p in ALL_PARTIES if p in all_parties_in_news or p in POLLING_BASELINE]

    # 報道量を正規化
    max_coverage = max(coverage_scores.values()) if coverage_scores else 1
    norm_coverage = {p: coverage_scores.get(p, 0) / max_coverage for p in parties}

    # 世論調査を正規化
    total_poll = sum(poll_scores.values()) if poll_scores else 1
    norm_poll = {p: poll_scores.get(p, 0) / total_poll for p in parties}

    # 統合スコア = 世論調査(55%) + 報道量(30%) + トーン補正(15%)
    combined_scores = {}
    for party in parties:
        base = (NEWS_POLLING_WEIGHT * norm_poll.get(party, 0)
                + NEWS_COVERAGE_WEIGHT * norm_coverage.get(party, 0))
        # トーン補正: +の報道トーンはスコアを押し上げ
        tone_adj = 1.0 + (tone_scores.get(party, 0) * NEWS_TONE_WEIGHT * 2)
        combined_scores[party] = base * tone_adj

    # POLLING_BASELINE にあるがニュースに出てこない政党のフォールバック
    for party in ALL_PARTIES:
        if party not in combined_scores:
            combined_scores[party] = POLLING_BASELINE.get(party, 0) / TOTAL_SEATS * 0.5

    # 正規化
    total = sum(combined_scores.values())
    if total > 0:
        combined_scores = {p: v / total for p, v in combined_scores.items()}

    # 歴史的なSMD比率で分割
    results = {}
    for party in ALL_PARTIES:
        total_seats = round(combined_scores.get(party, 0) * TOTAL_SEATS)
        smd_ratio = HISTORICAL_SMD_RATIO.get(party, 0.5)
        smd = round(total_seats * smd_ratio)
        pr = total_seats - smd
        results[party] = {"smd": smd, "pr": pr, "total": total_seats}

    results = adjust_model_total(results)

    # ニューススコアを返す（ダッシュボード表示用）
    news_shares = combined_scores
    return results, news_shares, coverage_scores, tone_scores, poll_scores


# === Model 6: 統合アンサンブル（YouTube + ニュース）===

def model6_combined_ensemble(m4_results, m5_results):
    """YouTubeアンサンブル(M4) + ニュース記事モデル(M5) の統合予測"""
    w4 = COMBINED_ENSEMBLE_WEIGHTS["model4"]
    w5 = COMBINED_ENSEMBLE_WEIGHTS["model5"]

    results = {}
    for party in ALL_PARTIES:
        m4 = m4_results.get(party, {"total": 0, "smd": 0, "pr": 0})
        m5 = m5_results.get(party, {"total": 0, "smd": 0, "pr": 0})

        total = w4 * m4["total"] + w5 * m5["total"]
        smd = w4 * m4["smd"] + w5 * m5["smd"]
        pr = w4 * m4["pr"] + w5 * m5["pr"]

        results[party] = {
            "total": round(total),
            "smd": round(smd),
            "pr": round(pr),
        }

    results = adjust_model_total(results)
    for party in results:
        diff = results[party]["total"] - (results[party]["smd"] + results[party]["pr"])
        if diff != 0:
            results[party]["pr"] += diff

    return results


def adjust_model_total(results):
    """全モデル結果の合計を465に調整"""
    current = sum(r["total"] for r in results.values())
    diff = TOTAL_SEATS - current
    if diff == 0:
        return results

    # 最大政党から調整
    sorted_parties = sorted(results.keys(), key=lambda p: results[p]["total"], reverse=True)
    for i in range(abs(diff)):
        p = sorted_parties[i % len(sorted_parties)]
        adj = 1 if diff > 0 else -1
        results[p]["total"] += adj
        # smdかprも調整
        if results[p]["smd"] > results[p]["pr"]:
            results[p]["smd"] += adj
        else:
            results[p]["pr"] += adj

    return results


# === CSV出力 ===

def save_predictions(m1, m2, m3, m4, m5, m6,
                     eng_scores, sentiment_scores, youtube_shares, blended_shares,
                     news_shares):
    """予測結果をCSVに保存"""
    rows = []
    for party in ALL_PARTIES:
        row = {
            "party_name": party,
            "model1_total": m1.get(party, {}).get("total", 0),
            "model1_smd": m1.get(party, {}).get("smd", 0),
            "model1_pr": m1.get(party, {}).get("pr", 0),
            "model2_total": m2.get(party, {}).get("total", 0),
            "model2_smd": m2.get(party, {}).get("smd", 0),
            "model2_pr": m2.get(party, {}).get("pr", 0),
            "model3_total": m3.get(party, {}).get("total", 0),
            "model3_smd": m3.get(party, {}).get("smd", 0),
            "model3_pr": m3.get(party, {}).get("pr", 0),
            "model4_total": m4.get(party, {}).get("total", 0),
            "model4_smd": m4.get(party, {}).get("smd", 0),
            "model4_pr": m4.get(party, {}).get("pr", 0),
            "model5_total": m5.get(party, {}).get("total", 0),
            "model5_smd": m5.get(party, {}).get("smd", 0),
            "model5_pr": m5.get(party, {}).get("pr", 0),
            "model6_total": m6.get(party, {}).get("total", 0),
            "model6_smd": m6.get(party, {}).get("smd", 0),
            "model6_pr": m6.get(party, {}).get("pr", 0),
            "engagement_score": eng_scores.get(party, 0.0),
            "sentiment_score": sentiment_scores.get(party, 0.0),
            "polling_baseline": POLLING_BASELINE.get(party, 0),
            "polling_baseline_smd": round(POLLING_BASELINE.get(party, 0) * HISTORICAL_SMD_RATIO.get(party, 0.5)),
            "polling_baseline_pr": POLLING_BASELINE.get(party, 0) - round(POLLING_BASELINE.get(party, 0) * HISTORICAL_SMD_RATIO.get(party, 0.5)),
            "youtube_share": youtube_shares.get(party, 0.0),
            "blended_share": blended_shares.get(party, 0.0),
            "news_share": news_shares.get(party, 0.0),
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    out_path = PROCESSED_DIR / "seat_predictions.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"  予測結果保存: {out_path}")
    return df


# === メイン実行 ===

def run_predictions():
    """全モデルを実行"""
    print("=" * 60)
    print("議席予測を実行中...")
    print("=" * 60)

    data = load_prediction_data()

    # Model 1
    print("\n[Model 1] YouTubeエンゲージメントシェアモデル")
    m1_results, eng_scores, youtube_shares = model1_engagement_share(data)
    print_results(m1_results)

    # Model 2
    print("\n[Model 2] 感情分析加重エンゲージメントモデル")
    m2_results, sentiment_scores = model2_sentiment_weighted(data, eng_scores)
    print_results(m2_results)

    # Model 3
    print("\n[Model 3] 世論調査 + YouTubeモメンタムモデル")
    m3_results, blended_shares = model3_polling_momentum(data, youtube_shares)
    print_results(m3_results)

    # Model 4
    print("\n[Model 4] YouTubeアンサンブル予測")
    m4_results = model4_ensemble(m1_results, m2_results, m3_results)
    print_results(m4_results)

    # Model 5
    print("\n[Model 5] ニュース記事モデル")
    m5_results, news_shares, coverage_scores, tone_scores, poll_scores = model5_news_prediction(data)
    print_results(m5_results)

    # Model 6
    print("\n[Model 6] 統合アンサンブル（YouTube + ニュース）")
    m6_results = model6_combined_ensemble(m4_results, m5_results)
    print_results(m6_results)

    # CSV保存
    df = save_predictions(
        m1_results, m2_results, m3_results, m4_results,
        m5_results, m6_results,
        eng_scores, sentiment_scores, youtube_shares, blended_shares,
        news_shares,
    )

    print("\n" + "=" * 60)
    print("議席予測完了!")
    print("=" * 60)

    return df


def print_results(results):
    """モデル結果を表示"""
    total = 0
    for party in ALL_PARTIES:
        r = results.get(party, {"total": 0, "smd": 0, "pr": 0})
        print(f"  {party:12s}: {r['total']:4d}議席 (小選挙区{r['smd']:3d} + 比例{r['pr']:3d})")
        total += r["total"]
    print(f"  {'合計':12s}: {total:4d}議席")


if __name__ == "__main__":
    run_predictions()
