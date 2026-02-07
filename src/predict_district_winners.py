"""
選挙区別当選予測スクリプト
実際の候補者データから、政党の地域強度・世論調査・現職有利を使い
各選挙区の当選者を予測し、確信度を算出する
"""
import re
import sys

import numpy as np
import pandas as pd

from config import (
    DATA_DIR,
    PREFECTURE_DISTRICTS,
    PREFECTURE_REGION_TYPE,
    REGIONAL_PARTY_STRENGTH,
)

PROCESSED_DIR = DATA_DIR / "processed"

# === 世論調査ベースライン（predict_seats.pyと同一） ===
TOTAL_SEATS = 465

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

# === 政党名マッピング ===
PARTY_ALIAS = {
    "中道改革連合": "立憲民主党",
}

KNOWN_LOOKUP_PARTIES = set(POLLING_BASELINE.keys()) | {"無所属"}

# === 区分別得票率ボーナス ===
# 現職・前職は選挙区での知名度・地盤があり大きな有利
KUBUN_VOTE_BONUS = {
    "現職": 0.25,
    "前職": 0.20,
    "元職": 0.10,
    "新人": 0.00,
    "不明": 0.00,
}

# === 小選挙区得票率ベースライン（2024衆院選実績ベース） ===
# 小選挙区での平均得票率シェア（候補者を擁立している選挙区での平均）
SMD_VOTE_SHARE_BASELINE = {
    "自由民主党":   0.38,
    "立憲民主党":   0.30,
    "日本維新の会": 0.25,
    "国民民主党":   0.22,
    "れいわ新選組": 0.08,
    "日本共産党":   0.06,
    "参政党":       0.04,
    "公明党":       0.15,
    "チームみらい": 0.05,
    "無所属":       0.12,
    "その他":       0.03,
}

SOFTMAX_TEMPERATURE = 0.35
CONFIDENCE_DENOMINATOR = 0.20


def build_prefecture_lookup():
    """短い都道府県名 → 都道府県コードのマッピングを構築"""
    lookup = {}
    for code, (full_name, _) in PREFECTURE_DISTRICTS.items():
        short = full_name
        for suffix in ["都", "府", "県"]:
            if short.endswith(suffix):
                short = short[:-1]
                break
        lookup[short] = code
    return lookup


def parse_district_name(district_name, pref_lookup):
    """'北海道1区' → (prefecture_code=1, district_number=1)"""
    m = re.match(r"^(.+?)(\d+)区$", district_name)
    if not m:
        return None, None
    prefix, number = m.group(1), int(m.group(2))
    code = pref_lookup.get(prefix)
    return code, number


def get_lookup_party(party_name):
    """政党名を世論調査/地域強度の参照用キーに変換"""
    mapped = PARTY_ALIAS.get(party_name, party_name)
    if mapped in KNOWN_LOOKUP_PARTIES:
        return mapped
    return "その他"


def _estimate_vote_share(row, region_profile):
    """候補者ごとの推定得票率を算出

    アプローチ:
    1. 政党の小選挙区得票率ベースラインを出発点とする
    2. 地域の政党強度で加減算補正する（関西→維新+、北海道→立憲+など）
    3. 現職/前職ボーナスを加算する（知名度・地盤の効果）
    """
    lookup_party = row["_lookup_party"]

    # 1. 小選挙区得票率ベースライン
    base = SMD_VOTE_SHARE_BASELINE.get(lookup_party, 0.03)

    # 2. 地域補正: REGIONAL_PARTY_STRENGTHの全国平均からの偏差を加減算
    regional = region_profile.get(lookup_party, 0.02)
    # 全地域の平均を計算（4地域の単純平均）
    all_regions = REGIONAL_PARTY_STRENGTH.values()
    national_avg = sum(r.get(lookup_party, 0.02) for r in all_regions) / len(
        REGIONAL_PARTY_STRENGTH
    )
    # 偏差を補正量として適用（±の範囲で穏やかに）
    regional_delta = (regional - national_avg) * 0.5
    adjusted = base + regional_delta

    # 3. 区分ボーナス
    kubun_bonus = KUBUN_VOTE_BONUS.get(row["区分"], 0.0)
    adjusted += kubun_bonus

    return max(adjusted, 0.01)


