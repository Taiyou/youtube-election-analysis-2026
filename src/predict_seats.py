"""
議席予測スクリプト
YouTubeデータ・ニュース記事・世論調査から7つのモデルで第51回衆院選の議席数を予測する
"""
import math
import re

import numpy as np
import pandas as pd

from config import (
    DATA_DIR,
    KOMEITO_SMD_RATIO,
    KOMEITO_PR_RATIO,
    OTHERS_SMD_RATIO,
    OTHERS_PR_RATIO,
    REGIONAL_PARTY_STRENGTH,
    PREFECTURE_REGION_TYPE,
    PREFECTURE_DISTRICTS,
    PR_BLOCK_PREFECTURES,
)

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

# 選挙日（時間減衰計算用）
ELECTION_DATE = pd.Timestamp("2026-02-08", tz="UTC")

# 過去選挙の実績データ（キューブ法則指数の較正用）
HISTORICAL_ELECTIONS = {
    2024: {
        "自由民主党":   {"vote_share": 0.383, "seat_share": 0.457},
        "立憲民主党":   {"vote_share": 0.297, "seat_share": 0.360},
        "日本維新の会": {"vote_share": 0.078, "seat_share": 0.014},
        "国民民主党":   {"vote_share": 0.068, "seat_share": 0.038},
        "日本共産党":   {"vote_share": 0.071, "seat_share": 0.003},
        "れいわ新選組": {"vote_share": 0.032, "seat_share": 0.000},
        "公明党":       {"vote_share": 0.028, "seat_share": 0.028},
    },
    2021: {
        "自由民主党":   {"vote_share": 0.481, "seat_share": 0.648},
        "立憲民主党":   {"vote_share": 0.299, "seat_share": 0.187},
        "日本維新の会": {"vote_share": 0.084, "seat_share": 0.055},
        "国民民主党":   {"vote_share": 0.027, "seat_share": 0.021},
        "日本共産党":   {"vote_share": 0.064, "seat_share": 0.003},
        "公明党":       {"vote_share": 0.019, "seat_share": 0.031},
    },
    2017: {
        "自由民主党":   {"vote_share": 0.476, "seat_share": 0.749},
        "立憲民主党":   {"vote_share": 0.087, "seat_share": 0.063},
        "希望の党":     {"vote_share": 0.235, "seat_share": 0.063},
        "日本共産党":   {"vote_share": 0.094, "seat_share": 0.003},
        "公明党":       {"vote_share": 0.014, "seat_share": 0.028},
    },
}

# 世論調査ベースライン（合計465）
# news_polling.csv の時間加重平均支持率（half-life=10日）から比例配分で算出
# 自民32.3%, 維新12.5%, 立憲10.3%, 国民9.1%, れいわ4.5%, 公明3.8%,
# 共産3.2%, チームみらい2.8%, 参政2.7%  → 「その他」に最低限を確保
POLLING_BASELINE = {
    "自由民主党":   183,
    "日本維新の会":  71,
    "立憲民主党":    59,
    "公明党":        21,
    "国民民主党":    52,
    "日本共産党":    18,
    "れいわ新選組":  25,
    "参政党":        15,
    "チームみらい":  16,
    "その他":         5,
}

# 歴史的な小選挙区比率
HISTORICAL_SMD_RATIO = {
    "自由民主党":   0.60,
    "日本維新の会":  0.40,
    "立憲民主党":    0.65,
    "公明党":        0.40,
    "国民民主党":    0.50,
    "日本共産党":    0.10,
    "れいわ新選組":  0.20,
    "参政党":        0.10,
    "チームみらい":  0.15,
    "その他":        0.90,
}

# エンゲージメントスコアの重み（成長率追加）
ENGAGEMENT_WEIGHTS = {
    "campaign_views": 0.35,
    "campaign_likes": 0.20,
    "subscribers": 0.10,
    "channel_views": 0.10,
    "avg_views": 0.10,
    "growth_rate": 0.15,
}

# モデル設定
CUBE_EXPONENT_DEFAULT = 2.0
SENTIMENT_WEIGHT = 0.3
POLLING_WEIGHT = 0.75   # 旧0.60→0.75: 世論調査の比重を上げる
YOUTUBE_WEIGHT = 0.25   # 旧0.40→0.25: YouTubeモメンタムを控えめに
MOMENTUM_CLAMP = 0.10   # 旧0.20→0.10: モメンタムの振れ幅を制限

# アンサンブル重み
# M3（世論調査ベース）の比重を上げ、M1/M2（YouTube純粋）を下げる
ENSEMBLE_WEIGHTS = {
    "model1": 0.15,     # 旧0.25
    "model2": 0.15,     # 旧0.25
    "model3": 0.70,     # 旧0.50: 世論調査を含むM3を重視
}

# 統合アンサンブル重み（Model 6）
COMBINED_ENSEMBLE_WEIGHTS = {
    "model4": 0.55,     # 旧0.70: YouTube系の比重を下げる
    "model5": 0.45,     # 旧0.30: ニュース（世論調査含む）の比重を上げる
}

# ニュースモデルの重み（世論調査を主軸に）
NEWS_COVERAGE_WEIGHT = 0.25   # 旧0.35: ニュース報道量
NEWS_TONE_WEIGHT = 0.05       # 旧0.10: 報道のトーン
NEWS_POLLING_WEIGHT = 0.45    # 旧0.30→0.45: 世論調査を最重視
NEWS_MEDIA_WEIGHT = 0.25      # メディア言及は据え置き

# 時間減衰パラメータ
TIME_DECAY_LAMBDA = 0.05
RECENCY_HALF_LIFE_DAYS = 7
POLL_DECAY_HALF_LIFE_DAYS = 10

# Model 7: 選挙区ボトムアップ予測の信号重み（v2: 先行研究ベース）
# 参考: 538 House Forecast, Cook PVI, Lewis-Beck & Tien (2012)
# partisan_lean を最重要変数に（538方式）、現職ボーナスは日本のRD研究に合わせ控えめ
DISTRICT_SIGNAL_WEIGHTS = {
    "partisan_lean":      0.35,  # 前回選挙の選挙区結果（538最重要変数: Cook PVI相当）
    "polling_swing":      0.25,  # 世論調査からの政党支持率変動
    "candidate_strength": 0.10,  # 候補者の個人的強さ（経験・区分）
    "incumbency":         0.05,  # 現職ボーナス（日本では弱い: Upham 2016 RD研究）
    "youtube_score":      0.15,  # YouTubeエンゲージメント（独自変数）
    "news_score":         0.10,  # ニュース言及（独自変数）
}
# 日本の現職優位は欧米より弱い（RD分析: 比例復活制度、政党要因の方が重要）
# 538のincumbency bonus 3.6ptに対し、日本では1-2pt相当に抑制
INCUMBENT_BONUS_VALUE = 0.02  # 旧: 0.08 → 0.02 (日本のRD研究に基づく)

# 2024年衆院選の選挙区結果ファイル
SMD_2024_RESULTS_FILE = "smd_2024_results.csv"

