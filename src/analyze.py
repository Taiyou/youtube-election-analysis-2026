"""
データ分析スクリプト
収集したYouTubeデータを加工・分析する
"""
import re

import pandas as pd

try:
    import MeCab
    _MECAB_AVAILABLE = True
except ImportError:
    _MECAB_AVAILABLE = False

from config import (
    DATA_DIR,
    ISSUE_KEYWORDS,
    PARTY_CHANNELS,
    SENTIMENT_POSITIVE_WORDS,
    SENTIMENT_NEGATIVE_WORDS,
    NEGATION_PATTERNS,
)


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
    """争点別の分析（ベクトル化）"""
    df = df.copy()

    # テキスト結合してissue分類をベクトル適用
    combined_text = df["title"].fillna("") + " " + df.get("description", pd.Series("", index=df.index)).fillna("")
    df["issues"] = combined_text.apply(classify_issue)

    # issues列をexplodeで展開（iterrows不要）
    issue_df = df.explode("issues").rename(columns={"issues": "issue"})

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
    # 既存のparty_name列がない、またはNaNの場合のみチャンネルIDからマッピング
    mapped = df_channels["channel_id"].map(id_to_party)
    if "party_name" in df_channels.columns:
        df_channels["party_name"] = df_channels["party_name"].fillna(mapped)
    else:
        df_channels["party_name"] = mapped

    # 政党チャンネルの動画を抽出（PARTY_CHANNELSのIDまたはサンプルデータのch_*形式）
    party_channel_ids = set(PARTY_CHANNELS.values())
    known_channel_ids = party_channel_ids | set(df_channels.dropna(subset=["party_name"])["channel_id"])
    party_videos = df_details[df_details["channel_id"].isin(known_channel_ids)].copy()
    vid_mapped = party_videos["channel_id"].map(id_to_party)
    # チャンネルデータからもマッピングを作成
    ch_id_to_party = dict(zip(df_channels["channel_id"], df_channels["party_name"]))
    vid_mapped = vid_mapped.fillna(party_videos["channel_id"].map(ch_id_to_party))
    party_videos["party_name"] = vid_mapped

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


def detect_spam_comments(df_comments):
    """Bot/スパムコメントを検出してフラグ付け"""
    df = df_comments.copy()
    df["is_spam"] = False

    # 1. 重複コメント検出（同一テキストが3回以上）
    text_counts = df["text"].value_counts()
    duplicate_texts = set(text_counts[text_counts >= 3].index)
    df.loc[df["text"].isin(duplicate_texts), "is_spam"] = True

    # 2. 高頻度投稿者検出（同一著者が10コメント以上）
    if "author" in df.columns:
        author_counts = df["author"].value_counts()
        spam_authors = set(author_counts[author_counts >= 10].index)
        df.loc[df["author"].isin(spam_authors), "is_spam"] = True

    # 3. URL含有 + 低いいね数
    url_pattern = r"https?://"
    has_url = df["text"].str.contains(url_pattern, na=False)
    low_likes = df.get("like_count", pd.Series(0, index=df.index)) < 2
    df.loc[has_url & low_likes, "is_spam"] = True

    # 4. 極端に短いコメント（5文字未満、絵文字のみを除く）
    short_text = df["text"].str.len() < 5
    # 絵文字のみのコメントは除外
    emoji_only = df["text"].str.match(r"^[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\s]+$", na=False)
    df.loc[short_text & ~emoji_only, "is_spam"] = True

    # 5. トライグラム類似度によるコピペ検出
    def char_trigrams(text):
        text = str(text)
        return set(text[i:i+3] for i in range(len(text) - 2))

    # 長いコメントのみ対象（計算量削減）
    long_comments = df[df["text"].str.len() >= 30]
    if len(long_comments) > 1:
        trigram_cache = {idx: char_trigrams(row["text"]) for idx, row in long_comments.iterrows()}
        checked = set()
        for idx_a, tg_a in trigram_cache.items():
            if not tg_a:
                continue
            for idx_b, tg_b in trigram_cache.items():
                if idx_a >= idx_b or (idx_a, idx_b) in checked:
                    continue
                checked.add((idx_a, idx_b))
                intersection = len(tg_a & tg_b)
                union = len(tg_a | tg_b)
                if union > 0 and intersection / union > 0.8:
                    df.loc[idx_b, "is_spam"] = True

    spam_count = df["is_spam"].sum()
    total = len(df)
    print(f"  スパム検出: {spam_count}/{total}件 ({spam_count/total*100:.1f}%)")

    return df


# === MeCab形態素解析ベースの感情分析 ===

def _init_mecab():
    """MeCab Taggerを初期化"""
    if not _MECAB_AVAILABLE:
        return None
    try:
        return MeCab.Tagger()
    except Exception:
        return None

_mecab_tagger = _init_mecab()


def _mecab_tokenize(text):
    """MeCabでテキストをトークン化し、基本形・品詞情報を返す"""
    if _mecab_tagger is None:
        return []

    tokens = []
    node = _mecab_tagger.parseToNode(str(text))
    while node:
        surface = node.surface
        if surface:
            features = node.feature.split(",")
            pos = features[0] if features else ""
            # unidic-liteでは基本形は7番目のフィールド
            base = features[7] if len(features) > 7 and features[7] != "*" else surface
            tokens.append({"surface": surface, "pos": pos, "base": base})
        node = node.next
    return tokens