def predict_district_winners(csv_path):
    """選挙区ごとの当選予測を行う"""
    df = pd.read_csv(csv_path, dtype={"年齢": str})

    pref_lookup = build_prefecture_lookup()

    # 都道府県コード・選挙区番号を導出
    parsed = df["選挙区名"].apply(lambda x: parse_district_name(x, pref_lookup))
    df["_pref_code"] = parsed.apply(lambda x: x[0])
    df["_district_num"] = parsed.apply(lambda x: x[1])
    df["_lookup_party"] = df["政党名"].apply(get_lookup_party)
    df["_region_type"] = df["_pref_code"].map(PREFECTURE_REGION_TYPE).fillna("rural_ldp")

    # 各候補者の推定得票率を計算
    raw_scores = []
    for _, row in df.iterrows():
        region_profile = REGIONAL_PARTY_STRENGTH.get(row["_region_type"], {})
        score = _estimate_vote_share(row, region_profile)
        raw_scores.append(score)

    df["_raw_score"] = raw_scores

    # 選挙区内で正規化→確率化、当選予測・確信度を算出
    df["当選確率"] = 0.0
    df["当選予測"] = 0
    df["確信度"] = 0.0

    for district, group in df.groupby("選挙区名"):
        idx = group.index
        raw = group["_raw_score"].values

        # softmax（数値安定性のためmax引き）
        shifted = raw - raw.max()
        exp_scores = np.exp(shifted / SOFTMAX_TEMPERATURE)
        probs = exp_scores / exp_scores.sum()

        df.loc[idx, "当選確率"] = probs

        # 当選者
        winner_pos = np.argmax(probs)
        winner_idx = idx[winner_pos]
        df.loc[winner_idx, "当選予測"] = 1

        # 確信度（1位と2位の差）
        sorted_probs = np.sort(probs)[::-1]
        margin = sorted_probs[0] - (sorted_probs[1] if len(sorted_probs) > 1 else 0)
        confidence = min(margin / CONFIDENCE_DENOMINATOR, 1.0)
        df.loc[idx, "確信度"] = round(confidence, 4)

    return df


def save_results(df, output_path):
    """予測結果をCSVに保存"""
    df["当選確率"] = df["当選確率"].round(4)
    df["当選予測"] = df["当選予測"].astype(int)

    output_cols = [
        "選挙区名", "候補者名", "政党名", "年齢", "区分", "当選人数",
        "当選予測", "当選確率", "確信度",
    ]
    df[output_cols].to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"予測結果を保存: {output_path}")


def print_aggregate_stats(df):
    """集計統計を表示"""
    winners = df[df["当選予測"] == 1]
    total_winners = len(winners)

    print("\n" + "=" * 60)
    print("選挙区別当選予測 集計結果")
    print("=" * 60)

    print(f"\n全{total_winners}選挙区の予測結果:")

    print("\n--- 政党別予測当選者数 ---")
    party_seats = winners.groupby("政党名").size().sort_values(ascending=False)
    for party, count in party_seats.items():
        pct = count / total_winners * 100
        print(f"  {party:20s}: {count:4d}議席 ({pct:5.1f}%)")
    print(f"  {'合計':20s}: {party_seats.sum():4d}議席")

    print("\n--- 確信度別集計 ---")
    bins = [
        (0.8, 1.01, "安全圏    (0.8-1.0)"),
        (0.5, 0.80, "優勢      (0.5-0.8)"),
        (0.3, 0.50, "やや優勢  (0.3-0.5)"),
        (0.0, 0.30, "接戦      (0.0-0.3)"),
    ]
    for low, high, label in bins:
        mask = (winners["確信度"] >= low) & (winners["確信度"] < high)
        count = mask.sum()
        print(f"  {label}: {count:4d}選挙区")

    print("\n--- 接戦選挙区 TOP10 ---")
    tossups = winners.nsmallest(10, "確信度")
    for _, row in tossups.iterrows():
        print(
            f"  {row['選挙区名']:12s} {row['候補者名']:12s} "
            f"({row['政党名']:12s}) 確信度={row['確信度']:.4f}"
        )


def main():
    csv_path = PROCESSED_DIR / "district_candidates.csv"
    if not csv_path.exists():
        print(f"エラー: {csv_path} が見つかりません", file=sys.stderr)
        sys.exit(1)

    df = predict_district_winners(csv_path)

    # 元のCSVを予測結果で更新
    output_path = PROCESSED_DIR / "district_candidates.csv"
    save_results(df, output_path)

    print_aggregate_stats(df)


if __name__ == "__main__":
    main()