ALL_PARTIES = list(POLLING_BASELINE.keys())
YOUTUBE_PARTIES = KNOWN_PARTIES


# === キューブ法則指数の較正 ===

def calibrate_cube_exponent():
    """過去選挙の得票率→議席率データからキューブ法則指数を較正"""
    best_exp = CUBE_EXPONENT_DEFAULT
    best_error = float("inf")

    for exp in [x / 10.0 for x in range(15, 41)]:
        total_error = 0.0
        count = 0
        for year, parties in HISTORICAL_ELECTIONS.items():
            vote_shares = {p: d["vote_share"] for p, d in parties.items() if d["vote_share"] > 0}
            actual_seats = {p: d["seat_share"] for p, d in parties.items()}

            adjusted = {p: s ** exp for p, s in vote_shares.items()}
            total_adj = sum(adjusted.values())
            if total_adj == 0:
                continue
            predicted = {p: v / total_adj for p, v in adjusted.items()}

            for p in vote_shares:
                total_error += (predicted[p] - actual_seats.get(p, 0)) ** 2
                count += 1

        if count > 0:
            mse = total_error / count
            if mse < best_error:
                best_error = mse
                best_exp = exp

    return best_exp


CUBE_EXPONENT = calibrate_cube_exponent()


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
            data["comments"]["sentiment"] = "neutral"
        else:
            data["comments"] = pd.DataFrame()

    news_path = PROCESSED_DIR / "news_articles.csv"
    data["news_articles"] = pd.read_csv(news_path) if news_path.exists() else pd.DataFrame()

    polling_path = PROCESSED_DIR / "news_polling.csv"
    data["news_polling"] = pd.read_csv(polling_path) if polling_path.exists() else pd.DataFrame()

    # メディア言及データ
    media_path = PROCESSED_DIR / "media_party_mentions.csv"
    data["media_mentions"] = pd.read_csv(media_path) if media_path.exists() else pd.DataFrame()

    # 候補者データ（議席上限制約用 + Model 7用）
    candidates_path = PROCESSED_DIR / "district_candidates.csv"
    if candidates_path.exists():
        raw_cand = pd.read_csv(candidates_path)
        data["candidates"] = _prepare_candidates(raw_cand, data)
    else:
        data["candidates"] = pd.DataFrame()

    return data


def _prepare_candidates(raw_cand, data):
    """日本語カラムCSVを Model 7 が期待する英語カラム形式に変換し、
    先行研究ベースの6信号を算出する（v2: 538/Cook PVI方式）"""
    if raw_cand.empty:
        return raw_cand

    # 日本語カラム版の場合のみ変換（英語カラム版ならそのまま通す）
    if "政党名" not in raw_cand.columns:
        return raw_cand

    cand = raw_cand.copy()

    # --- 基本カラム変換 ---
    cand["candidate_name"] = cand["候補者名"]
    cand["age"] = cand["年齢"]

    # 中道改革連合はそのまま保持（立憲民主党+公明党の統一候補）
    # Model 7 では中道改革連合として選挙区予測し、最終集計で立憲+公明に配分
    cand["party"] = cand["政党名"]
    cand["original_party"] = cand["政党名"]

    # 区分→is_incumbent
    cand["is_incumbent"] = (cand["区分"].isin(["現職", "前職"])).astype(int)

    # 選挙区名→prefecture_code, district_number
    _PREF_SHORT_TO_CODE = {}
    for code, (full_name, _) in PREFECTURE_DISTRICTS.items():
        short = full_name
        for suffix in ["都", "府", "県"]:
            if short.endswith(suffix):
                short = short[:-1]
                break
        _PREF_SHORT_TO_CODE[short] = code
    _PREF_NAMES = {code: name for code, (name, _) in PREFECTURE_DISTRICTS.items()}

    def _parse_district(d):
        m = re.match(r"^(.+?)(\d+)区$", d)
        if not m:
            return None, None
        return _PREF_SHORT_TO_CODE.get(m.group(1)), int(m.group(2))

    parsed = cand["選挙区名"].apply(_parse_district)
    cand["prefecture_code"] = parsed.apply(lambda x: x[0])
    cand["district_number"] = parsed.apply(lambda x: x[1])
    cand["prefecture_name"] = cand["prefecture_code"].map(_PREF_NAMES)
    cand["district_name"] = cand["選挙区名"]

    # --- ① partisan_lean: 前回(2024)選挙区結果ベースの党派性スコア ---
    # 538の最重要変数。前回選挙でどの政党がその選挙区を制したかを基に
    # 候補者の政党がその選挙区でどの程度有利かを定量化する
    cand["partisan_lean"] = _compute_partisan_lean(cand, data)

    # --- ② polling_swing: 世論調査の支持率変動 ---
    # 前回2024年選挙時の得票率 vs 現在の世論調査支持率の変動幅
    cand["polling_swing"] = _compute_polling_swing(cand, data)

    # --- ③ candidate_strength: 候補者の個人的強さ ---
    # 538のcandidate experience + fundraisingに相当
    KUBUN_STRENGTH = {
        "現職": 0.30, "前職": 0.22, "元職": 0.12, "新人": 0.05, "不明": 0.03,
    }
    cand["candidate_strength"] = cand["区分"].map(KUBUN_STRENGTH).fillna(0.03)

    # --- ④ incumbency: 現職ボーナス（日本のRD研究で弱いことが判明） ---
    cand["incumbency"] = cand["is_incumbent"].astype(float) * INCUMBENT_BONUS_VALUE

    # --- ⑤ youtube_score: 政党レベルのエンゲージメントスコア ---
    cand["youtube_score"] = 0.0
    try:
        channels = data.get("channels", pd.DataFrame())
        party_stats = data.get("party_stats", pd.DataFrame())
        if not channels.empty and not party_stats.empty:
            eng_scores = compute_engagement_scores(data)
            max_eng = max(eng_scores.values()) if eng_scores else 1
            for party, score in eng_scores.items():
                cand.loc[cand["party"] == party, "youtube_score"] = score / max_eng
            # 中道改革連合 = 立憲のYouTubeスコアを継承（公明はYouTubeデータなし）
            ritsumin_yt = eng_scores.get("立憲民主党", 0) / max_eng if max_eng else 0
            cand.loc[cand["party"] == "中道改革連合", "youtube_score"] = ritsumin_yt
    except Exception:
        pass

    # --- ⑥ news_score: ニュース言及（0-1正規化） ---
    cand["news_mentions"] = 0.0
    try:
        articles = data.get("news_articles", pd.DataFrame())
        if not articles.empty and "mentioned_parties" in articles.columns:
            party_mention_count = {}
            for parties_str in articles["mentioned_parties"].dropna():
                for p in str(parties_str).split("|"):
                    if p and p != "nan":
                        party_mention_count[p] = party_mention_count.get(p, 0) + 1
            for party, count in party_mention_count.items():
                cand.loc[cand["party"] == party, "news_mentions"] = count
            # 中道改革連合 = 立憲 + 公明 のニュース言及を合算
            chudo_mentions = (
                party_mention_count.get("立憲民主党", 0)
                + party_mention_count.get("公明党", 0)
            )
            cand.loc[cand["party"] == "中道改革連合", "news_mentions"] = chudo_mentions
    except Exception:
        pass  # ニュースデータがない場合は0のまま

    # predicted_vote_share を後方互換性のため残す（出力用）
    cand["predicted_vote_share"] = cand["partisan_lean"] + cand["polling_swing"]

    return cand