def score_sentiment_mecab(text):
    """MeCab形態素解析ベースの感情スコアリング"""
    tokens = _mecab_tokenize(text)
    if not tokens:
        # MeCabが利用不可の場合はフォールバック
        return score_sentiment_keyword(text)

    pos_score = 0.0
    neg_score = 0.0

    for i, token in enumerate(tokens):
        base = token["base"]
        surface = token["surface"]

        # 否定助動詞チェック（次のトークンが「ない」等か）
        is_negated = False
        if i + 1 < len(tokens):
            next_base = tokens[i + 1]["base"]
            next_pos = tokens[i + 1]["pos"]
            if next_base in ("ない", "ぬ", "ず", "ません") or (next_pos == "助動詞" and next_base == "ない"):
                is_negated = True

        # ポジティブ辞書との照合（基本形で）
        for word, intensity in SENTIMENT_POSITIVE_WORDS.items():
            if base == word or surface == word:
                if is_negated:
                    neg_score += intensity  # 否定されたポジティブ→ネガティブ
                else:
                    pos_score += intensity
                break

        # ネガティブ辞書との照合（基本形で）
        for word, intensity in SENTIMENT_NEGATIVE_WORDS.items():
            if base == word or surface == word:
                if is_negated:
                    pos_score += intensity * 0.5  # 否定されたネガティブ→弱いポジティブ
                else:
                    neg_score += intensity
                break

    total = pos_score + neg_score
    if total == 0:
        return 0.0, "neutral"

    score = (pos_score - neg_score) / total

    if score > 0.1:
        label = "positive"
    elif score < -0.1:
        label = "negative"
    else:
        label = "neutral"

    return score, label


# === キーワードベースのフォールバック感情分析 ===

def _check_negation(text, keyword_pos):
    """キーワードの前に否定表現があるか判定"""
    # キーワード位置の前30文字を検査
    window_start = max(0, keyword_pos - 30)
    preceding = text[window_start:keyword_pos]
    for neg in NEGATION_PATTERNS:
        if neg in preceding:
            return True
    return False


def score_sentiment_keyword(text):
    """キーワードベースの強度付き感情スコア（MeCab未使用時のフォールバック）"""
    text = str(text)
    pos_score = 0.0
    neg_score = 0.0

    # ポジティブスコア
    for word, intensity in SENTIMENT_POSITIVE_WORDS.items():
        idx = text.find(word)
        if idx >= 0:
            if _check_negation(text, idx):
                neg_score += intensity  # 否定されたポジティブ → ネガティブ
            else:
                pos_score += intensity

    # ネガティブスコア
    for word, intensity in SENTIMENT_NEGATIVE_WORDS.items():
        idx = text.find(word)
        if idx >= 0:
            if _check_negation(text, idx):
                pos_score += intensity * 0.5  # 否定されたネガティブ → 弱いポジティブ
            else:
                neg_score += intensity

    total = pos_score + neg_score
    if total == 0:
        return 0.0, "neutral"

    # 正規化された連続値スコア（-1.0〜+1.0）
    score = (pos_score - neg_score) / total

    if score > 0.1:
        label = "positive"
    elif score < -0.1:
        label = "negative"
    else:
        label = "neutral"

    return score, label


def score_sentiment(text):
    """感情スコアのディスパッチャー: MeCab利用可能ならMeCab版、それ以外はキーワード版"""
    if _mecab_tagger is not None:
        return score_sentiment_mecab(text)
    return score_sentiment_keyword(text)


def analyze_comments_sentiment(df_comments):
    """コメントの感情分析（強度付き・否定表現対応・MeCab対応）"""
    df_comments = df_comments.copy()

    results = df_comments["text"].apply(score_sentiment)
    df_comments["sentiment_score"] = results.apply(lambda x: x[0])
    df_comments["sentiment"] = results.apply(lambda x: x[1])

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
    print("\n[1/5] 動画トレンド分析...")
    df_details, daily_counts, daily_views = analyze_video_trends(df_details)

    print("[2/5] 争点別分析...")
    issue_df, issue_stats = analyze_by_issue(df_details)

    print("[3/5] チャンネル分析...")
    df_channels, party_video_stats = analyze_channels(df_details, df_channels)

    print("[4/5] スパムコメント検出...")
    df_comments = detect_spam_comments(df_comments)

    print("[5/5] コメント感情分析（スパム除外）...")
    # スパムを除外してから感情分析
    df_clean = df_comments[~df_comments["is_spam"]].copy()
    df_clean, sentiment_counts = analyze_comments_sentiment(df_clean)
    # スパムコメントにもsentiment列を追加（neutral扱い）
    df_comments = df_comments.merge(
        df_clean[["text", "sentiment", "sentiment_score"]].drop_duplicates(subset=["text"]),
        on="text", how="left", suffixes=("", "_clean"),
    )
    if "sentiment_clean" in df_comments.columns:
        df_comments["sentiment"] = df_comments["sentiment_clean"].fillna("neutral")
        df_comments["sentiment_score"] = df_comments.get("sentiment_score_clean", pd.Series(0.0)).fillna(0.0)
        df_comments.drop(columns=[c for c in df_comments.columns if c.endswith("_clean")], inplace=True)
    else:
        df_comments["sentiment"] = df_comments["sentiment"].fillna("neutral")
        df_comments["sentiment_score"] = df_comments.get("sentiment_score", pd.Series(0.0)).fillna(0.0)

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