def _compute_partisan_lean(cand, data):
    """前回(2024)選挙区結果に基づく党派性スコアを算出。
    538のPartisan Lean / Cook PVI に相当する最重要変数。
    その選挙区を前回どの政党が制したかで、候補者の政党に有利/不利スコアを付与。

    中道改革連合の扱い:
      2026年の中道改革連合 = 立憲民主党 + 公明党 の統一候補。
      2024年選挙区結果で立憲民主党 OR 公明党が勝った選挙区は、
      中道改革連合候補にとって有利な「自陣営の前回勝利」として扱う。
    """
    # 2024年選挙区結果を読み込み
    results_path = PROCESSED_DIR / SMD_2024_RESULTS_FILE
    if not results_path.exists():
        return _fallback_vote_share_baseline(cand)

    results_2024 = pd.read_csv(results_path)

    # 中道改革連合の構成政党（2024年時点の個別政党名）
    CHUDO_MEMBERS_2024 = {"立憲民主党", "公明党"}

    # 選挙区キーを作成（district_name で結合）
    district_winner = {}
    district_margin = {}
    for _, row in results_2024.iterrows():
        dn = row.get("district_name")
        if pd.notna(dn):
            district_winner[dn] = row.get("winner_party_jp", "")
            margin = row.get("margin")
            district_margin[dn] = float(margin) / 100.0 if pd.notna(margin) else 0.05

    # 全国の2024年SMD勝者分布から政党別の勝率を算出
    total_districts = len(district_winner)
    party_win_rate_2024 = {}
    for party in ALL_PARTIES + ["中道改革連合"]:
        if party == "中道改革連合":
            # 中道改革連合 = 立憲 + 公明 の合計勝率
            wins = sum(1 for w in district_winner.values() if w in CHUDO_MEMBERS_2024)
        else:
            wins = sum(1 for w in district_winner.values() if w == party)
        party_win_rate_2024[party] = wins / max(total_districts, 1)

    def _is_party_match(candidate_party, winner_2024):
        """候補者の政党と前回勝者が同一陣営かどうか判定"""
        if candidate_party == "中道改革連合":
            # 中道改革連合候補: 立憲 OR 公明が前回勝っていれば自陣営の勝利
            return winner_2024 in CHUDO_MEMBERS_2024
        return candidate_party == winner_2024

    # 各候補者の partisan_lean を計算
    lean_scores = []
    for _, row in cand.iterrows():
        party = row["party"]
        district = row.get("district_name", row.get("選挙区名", ""))

        winner_2024 = district_winner.get(district, "")
        margin_2024 = district_margin.get(district, 0.05)

        if _is_party_match(party, winner_2024):
            # この候補者の政党（陣営）が前回勝った選挙区 → 有利
            lean = 0.40 + min(margin_2024, 0.20) * 1.5
            # 中道改革連合は2026年の新連合なので、前回の個別政党勝利からの
            # 引き継ぎに不確実性がある（組織統合コスト）→ 10%割引
            if party == "中道改革連合":
                lean *= 0.90
        elif winner_2024 == "":
            lean = party_win_rate_2024.get(party, 0.02) * 0.5 + 0.10
        else:
            # 前回は別の政党が勝った → 不利だが、接戦なら可能性あり
            lean = max(0.05, 0.25 - margin_2024 * 1.0)

        # 地域補正を軽く加味
        rt = PREFECTURE_REGION_TYPE.get(row.get("prefecture_code"), "rural_ldp")
        region_profile = REGIONAL_PARTY_STRENGTH.get(rt, {})
        # 中道改革連合は立憲の地域強度を参照
        lookup_party = "立憲民主党" if party == "中道改革連合" else party
        regional = region_profile.get(lookup_party, 0.02)
        national_avg = sum(
            r.get(lookup_party, 0.02) for r in REGIONAL_PARTY_STRENGTH.values()
        ) / max(len(REGIONAL_PARTY_STRENGTH), 1)
        regional_delta = (regional - national_avg) * 0.15
        lean += regional_delta

        lean_scores.append(max(lean, 0.01))

    return pd.Series(lean_scores, index=cand.index)


def _compute_polling_swing(cand, data):
    """世論調査の支持率変動スコア。
    前回2024年選挙時の全国得票率 vs 現在のPOLLING_BASELINEの変動幅を候補者に反映。

    中道改革連合の扱い:
      2024年の立憲民主党+公明党の合計得票率 vs 現在の立憲+公明の合計支持率。
    """
    # 2024年衆院選の全国SMD得票率（公式結果）
    VOTE_SHARE_2024 = {
        "自由民主党":   0.3846,
        "立憲民主党":   0.2901,
        "日本維新の会":  0.1115,
        "日本共産党":   0.0681,
        "国民民主党":   0.0433,
        "公明党":       0.0135,
        "れいわ新選組":  0.0100,
        "参政党":       0.0029,
        "チームみらい":  0.0010,
        "その他":       0.0750,
    }
    # 中道改革連合 = 立憲 + 公明 の2024年合計得票率
    VOTE_SHARE_2024["中道改革連合"] = (
        VOTE_SHARE_2024.get("立憲民主党", 0) + VOTE_SHARE_2024.get("公明党", 0)
    )

    # 現在の世論調査支持率（POLLING_BASELINEから算出）
    total_baseline = sum(POLLING_BASELINE.values())
    current_shares = {p: v / total_baseline for p, v in POLLING_BASELINE.items()}
    # 中道改革連合 = 立憲 + 公明 の現在合計支持率
    current_shares["中道改革連合"] = (
        current_shares.get("立憲民主党", 0) + current_shares.get("公明党", 0)
    )

    # 各政党のスイング（変動幅）
    party_swing = {}
    for party in list(ALL_PARTIES) + ["中道改革連合"]:
        prev = VOTE_SHARE_2024.get(party, 0.01)
        curr = current_shares.get(party, 0.01)
        party_swing[party] = (curr - prev) * 0.5

    swing_scores = cand["party"].map(party_swing).fillna(0.0)
    return swing_scores


def _fallback_vote_share_baseline(cand):
    """2024年選挙区結果がない場合のフォールバック（旧方式）"""
    SMD_VOTE_SHARE_BASELINE = {
        "自由民主党":   0.38, "立憲民主党":   0.30, "日本維新の会": 0.25,
        "国民民主党":   0.22, "れいわ新選組": 0.08, "日本共産党":   0.06,
        "参政党":       0.04, "公明党":       0.15, "チームみらい": 0.05,
        "無所属":       0.12, "その他":       0.03,
    }
    return cand["party"].map(SMD_VOTE_SHARE_BASELINE).fillna(0.03)


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
    """政党別の感情スコアを算出（連続値スコア対応）"""
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

    # sentiment_scoreがある場合（連続値）はそれを使う
    if "sentiment_score" in merged.columns:
        sentiment_scores = {}
        for party in KNOWN_PARTIES:
            party_comments = merged[merged["party"] == party]
            if len(party_comments) < 3:
                sentiment_scores[party] = 0.0
            else:
                sentiment_scores[party] = party_comments["sentiment_score"].mean()
        return sentiment_scores

    if "sentiment" not in merged.columns:
        return {p: 0.0 for p in KNOWN_PARTIES}

    # フォールバック: 3値分類からスコア算出
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


# === 候補者数上限制約 ===

def compute_candidate_caps(data):
    """政党別の候補者数から小選挙区・比例代表の議席上限を算出

    比例代表は重複立候補 + 比例単独候補があるため、小選挙区候補数よりも
    かなり多い候補者を擁立できる。実際の比例名簿は小選挙区候補の2-3倍。
    """
    candidates = data.get("candidates", pd.DataFrame())
    if candidates.empty:
        return {}

    # 「無所属」→「その他」にマッピング
    cand = candidates.copy()
    if "party" not in cand.columns:
        return {}  # カラム不足の場合はスキップ
    cand["party"] = cand["party"].replace({"無所属": "その他"})

    # 中道改革連合の候補者数を立憲民主党と公明党に加算
    # （中道改革連合 = 立憲 + 公明 の統一候補として出馬しているため）
    # 2024年SMD実績比で配分（立憲104:公明4 ≈ 96:4）
    chudo_count = len(cand[cand["party"] == "中道改革連合"])
    RITSUMIN_SMD_2024 = 104
    KOMEITO_SMD_2024 = 4
    chudo_ratio_r = RITSUMIN_SMD_2024 / max(RITSUMIN_SMD_2024 + KOMEITO_SMD_2024, 1)
    chudo_to_ritsumin_cap = round(chudo_count * chudo_ratio_r)
    chudo_to_komeito_cap = chudo_count - chudo_to_ritsumin_cap

    # 比例名簿の想定候補数
    # 実際の選挙では比例単独候補も多数擁立するため、比例上限は世論調査ベースラインの
    # 比例分を下限とし、SMD候補数も加味する。PR全体の上限(176)以内。
    caps = {}
    for party in ALL_PARTIES:
        party_candidates = cand[cand["party"] == party]
        smd_count = len(party_candidates)  # 小選挙区候補者数
        # 中道改革連合からの加算
        if party == "立憲民主党":
            smd_count += chudo_to_ritsumin_cap
        elif party == "公明党":
            smd_count += chudo_to_komeito_cap
        if smd_count > 0:
            # 比例: SMD候補の重複 + 比例単独を想定
            # 最低でも世論調査ベースラインの比例分は確保
            baseline_pr = POLLING_BASELINE.get(party, 0) - round(
                POLLING_BASELINE.get(party, 0) * HISTORICAL_SMD_RATIO.get(party, 0.5)
            )
            pr_cap = max(smd_count * 3, baseline_pr, PR_SEATS // 4)
            pr_cap = min(pr_cap, PR_SEATS)
        else:
            # 小選挙区候補なし → 比例専門政党として PR_SEATS を上限に
            pr_cap = PR_SEATS
        caps[party] = {"smd": smd_count, "pr": pr_cap, "total": smd_count + pr_cap}

    return caps


def apply_candidate_caps(results, caps):
    """候補者数上限を適用し、超過分を他の政党に再配分"""
    if not caps:
        return results

    results = {p: dict(v) for p, v in results.items()}  # deep copy

    # 超過分を計算
    overflow = 0
    capped_parties = set()
    for party, r in results.items():
        if party not in caps:
            continue
        cap = caps[party]

        # 小選挙区の上限適用
        if r["smd"] > cap["smd"]:
            overflow += r["smd"] - cap["smd"]
            r["smd"] = cap["smd"]
            capped_parties.add(party)

        # 比例代表の上限適用
        if r["pr"] > cap["pr"]:
            overflow += r["pr"] - cap["pr"]
            r["pr"] = cap["pr"]
            capped_parties.add(party)

        r["total"] = r["smd"] + r["pr"]

    if overflow == 0:
        return results

    # 超過分を、上限に達していない政党に配分
    # 世論調査ベースラインの比率で配分（現在議席比例だと大政党に偏りすぎる）
    eligible = {
        p: POLLING_BASELINE.get(p, 1) for p in results
        if p not in capped_parties and results[p]["total"] > 0
    }
    total_eligible = sum(eligible.values())

    if total_eligible == 0:
        # 全政党がキャップ済みの場合、均等配分
        eligible = {p: 1 for p in results if p not in capped_parties}
        total_eligible = len(eligible)

    # 最大残余法で超過分を配分
    raw_alloc = {p: overflow * (v / total_eligible) for p, v in eligible.items()}
    alloc = {p: int(v) for p, v in raw_alloc.items()}
    remainders = {p: raw_alloc[p] - alloc[p] for p in alloc}
    leftover = overflow - sum(alloc.values())

    for p in sorted(remainders, key=lambda x: remainders[x], reverse=True):
        if leftover <= 0:
            break
        alloc[p] += 1
        leftover -= 1

    # 配分を適用（SMDとPRに歴史的比率で分割）
    for party, extra in alloc.items():
        if extra <= 0:
            continue
        smd_ratio = HISTORICAL_SMD_RATIO.get(party, 0.5)
        cap = caps.get(party, {"smd": SMD_SEATS, "pr": PR_SEATS})
        extra_smd = min(round(extra * smd_ratio), cap["smd"] - results[party]["smd"])
        extra_smd = max(0, extra_smd)
        extra_pr = extra - extra_smd
        # 比例の上限チェック
        if party in caps and results[party]["pr"] + extra_pr > caps[party]["pr"]:
            extra_pr = max(0, caps[party]["pr"] - results[party]["pr"])
            extra_smd = min(extra - extra_pr, cap["smd"] - results[party]["smd"])
            extra_smd = max(0, extra_smd)
        results[party]["smd"] += extra_smd
        results[party]["pr"] += extra_pr
        results[party]["total"] = results[party]["smd"] + results[party]["pr"]

    # 最終調整（端数で合計がずれた場合）
    results = adjust_model_total(results)
    return results


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
    for p in shares:
        if p not in seats:
            seats[p] = 0

    seats = adjust_to_total(seats, total_seats, raw_seats)
    return seats


def adjust_to_total(seats, target, raw_values=None):
    """最大残余法で合計がtargetになるよう調整"""
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


# === 共通議席配分ヘルパー ===

def allocate_youtube_seats(shares):
    """YouTubeシェアからSMD+PR議席を配分（Model 1/2共通）"""
    komeito_smd = round(KOMEITO_SEATS * KOMEITO_SMD_RATIO)
    komeito_pr = round(KOMEITO_SEATS * KOMEITO_PR_RATIO)
    others_smd = round(OTHERS_SEATS * OTHERS_SMD_RATIO)
    others_pr = round(OTHERS_SEATS * OTHERS_PR_RATIO)

    pr_available = PR_SEATS - komeito_pr - others_pr
    pr_scores = {p: shares[p] * 1000 for p in YOUTUBE_PARTIES}
    pr_seats = dhondt_allocation(pr_scores, pr_available)

    smd_available = SMD_SEATS - komeito_smd - others_smd
    smd_seats = cube_law_allocation(shares, smd_available)

    results = {}
    for party in YOUTUBE_PARTIES:
        results[party] = {
            "smd": smd_seats.get(party, 0),
            "pr": pr_seats.get(party, 0),
            "total": smd_seats.get(party, 0) + pr_seats.get(party, 0),
        }

    results["公明党"] = {"smd": komeito_smd, "pr": komeito_pr, "total": KOMEITO_SEATS}
    results["その他"] = {"smd": others_smd, "pr": others_pr, "total": OTHERS_SEATS}

    results = adjust_model_total(results)
    return results


def allocate_by_historical_ratio(shares_dict):
    """歴史的SMD比率で分割する共通ヘルパー（Model 3/5共通）"""
    results = {}
    for party in ALL_PARTIES:
        total_seats = round(shares_dict.get(party, 0) * TOTAL_SEATS)
        smd_ratio = HISTORICAL_SMD_RATIO.get(party, 0.5)
        smd = round(total_seats * smd_ratio)
        pr = total_seats - smd
        results[party] = {"smd": smd, "pr": pr, "total": total_seats}

    results = adjust_model_total(results)
    return results


# === エンゲージメントスコア計算 ===

def compute_time_weighted_stats(data):
    """動画の時間減衰重み付き統計を政党別に計算"""
    videos = data.get("videos", pd.DataFrame())
    if videos.empty:
        return {}

    videos = videos.copy()
    videos["published_at"] = pd.to_datetime(videos["published_at"], errors="coerce")
    videos["party"] = videos["title"].apply(extract_party_from_title)
    videos = videos.dropna(subset=["published_at"])

    days_before = (ELECTION_DATE - videos["published_at"]).dt.total_seconds() / 86400
    videos["time_weight"] = np.exp(-TIME_DECAY_LAMBDA * days_before.clip(lower=0))

    party_weighted = {}
    for party in YOUTUBE_PARTIES:
        pv = videos[videos["party"] == party]
        if pv.empty:
            continue
        party_weighted[party] = {
            "weighted_views": (pv["view_count"] * pv["time_weight"]).sum(),
            "weighted_likes": (pv["like_count"] * pv["time_weight"]).sum(),
        }

    return party_weighted


def compute_engagement_scores(data):
    """各政党のエンゲージメントスコアを計算（時間減衰・成長率付き）"""
    channels = data["channels"].dropna(subset=["party_name"])
    party_stats = data["party_stats"]
    videos = data["videos"]

    time_weighted = compute_time_weighted_stats(data)

    # 成長率計算: 後半期間 vs 前半期間
    growth_rates = {}
    if not videos.empty and "published_at" in videos.columns:
        vc = videos.copy()
        vc["published_at"] = pd.to_datetime(vc["published_at"], errors="coerce")
        vc["party"] = vc["title"].apply(extract_party_from_title)
        vc = vc.dropna(subset=["published_at"])
        midpoint = vc["published_at"].min() + (vc["published_at"].max() - vc["published_at"].min()) / 2
        for party in YOUTUBE_PARTIES:
            pv = vc[vc["party"] == party]
            early = pv[pv["published_at"] <= midpoint]["view_count"].sum()
            late = pv[pv["published_at"] > midpoint]["view_count"].sum()
            growth_rates[party] = late / early if early > 0 else 1.0

    scores = {}
    for party in YOUTUBE_PARTIES:
        ch = channels[channels["party_name"] == party]
        ps = party_stats[party_stats["party_name"] == party]

        if ch.empty or ps.empty:
            scores[party] = 0.0
            continue

        ch = ch.iloc[0]
        ps = ps.iloc[0]

        tw = time_weighted.get(party, {})
        scores[party] = {
            "subscribers": ch["subscriber_count"],
            "channel_views": ch["view_count"],
            "campaign_views": tw.get("weighted_views", ps["total_views"]),
            "campaign_likes": tw.get("weighted_likes", ps["total_likes"]),
            "avg_views": ps["avg_views"],
            "growth_rate": growth_rates.get(party, 1.0),
        }

    # 正規化してスコア算出
    metrics = list(ENGAGEMENT_WEIGHTS.keys())
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
    results = allocate_youtube_seats(shares)
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
    results = allocate_youtube_seats(shares)
    return results, sentiment_scores


# === Model 3: 世論調査 + YouTubeモメンタムモデル ===

def _get_weighted_poll_shares(data):
    """世論調査の時系列加重平均を算出（最新調査を重視）"""
    polling = data.get("news_polling", pd.DataFrame())
    if polling.empty:
        return {p: v / TOTAL_SEATS for p, v in POLLING_BASELINE.items()}

    polling = polling.copy()
    polling["survey_date"] = pd.to_datetime(polling["survey_date"])
    latest_date = polling["survey_date"].max()

    days_ago = (latest_date - polling["survey_date"]).dt.days
    polling["weight"] = np.exp(-np.log(2) * days_ago / POLL_DECAY_HALF_LIFE_DAYS)

    if "sample_size" in polling.columns:
        polling["weight"] *= np.sqrt(polling["sample_size"].fillna(1000) / 1000)

    weighted_rates = {}
    for party in polling["party_name"].unique():
        if party == "支持なし":
            continue
        pm = polling[polling["party_name"] == party]
        if pm["weight"].sum() > 0:
            weighted_rates[party] = (pm["support_rate"] * pm["weight"]).sum() / pm["weight"].sum()

    total = sum(weighted_rates.values())
    if total > 0:
        return {p: v / total for p, v in weighted_rates.items()}

    return {p: v / TOTAL_SEATS for p, v in POLLING_BASELINE.items()}


def model3_polling_momentum(data, youtube_shares):
    """世論調査ベースラインにYouTubeの勢いで補正（時系列加重対応）"""
    polling_shares = _get_weighted_poll_shares(data)

    blended_shares = {}
    for party in ALL_PARTIES:
        ps = polling_shares.get(party, POLLING_BASELINE.get(party, 0) / TOTAL_SEATS)
        if party in YOUTUBE_PARTIES and party in youtube_shares:
            momentum = youtube_shares[party] - ps
            momentum = max(-MOMENTUM_CLAMP, min(MOMENTUM_CLAMP, momentum))
            blended = POLLING_WEIGHT * ps + YOUTUBE_WEIGHT * (ps + momentum)
        else:
            blended = ps
        blended_shares[party] = blended

    total = sum(blended_shares.values())
    blended_shares = {p: v / total for p, v in blended_shares.items()}

    results = allocate_by_historical_ratio(blended_shares)
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
    for party in results:
        diff = results[party]["total"] - (results[party]["smd"] + results[party]["pr"])
        if diff != 0:
            results[party]["pr"] += diff

    return results


# === Model 5: ニュース記事モデル（信頼度・時間減衰・メディア言及対応）===

def compute_news_scores(data):
    """ニュース記事の報道量・トーンから政党スコアを算出（信頼度・時間減衰付き）"""
    articles = data.get("news_articles", pd.DataFrame())
    polling = data.get("news_polling", pd.DataFrame())
    media_mentions = data.get("media_mentions", pd.DataFrame())

    coverage_scores = {}
    tone_scores = {}

    if not articles.empty:
        articles = articles.copy()
        articles["published_at"] = pd.to_datetime(articles["published_at"], errors="coerce")
        latest = articles["published_at"].max()

        days_ago = (latest - articles["published_at"]).dt.days.fillna(0)
        articles["recency_weight"] = np.exp(-np.log(2) * days_ago / RECENCY_HALF_LIFE_DAYS)

        if "credibility_score" in articles.columns:
            articles["cred_weight"] = articles["credibility_score"].fillna(3.0) / 5.0
        else:
            articles["cred_weight"] = 1.0

        articles["combined_weight"] = (
            articles["page_views"].fillna(0)
            * articles["recency_weight"]
            * articles["cred_weight"]
        )

        party_rows = []
        for idx, row in articles.iterrows():
            parties = str(row.get("mentioned_parties", "")).split("|")
            for party in parties:
                if party and party != "nan":
                    party_rows.append({
                        "party": party,
                        "weighted_pv": row["combined_weight"],
                        "tone_weighted": row.get("tone", 0) * row["recency_weight"] * row["cred_weight"],
                        "count": 1,
                    })

        if party_rows:
            df_party = pd.DataFrame(party_rows)
            agg = df_party.groupby("party").agg(
                total_weighted_pv=("weighted_pv", "sum"),
                total_weighted_tone=("tone_weighted", "sum"),
                article_count=("count", "sum"),
            )
            coverage_scores = agg["total_weighted_pv"].to_dict()
            tone_scores = (agg["total_weighted_tone"] / agg["article_count"]).to_dict()

    # 世論調査スコア（時系列加重平均）
    poll_scores = _get_weighted_poll_shares(data)

    # メディア言及スコア
    media_scores = {}
    if not media_mentions.empty:
        total_media = media_mentions["media_mention_views"].sum()
        if total_media > 0:
            for _, row in media_mentions.iterrows():
                media_scores[row["party_name"]] = row["media_mention_views"] / total_media

    return coverage_scores, tone_scores, poll_scores, media_scores


def model5_news_prediction(data):
    """ニュース記事データで議席を予測（信頼度・時間減衰・メディア言及対応）"""
    coverage_scores, tone_scores, poll_scores, media_scores = compute_news_scores(data)

    all_parties_in_news = set(
        list(coverage_scores.keys()) + list(poll_scores.keys()) + list(media_scores.keys())
    )
    parties = [p for p in ALL_PARTIES if p in all_parties_in_news or p in POLLING_BASELINE]

    max_coverage = max(coverage_scores.values()) if coverage_scores else 1
    norm_coverage = {p: coverage_scores.get(p, 0) / max_coverage for p in parties}

    norm_poll = {p: poll_scores.get(p, 0) for p in parties}

    max_media = max(media_scores.values()) if media_scores else 1
    norm_media = {p: media_scores.get(p, 0) / max_media for p in parties}

    combined_scores = {}
    for party in parties:
        base = (NEWS_POLLING_WEIGHT * norm_poll.get(party, 0)
                + NEWS_COVERAGE_WEIGHT * norm_coverage.get(party, 0)
                + NEWS_MEDIA_WEIGHT * norm_media.get(party, 0))
        tone_adj = 1.0 + (tone_scores.get(party, 0) * NEWS_TONE_WEIGHT * 2)
        combined_scores[party] = base * tone_adj

    for party in ALL_PARTIES:
        if party not in combined_scores:
            combined_scores[party] = POLLING_BASELINE.get(party, 0) / TOTAL_SEATS * 0.5

    total = sum(combined_scores.values())
    if total > 0:
        combined_scores = {p: v / total for p, v in combined_scores.items()}

    results = allocate_by_historical_ratio(combined_scores)

    news_shares = combined_scores
    return results, news_shares, coverage_scores, tone_scores, poll_scores


# === Model 6: 統合アンサンブル（YouTube + ニュース）===

# 世論調査アンカリングの強さ（0=アンカリングなし、1=完全に世論調査通り）
# 538も最終結果を世論調査ベースラインから大きく離さないアンカーを使用
POLLING_ANCHOR_WEIGHT = 0.30


def model6_combined_ensemble(m4_results, m5_results):
    """YouTubeアンサンブル(M4) + ニュース記事モデル(M5) の統合予測
    + 世論調査ベースラインへのアンカリング"""
    w4 = COMBINED_ENSEMBLE_WEIGHTS["model4"]
    w5 = COMBINED_ENSEMBLE_WEIGHTS["model5"]

    # Step 1: M4+M5 の加重平均
    raw_results = {}
    for party in ALL_PARTIES:
        m4 = m4_results.get(party, {"total": 0, "smd": 0, "pr": 0})
        m5 = m5_results.get(party, {"total": 0, "smd": 0, "pr": 0})

        total = w4 * m4["total"] + w5 * m5["total"]
        smd = w4 * m4["smd"] + w5 * m5["smd"]
        pr = w4 * m4["pr"] + w5 * m5["pr"]

        raw_results[party] = {
            "total": total,
            "smd": smd,
            "pr": pr,
        }

    # Step 2: 世論調査ベースラインへのアンカリング
    # データ駆動の予測と世論調査ベースラインの加重平均をとる
    wa = POLLING_ANCHOR_WEIGHT
    results = {}
    for party in ALL_PARTIES:
        raw = raw_results[party]
        bl_total = POLLING_BASELINE.get(party, 0)
        bl_smd = round(bl_total * HISTORICAL_SMD_RATIO.get(party, 0.5))
        bl_pr = bl_total - bl_smd

        results[party] = {
            "total": round((1 - wa) * raw["total"] + wa * bl_total),
            "smd": round((1 - wa) * raw["smd"] + wa * bl_smd),
            "pr": round((1 - wa) * raw["pr"] + wa * bl_pr),
        }

    results = adjust_model_total(results)
    for party in results:
        diff = results[party]["total"] - (results[party]["smd"] + results[party]["pr"])
        if diff != 0:
            results[party]["pr"] += diff

    return results


def adjust_model_total(results):
    """最大残余法で全モデル結果の合計を465に調整し、SMD/PRの内訳も289/176に合わせる"""
    # Step 1: Total を 465 に調整
    current = sum(r["total"] for r in results.values())
    diff = TOTAL_SEATS - current
    if diff != 0:
        sorted_parties = sorted(results.keys(), key=lambda p: results[p]["total"], reverse=True)
        for i in range(abs(diff)):
            p = sorted_parties[i % len(sorted_parties)]
            adj = 1 if diff > 0 else -1
            results[p]["total"] += adj
            if results[p]["smd"] > results[p]["pr"]:
                results[p]["smd"] += adj
            else:
                results[p]["pr"] += adj

    # Step 2: SMD 合計を 289 に、PR 合計を 176 に調整
    # total は維持しつつ、各政党の SMD/PR 配分を微調整する
    smd_total = sum(r["smd"] for r in results.values())
    smd_diff = SMD_SEATS - smd_total  # 289 - 現在のSMD合計

    if smd_diff != 0:
        # SMDを増やす(smd_diff > 0)か減らす(smd_diff < 0)必要がある
        # SMDを増やす場合: PRが多い（SMD比率が低い）政党からPR→SMDにシフト
        # SMDを減らす場合: SMDが多い（SMD比率が高い）政党からSMD→PRにシフト
        if smd_diff > 0:
            # PRからSMDへシフト: PR/total比率が高い政党を優先
            candidates = sorted(
                [p for p in results if results[p]["pr"] > 0],
                key=lambda p: results[p]["pr"] / max(results[p]["total"], 1),
                reverse=True,
            )
        else:
            # SMDからPRへシフト: SMD/total比率が高い政党を優先
            candidates = sorted(
                [p for p in results if results[p]["smd"] > 0],
                key=lambda p: results[p]["smd"] / max(results[p]["total"], 1),
                reverse=True,
            )

        for i in range(abs(smd_diff)):
            if not candidates:
                break
            p = candidates[i % len(candidates)]
            if smd_diff > 0 and results[p]["pr"] > 0:
                results[p]["smd"] += 1
                results[p]["pr"] -= 1
            elif smd_diff < 0 and results[p]["smd"] > 0:
                results[p]["smd"] -= 1
                results[p]["pr"] += 1

    return results


# === Model 7: 選挙区ボトムアップ予測 ===

def _compute_candidate_composite_scores(cand, polling_shares):
    """各候補者の複合予測スコアを算出（v2: 先行研究ベース6信号）

    参考文献:
    - 538 House Forecast (ABC News, 2024): partisan_lean最重要、incumbency ~3.6pt
    - Cook PVI (2025): 過去2回の選挙結果加重平均
    - Lewis-Beck & Tien (2012): 政治経済モデル（GDP + 内閣支持率）
    - Upham (2016): 日本のRD分析で現職優位は欧米より弱い
    - Scheiner (2012): 2005年以降は政党帰属が最大予測因子
    """
    w = DISTRICT_SIGNAL_WEIGHTS

    # 1. partisan_lean: 前回選挙区結果ベースの党派性（最重要変数）
    partisan_lean_signal = cand["partisan_lean"].fillna(0.10)

    # 2. polling_swing: 世論調査の支持率変動
    polling_swing_signal = cand["polling_swing"].fillna(0.0)
    # スイングを0-1スケールに正規化 (-0.2 ~ +0.2 → 0.0 ~ 0.4)
    polling_swing_normalized = (polling_swing_signal + 0.2).clip(0.0, 0.4)

    # 3. candidate_strength: 候補者の個人的強さ（区分ベース）
    candidate_strength_signal = cand["candidate_strength"].fillna(0.03)

    # 4. incumbency: 現職ボーナス（日本では控えめ）
    incumbency_signal = cand["incumbency"].fillna(0.0)

    # 5. youtube_score: YouTubeエンゲージメント（0-1）
    yt_signal = cand["youtube_score"].fillna(0)

    # 6. news_score: ニュース言及（0-1に正規化）
    max_news = cand["news_mentions"].max()
    news_signal = cand["news_mentions"].fillna(0) / max(max_news, 1)

    composite = (
        w["partisan_lean"] * partisan_lean_signal
        + w["polling_swing"] * polling_swing_normalized
        + w["candidate_strength"] * candidate_strength_signal
        + w["incumbency"] * incumbency_signal
        + w["youtube_score"] * yt_signal
        + w["news_score"] * news_signal
    )
    return composite


def model7_district_prediction(data, polling_shares=None):
    """選挙区ごとの予測優勢をもとに議席配分を予測（ボトムアップ方式）"""
    candidates = data.get("candidates", pd.DataFrame())
    if polling_shares is None:
        polling_shares = {p: v / TOTAL_SEATS for p, v in POLLING_BASELINE.items()}

    if candidates.empty:
        # フォールバック: 世論調査ベースで配分
        results = allocate_by_historical_ratio(polling_shares)
        return results, pd.DataFrame()

    cand = candidates.copy()

    # 各候補者の複合スコアを計算
    cand["composite_score"] = _compute_candidate_composite_scores(cand, polling_shares)

    # 選挙区キー
    cand["district_key"] = (
        cand["prefecture_code"].astype(str) + "_" + cand["district_number"].astype(str)
    )

    # 選挙区内で順位付け
    cand["model7_rank"] = cand.groupby("district_key")["composite_score"].rank(
        ascending=False, method="first"
    ).astype(int)

    # マージン計算
    max_scores = cand.groupby("district_key")["composite_score"].transform("max")
    second_scores = cand.groupby("district_key")["composite_score"].apply(
        lambda x: x.nlargest(2).iloc[-1] if len(x) >= 2 else 0
    )
    second_map = second_scores.to_dict()
    cand["model7_margin"] = cand.apply(
        lambda row: row["composite_score"] - second_map.get(row["district_key"], 0)
        if row["model7_rank"] == 1
        else max_scores[row.name] - row["composite_score"],
        axis=1,
    )

    # SMD議席集計
    # 中道改革連合の当選者を立憲民主党と公明党に振り分ける
    winners = cand[cand["model7_rank"] == 1].copy()
    winner_parties = winners["party"].replace({"無所属": "その他"})

    # 中道改革連合のSMD議席を立憲民主党と公明党に振り分ける
    # 配分比率: 2024年のSMD実績比を使用（支持率比ではなく）
    # 2024年: 立憲104 SMD, 公明4 SMD → 立憲96.3% : 公明3.7%
    # 公明は歴史的にSMD候補が少なく比例中心のため、支持率比での配分は過大になる
    chudo_total = int((winner_parties == "中道改革連合").sum())
    RITSUMIN_SMD_2024 = 104  # 2024年の立憲SMD当選数
    KOMEITO_SMD_2024 = 4     # 2024年の公明SMD当選数
    smd_total_2024 = RITSUMIN_SMD_2024 + KOMEITO_SMD_2024
    ritsumin_ratio = RITSUMIN_SMD_2024 / max(smd_total_2024, 1)
    chudo_to_ritsumin = round(chudo_total * ritsumin_ratio)
    chudo_to_komeito = chudo_total - chudo_to_ritsumin

    smd_seats = {}
    for party in ALL_PARTIES:
        if party == "立憲民主党":
            own = int((winner_parties == party).sum())
            smd_seats[party] = own + chudo_to_ritsumin
        elif party == "公明党":
            own = int((winner_parties == party).sum())
            smd_seats[party] = own + chudo_to_komeito
        elif party == "中道改革連合":
            continue  # 中道改革連合は立憲+公明に分配済み
        else:
            smd_seats[party] = int((winner_parties == party).sum())

    # PR議席配分（ドント方式、世論調査ベース）
    pr_scores = {p: max(polling_shares.get(p, 0), 0.001) for p in ALL_PARTIES}
    pr_scores_scaled = {p: v * 1000 for p, v in pr_scores.items()}
    pr_seats = dhondt_allocation(pr_scores_scaled, PR_SEATS)

    # 結果組み立て
    results = {}
    for party in ALL_PARTIES:
        s = smd_seats.get(party, 0)
        p = pr_seats.get(party, 0)
        results[party] = {"smd": s, "pr": p, "total": s + p}

    results = adjust_model_total(results)

    # district_results DataFrame を構築
    output_cols = [
        "prefecture_code", "prefecture_name", "district_number", "district_name",
        "candidate_name", "party", "age", "is_incumbent",
        "composite_score", "model7_rank", "model7_margin",
        "youtube_score", "news_mentions",
    ]
    # 存在するカラムのみ選択
    available_cols = [c for c in output_cols if c in cand.columns]
    district_results = cand[available_cols].copy()
    district_results = district_results.rename(columns={
        "composite_score": "predicted_vote_share",
        "model7_rank": "predicted_rank",
        "model7_margin": "margin",
    })

    return results, district_results


def save_district_predictions(district_results):
    """Model 7の選挙区予測結果を別ファイルに保存（元のCSVを上書きしない）"""
    if district_results.empty:
        return
    out_path = PROCESSED_DIR / "district_model7_results.csv"
    district_results.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"  Model 7 選挙区予測結果保存: {out_path}")


def derive_prefecture_summary(district_results):
    """Model 7の選挙区予測結果からprefecture_summary.csvを導出"""
    if district_results.empty:
        return

    winners = district_results[district_results["predicted_rank"] == 1].copy()

    party_list = [
        "自由民主党", "立憲民主党", "日本維新の会", "国民民主党",
        "公明党", "日本共産党", "れいわ新選組", "参政党",
        "チームみらい", "無所属",
    ]

    rows = []
    for pref_code in sorted(winners["prefecture_code"].unique()):
        pref_winners = winners[winners["prefecture_code"] == pref_code]
        pref_name = pref_winners["prefecture_name"].iloc[0]

        block_name = ""
        for block, pref_codes in PR_BLOCK_PREFECTURES.items():
            if pref_code in pref_codes:
                block_name = block
                break

        n_districts = len(pref_winners)

        party_seats = {}
        for party in party_list:
            party_seats[party] = int((pref_winners["party"] == party).sum())

        dominant_party = max(party_seats, key=party_seats.get)
        battleground = int((pref_winners["margin"] < 0.05).sum())

        row = {
            "prefecture_code": pref_code,
            "prefecture_name": pref_name,
            "region_block": block_name,
            "total_smd_seats": n_districts,
            "dominant_party": dominant_party,
        }
        row.update(party_seats)
        row["battleground_count"] = battleground
        rows.append(row)

    df = pd.DataFrame(rows)
    out_path = PROCESSED_DIR / "prefecture_summary.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"  都道府県集約データ更新: {out_path}")


# === CSV出力 ===

def save_predictions(m1, m2, m3, m4, m5, m6, m7,
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
            "model7_total": m7.get(party, {}).get("total", 0),
            "model7_smd": m7.get(party, {}).get("smd", 0),
            "model7_pr": m7.get(party, {}).get("pr", 0),
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
    print(f"  較正済みキューブ指数: {CUBE_EXPONENT:.1f}")
    print("=" * 60)

    data = load_prediction_data()

    # 候補者数上限を算出
    caps = compute_candidate_caps(data)
    if caps:
        print("  候補者数上限:")
        for party in ALL_PARTIES:
            if party in caps:
                c = caps[party]
                print(f"    {party}: SMD≤{c['smd']}, PR≤{c['pr']}, 合計≤{c['total']}")

    # Model 1（候補者上限はM4アンサンブル後に適用）
    print("\n[Model 1] YouTubeエンゲージメントシェアモデル")
    m1_results, eng_scores, youtube_shares = model1_engagement_share(data)
    print_results(m1_results)

    # Model 2（候補者上限はM4アンサンブル後に適用）
    print("\n[Model 2] 感情分析加重エンゲージメントモデル")
    m2_results, sentiment_scores = model2_sentiment_weighted(data, eng_scores)
    print_results(m2_results)

    # Model 3（候補者上限はM4アンサンブル後に適用）
    print("\n[Model 3] 世論調査 + YouTubeモメンタムモデル（時系列加重）")
    m3_results, blended_shares = model3_polling_momentum(data, youtube_shares)
    print_results(m3_results)

    # Model 4（M1-M3のアンサンブル → 候補者上限適用）
    print("\n[Model 4] YouTubeアンサンブル予測")
    m4_results = model4_ensemble(m1_results, m2_results, m3_results)
    m4_results = apply_candidate_caps(m4_results, caps)
    print_results(m4_results)

    # Model 5（ニュースモデル → 候補者上限適用）
    print("\n[Model 5] ニュース記事モデル（信頼度・時間減衰・メディア言及）")
    m5_results, news_shares, coverage_scores, tone_scores, poll_scores = model5_news_prediction(data)
    m5_results = apply_candidate_caps(m5_results, caps)
    print_results(m5_results)

    # Model 6（M4+M5の統合）
    print("\n[Model 6] 統合アンサンブル（YouTube + ニュース）")
    m6_results = model6_combined_ensemble(m4_results, m5_results)
    print_results(m6_results)

    # Model 7（選挙区ボトムアップ → 候補者上限適用）
    print("\n[Model 7] 選挙区ボトムアップ予測モデル")
    polling_shares_for_m7 = _get_weighted_poll_shares(data)
    m7_results, district_results = model7_district_prediction(data, polling_shares_for_m7)
    m7_results = apply_candidate_caps(m7_results, caps)
    print_results(m7_results)

    # Model 7の結果から選挙区・都道府県データを再生成
    save_district_predictions(district_results)
    derive_prefecture_summary(district_results)

    # CSV保存（M1-M3は表示用に候補者上限を適用）
    m1_save = apply_candidate_caps(m1_results, caps)
    m2_save = apply_candidate_caps(m2_results, caps)
    m3_save = apply_candidate_caps(m3_results, caps)
    df = save_predictions(
        m1_save, m2_save, m3_save, m4_results,
        m5_results, m6_results, m7_results,
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
