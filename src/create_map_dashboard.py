"""
選挙区マップダッシュボード生成スクリプト
日本地図（都道府県レベル）に選挙区をマッピングし、候補者情報を表示する
"""
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

import sys
sys.path.insert(0, str(Path(__file__).parent))
from config import PARTY_COLORS

DATA_DIR = Path(__file__).parent.parent / "data"
PROCESSED_DIR = DATA_DIR / "processed"
GEOJSON_DIR = DATA_DIR / "geojson"
OUTPUT_DIR = Path(__file__).parent.parent / "output"

# 政党を数値IDにマッピング（コロプレス用）
PARTY_ID_MAP = {
    "自由民主党": 0, "中道改革連合": 1, "日本維新の会": 2,
    "国民民主党": 3, "公明党": 4, "日本共産党": 5,
    "れいわ新選組": 6, "参政党": 7, "チームみらい": 8, "無所属": 9,
}

# 都道府県コード → 名前（選挙区名からコードを逆引き用）
import re
PREFECTURE_NAMES = {
    1: "北海道", 2: "青森県", 3: "岩手県", 4: "宮城県", 5: "秋田県",
    6: "山形県", 7: "福島県", 8: "茨城県", 9: "栃木県", 10: "群馬県",
    11: "埼玉県", 12: "千葉県", 13: "東京都", 14: "神奈川県", 15: "新潟県",
    16: "富山県", 17: "石川県", 18: "福井県", 19: "山梨県", 20: "長野県",
    21: "岐阜県", 22: "静岡県", 23: "愛知県", 24: "三重県", 25: "滋賀県",
    26: "京都府", 27: "大阪府", 28: "兵庫県", 29: "奈良県", 30: "和歌山県",
    31: "鳥取県", 32: "島根県", 33: "岡山県", 34: "広島県", 35: "山口県",
    36: "徳島県", 37: "香川県", 38: "愛媛県", 39: "高知県", 40: "福岡県",
    41: "佐賀県", 42: "長崎県", 43: "熊本県", 44: "大分県", 45: "宮崎県",
    46: "鹿児島県", 47: "沖縄県",
}

# 短い都道府県名 → コード（選挙区名のパース用）
PREF_SHORT_TO_CODE = {}
for _code, _name in PREFECTURE_NAMES.items():
    _short = _name
    for _suf in ["都", "府", "県"]:
        if _short.endswith(_suf):
            _short = _short[:-1]
            break
    PREF_SHORT_TO_CODE[_short] = _code


def _parse_district_name(district_name):
    """'北海道1区' → (prefecture_code, district_number)"""
    m = re.match(r"^(.+?)(\d+)区$", district_name)
    if not m:
        return None, None
    return PREF_SHORT_TO_CODE.get(m.group(1)), int(m.group(2))


# === 世論調査ベースライン（predict_seats.pyと同一） ===
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
TOTAL_SEATS = 465
PR_TOTAL_SEATS = 176

# 比例代表ブロック別議席数
PR_BLOCK_SEATS = {
    "北海道": 8, "東北": 13, "北関東": 19, "南関東": 22,
    "東京": 17, "北陸信越": 11, "東海": 21, "近畿": 28,
    "中国": 11, "四国": 6, "九州": 20,
}

# 中道改革連合は比例では立憲民主党として扱う
PR_PARTY_ALIAS = {
    "中道改革連合": "立憲民主党",
}


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


def compute_combined_seats(data):
    """seat_predictions.csvの統合アンサンブル（Model 6）から合算議席を取得

    サマリーダッシュボードと同じデータソースを使うことで整合性を保つ。
    小選挙区の予測当選者（predict_district_winners.py）の結果も併記する。
    """
    # seat_predictions.csv から統合アンサンブル結果を読み込む
    pred_path = PROCESSED_DIR / "seat_predictions.csv"
    if pred_path.exists():
        pred_df = pd.read_csv(pred_path)
    else:
        pred_df = pd.DataFrame()

    # 小選挙区予測当選者（マップダッシュボード独自の選挙区予測）
    dist_df = data["districts"]
    smd_district_seats = {}
    if not dist_df.empty and "当選予測" in dist_df.columns:
        winners = dist_df[dist_df["当選予測"] == 1]
        party_counts = winners["政党名"].value_counts()
        for party, count in party_counts.items():
            smd_district_seats[party] = int(count)

    combined = {}

    if not pred_df.empty and "model6_total" in pred_df.columns:
        # Model 6（統合アンサンブル）の結果を使用
        for _, row in pred_df.iterrows():
            party = row["party_name"]
            smd = int(row.get("model6_smd", 0))
            pr = int(row.get("model6_pr", 0))
            total = int(row.get("model6_total", 0))
            combined[party] = {"smd": smd, "pr": pr, "total": total}

        # 中道改革連合は小選挙区で独立して立候補しているため、
        # Model 6の「立憲民主党」に含まれるSMD分のうち
        # 選挙区予測で中道改革連合が勝った分を分離表示する
        chudo_smd = smd_district_seats.get("中道改革連合", 0)
        if chudo_smd > 0 and "立憲民主党" in combined:
            cdp = combined["立憲民主党"]
            # 立憲のSMDを中道改革連合の分だけ減らし、中道改革連合として表示
            split_smd = min(chudo_smd, cdp["smd"])
            cdp["smd"] -= split_smd
            cdp["total"] -= split_smd
            combined["中道改革連合"] = {
                "smd": split_smd,
                "pr": 0,
                "total": split_smd,
            }
    else:
        # フォールバック: 選挙区予測 + ドント方式
        pr_scores = {p: max(s, 0.1) for p, s in POLLING_BASELINE.items()}
        pr_seats = dhondt_allocation(pr_scores, PR_TOTAL_SEATS)
        all_parties = set(smd_district_seats.keys()) | set(pr_seats.keys())
        for party in all_parties:
            s = smd_district_seats.get(party, 0)
            p = pr_seats.get(party, 0)
            combined[party] = {"smd": s, "pr": p, "total": s + p}

    return combined


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


def load_map_data():
    """マップ用データを読み込む"""
    data = {}

    dist_path = PROCESSED_DIR / "district_candidates.csv"
    if dist_path.exists():
        dist_df = pd.read_csv(dist_path, dtype={"年齢": str})
        # 都道府県コード・選挙区番号を導出
        parsed = dist_df["選挙区名"].apply(_parse_district_name)
        dist_df["prefecture_code"] = parsed.apply(lambda x: x[0])
        dist_df["district_number"] = parsed.apply(lambda x: x[1])
        dist_df["prefecture_name"] = dist_df["prefecture_code"].map(PREFECTURE_NAMES)
        data["districts"] = dist_df
    else:
        data["districts"] = pd.DataFrame()

    # 都道府県サマリーを候補者データから生成
    data["prefectures"] = _build_prefecture_summary(data["districts"])

    geojson_path = GEOJSON_DIR / "japan.geojson"
    if geojson_path.exists():
        with open(geojson_path, encoding="utf-8") as f:
            data["geojson"] = json.load(f)
    else:
        data["geojson"] = None

    return data


def _build_prefecture_summary(dist_df):
    """候補者データから都道府県サマリーを生成"""
    if dist_df.empty or "当選予測" not in dist_df.columns:
        return pd.DataFrame()

    winners = dist_df[dist_df["当選予測"] == 1].copy()
    party_cols = list(PARTY_ID_MAP.keys())

    rows = []
    for pref_code in sorted(winners["prefecture_code"].dropna().unique()):
        pref_code = int(pref_code)
        pref_winners = winners[winners["prefecture_code"] == pref_code]
        pref_name = PREFECTURE_NAMES.get(pref_code, "")

        n_districts = len(pref_winners)
        party_seats = {}
        for party in party_cols:
            party_seats[party] = int((pref_winners["政党名"] == party).sum())

        dominant_party = max(party_seats, key=party_seats.get) if party_seats else ""
        battleground = int((pref_winners["確信度"] < 0.5).sum())

        row = {
            "prefecture_code": pref_code,
            "prefecture_name": pref_name,
            "total_smd_seats": n_districts,
            "dominant_party": dominant_party,
        }
        row.update(party_seats)
        row["battleground_count"] = battleground
        rows.append(row)

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def build_prefecture_map(data):
    """都道府県コロプレスマップ（政党色で色分け）"""
    pref_df = data["prefectures"]
    geojson = data["geojson"]

    if pref_df.empty or geojson is None:
        return go.Figure().update_layout(title="マップデータなし")

    # 政党IDを割り当て
    pref_df = pref_df.copy()
    pref_df["party_id"] = pref_df["dominant_party"].map(PARTY_ID_MAP).fillna(9).astype(int)

    # 議席内訳テキスト
    party_cols = list(PARTY_ID_MAP.keys())
    hover_texts = []
    for _, row in pref_df.iterrows():
        breakdown = []
        for p in party_cols:
            if p in row and row[p] > 0:
                breakdown.append(f"  {p}: {int(row[p])}議席")
        text = (
            f"<b>{row['prefecture_name']}</b><br>"
            f"小選挙区数: {row['total_smd_seats']}<br>"
            f"優勢政党: {row['dominant_party']}<br>"
            f"接戦区: {row.get('battleground_count', 0)}<br>"
            f"<br>{'<br>'.join(breakdown)}"
        )
        hover_texts.append(text)

    # カスタムカラースケール（政党色に対応）
    parties_ordered = list(PARTY_ID_MAP.keys())
    n = len(parties_ordered)
    colorscale = []
    for i, p in enumerate(parties_ordered):
        frac = i / (n - 1) if n > 1 else 0
        colorscale.append([frac, PARTY_COLORS.get(p, "#999")])

    fig = go.Figure(go.Choroplethmapbox(
        geojson=geojson,
        locations=pref_df["prefecture_code"].tolist(),
        z=pref_df["party_id"].tolist(),
        featureidkey="properties.id",
        colorscale=colorscale,
        zmin=0, zmax=n - 1,
        marker_opacity=0.75,
        marker_line_width=1,
        marker_line_color="white",
        hovertext=hover_texts,
        hoverinfo="text",
        showscale=False,
        customdata=pref_df["prefecture_name"].tolist(),
    ))

    fig.update_layout(
        mapbox=dict(
            style="white-bg",
            center=dict(lat=36.5, lon=137.5),
            zoom=4.2,
            layers=[{
                "below": "traces",
                "sourcetype": "raster",
                "sourceattribution": "© OpenStreetMap",
                "source": [
                    "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
                ],
            }],
        ),
        title="都道府県別 予測優勢政党マップ（クリックで選挙区詳細を表示）",
        height=650,
        margin=dict(l=0, r=0, t=50, b=0),
    )

    return fig


def build_regional_block_chart(data):
    """比例ブロック別の議席予測"""
    pref_df = data["prefectures"]
    if pref_df.empty:
        return go.Figure().update_layout(title="データなし")

    party_cols = list(PARTY_ID_MAP.keys())

    block_data = []
    for block_name, pref_codes in PR_BLOCKS.items():
        block_prefs = pref_df[pref_df["prefecture_code"].isin(pref_codes)]
        row = {"block": block_name}
        for p in party_cols:
            if p in block_prefs.columns:
                row[p] = int(block_prefs[p].sum())
            else:
                row[p] = 0
        row["total"] = sum(row[p] for p in party_cols)
        block_data.append(row)

    block_df = pd.DataFrame(block_data)
    block_order = list(PR_BLOCKS.keys())

    fig = go.Figure()
    for party in party_cols:
        vals = [int(block_df.loc[block_df["block"] == b, party].iloc[0])
                if b in block_df["block"].values else 0
                for b in block_order]
        fig.add_trace(go.Bar(
            y=block_order, x=vals, name=party, orientation="h",
            marker_color=PARTY_COLORS.get(party, "#999"),
            text=[str(v) if v > 0 else "" for v in vals],
            textposition="inside", textfont_size=9,
        ))

    fig.update_layout(
        title="比例ブロック別 小選挙区予測議席（政党別積み上げ）",
        xaxis_title="予測議席数", barmode="stack",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        height=500,
    )
    return fig


def build_battleground_chart(data):
    """接戦区分析（確信度が低い選挙区TOP20）"""
    dist_df = data["districts"]
    if dist_df.empty or "当選予測" not in dist_df.columns:
        return go.Figure().update_layout(title="データなし")

    winners = dist_df[dist_df["当選予測"] == 1].copy()
    close = winners.nsmallest(20, "確信度")

    colors = [PARTY_COLORS.get(p, "#999") for p in close["政党名"]]

    fig = go.Figure(go.Bar(
        y=close["選挙区名"],
        x=close["確信度"],
        orientation="h",
        marker_color=colors,
        text=[f"{c:.2f} ({p})" for c, p in zip(close["確信度"], close["政党名"])],
        textposition="outside",
        hovertemplate=(
            "<b>%{y}</b><br>"
            "当選予測: %{customdata[0]} (%{customdata[1]})<br>"
            "当選確率: %{customdata[2]:.1%}<br>"
            "確信度: %{x:.2f}<extra></extra>"
        ),
        customdata=list(zip(close["候補者名"], close["政党名"], close["当選確率"])),
    ))

    fig.update_layout(
        title="接戦区ランキング（確信度が低い選挙区 TOP20）",
        xaxis_title="確信度",
        xaxis=dict(range=[0, 1.1]),
        height=max(400, len(close) * 30),
    )
    return fig


def build_party_seats_chart(data):
    """政党別予測当選者数の棒グラフ"""
    dist_df = data["districts"]
    if dist_df.empty or "当選予測" not in dist_df.columns:
        return go.Figure().update_layout(title="データなし")

    winners = dist_df[dist_df["当選予測"] == 1]
    party_seats = winners.groupby("政党名").size().sort_values(ascending=True)

    colors = [PARTY_COLORS.get(p, "#999") for p in party_seats.index]

    fig = go.Figure(go.Bar(
        y=party_seats.index,
        x=party_seats.values,
        orientation="h",
        marker_color=colors,
        text=[f"{v}議席" for v in party_seats.values],
        textposition="outside",
    ))

    fig.update_layout(
        title="政党別 予測当選者数（小選挙区289議席）",
        xaxis_title="予測議席数",
        height=max(350, len(party_seats) * 45),
    )
    return fig


def build_confidence_chart(data):
    """確信度の分布ヒストグラム"""
    dist_df = data["districts"]
    if dist_df.empty or "当選予測" not in dist_df.columns:
        return go.Figure().update_layout(title="データなし")

    winners = dist_df[dist_df["当選予測"] == 1]

    # カテゴリ別に集計
    categories = [
        (0.8, 1.01, "安全圏", "#2ECC71"),
        (0.5, 0.80, "優勢", "#3498DB"),
        (0.3, 0.50, "やや優勢", "#F39C12"),
        (0.0, 0.30, "接戦", "#E74C3C"),
    ]

    labels = []
    counts = []
    bar_colors = []
    for low, high, label, color in categories:
        mask = (winners["確信度"] >= low) & (winners["確信度"] < high)
        labels.append(label)
        counts.append(int(mask.sum()))
        bar_colors.append(color)

    fig = go.Figure(go.Bar(
        x=labels,
        y=counts,
        marker_color=bar_colors,
        text=[f"{c}区" for c in counts],
        textposition="outside",
        textfont_size=14,
    ))

    fig.update_layout(
        title="確信度別 選挙区分布",
        yaxis_title="選挙区数",
        height=380,
    )
    return fig


def build_combined_seats_chart(combined_seats):
    """政党別 小選挙区＋比例代表 合算議席の積み上げ棒グラフ"""
    if not combined_seats:
        return go.Figure().update_layout(title="データなし")

    # 合計議席の降順でソート
    sorted_parties = sorted(
        combined_seats.keys(),
        key=lambda p: combined_seats[p]["total"],
    )
    # 0議席の政党を除外
    sorted_parties = [p for p in sorted_parties if combined_seats[p]["total"] > 0]

    parties = sorted_parties
    smd_vals = [combined_seats[p]["smd"] for p in parties]
    pr_vals = [combined_seats[p]["pr"] for p in parties]
    total_vals = [combined_seats[p]["total"] for p in parties]

    fig = go.Figure()

    # 小選挙区
    fig.add_trace(go.Bar(
        y=parties,
        x=smd_vals,
        name="小選挙区（289議席）",
        orientation="h",
        marker_color=[PARTY_COLORS.get(p, "#999") for p in parties],
        text=[f"{v}" if v > 0 else "" for v in smd_vals],
        textposition="inside",
        textfont_size=10,
    ))

    # 比例代表（やや薄い色）
    fig.add_trace(go.Bar(
        y=parties,
        x=pr_vals,
        name="比例代表（176議席）",
        orientation="h",
        marker_color=[PARTY_COLORS.get(p, "#999") for p in parties],
        marker_opacity=0.5,
        marker_line_color=[PARTY_COLORS.get(p, "#999") for p in parties],
        marker_line_width=1,
        text=[f"{v}" if v > 0 else "" for v in pr_vals],
        textposition="inside",
        textfont_size=10,
    ))

    # 合計を右端に表示
    fig.add_trace(go.Scatter(
        x=[t + 5 for t in total_vals],
        y=parties,
        mode="text",
        text=[f"<b>{t}議席</b>" for t in total_vals],
        textposition="middle right",
        textfont_size=11,
        showlegend=False,
    ))

    fig.update_layout(
        title="政党別 予測合計議席（小選挙区＋比例代表 = 465議席）",
        xaxis_title="予測議席数",
        barmode="stack",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        height=max(400, len(parties) * 50),
        xaxis=dict(range=[0, max(total_vals) * 1.2] if total_vals else [0, 250]),
    )
    return fig


def generate_prefecture_panels_html(data):
    """47都道府県の選挙区詳細パネルHTML（JavaScriptで切り替え用）"""
    dist_df = data["districts"]
    if dist_df.empty:
        return ""

    panels_html = ""
    for pref_code in sorted(dist_df["prefecture_code"].dropna().unique()):
        pref_code = int(pref_code)
        pref_data = dist_df[dist_df["prefecture_code"] == pref_code].copy()
        pref_name = PREFECTURE_NAMES.get(pref_code, "")

        # 選挙区ごとにグループ化
        table_rows = ""
        for dist_num in sorted(pref_data["district_number"].dropna().unique()):
            dist_num = int(dist_num)
            dist_data = pref_data[pref_data["district_number"] == dist_num].sort_values(
                "当選確率", ascending=False
            )
            dist_name = dist_data["選挙区名"].iloc[0]

            for _, row in dist_data.iterrows():
                party = row["政党名"]
                color = PARTY_COLORS.get(party, "#999")
                is_winner = int(row.get("当選予測", 0)) == 1
                win_badge = "&#x2605;" if is_winner else ""
                prob = row.get("当選確率", 0)
                confidence = row.get("確信度", 0)
                kubun = row.get("区分", "")
                age = row.get("年齢", "-")

                # 確信度バッジ色
                if confidence >= 0.8:
                    conf_color = "#2ECC71"
                elif confidence >= 0.5:
                    conf_color = "#3498DB"
                elif confidence >= 0.3:
                    conf_color = "#F39C12"
                else:
                    conf_color = "#E74C3C"

                row_style = "background:#e8f5e9; font-weight:500;" if is_winner else ""

                table_rows += f"""<tr style="{row_style}">
                    <td>{dist_name}</td>
                    <td>{win_badge} {row['候補者名']}</td>
                    <td><span style="color:{color}; font-weight:bold;">&#x25CF;</span> {party}</td>
                    <td style="text-align:center;">{kubun}</td>
                    <td style="text-align:right;">{age}</td>
                    <td style="text-align:right;">{prob:.1%}</td>
                    <td style="text-align:center;">
                        <span style="color:{conf_color}; font-weight:bold;">{confidence:.2f}</span>
                    </td>
                </tr>"""

        n_districts = pref_data["選挙区名"].nunique()
        panels_html += f"""
        <div id="pref-panel-{pref_code}" class="pref-panel" style="display:none;">
            <h3 style="margin: 0 0 1rem 0; color: #1a1a2e;">
                {pref_name} の小選挙区一覧
                <span style="font-size: 0.8rem; color: #666; font-weight: normal;">
                    （{n_districts}選挙区）
                </span>
            </h3>
            <div style="overflow-x: auto;">
            <table class="district-table">
                <thead>
                    <tr>
                        <th>選挙区</th>
                        <th>候補者名</th>
                        <th>政党</th>
                        <th>区分</th>
                        <th>年齢</th>
                        <th>当選確率</th>
                        <th>確信度</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
            </div>
        </div>
        """

    return panels_html


def generate_legend_html():
    """政党カラー凡例のHTML"""
    items = ""
    for party, color in PARTY_COLORS.items():
        if party == "その他":
            continue
        items += (
            f'<span style="display:inline-flex; align-items:center; margin: 0.3rem 0.8rem;">'
            f'<span style="width:14px; height:14px; background:{color}; '
            f'border-radius:3px; display:inline-block; margin-right:5px;"></span>'
            f'{party}</span>'
        )
    return items


def create_map_dashboard():
    """選挙区マップHTMLダッシュボードを生成"""
    print("選挙区マップデータ読み込み中...")
    data = load_map_data()

    if data["prefectures"].empty:
        print("都道府県データがありません。先に generate_sample_data.py を実行してください。")
        return

    if data["geojson"] is None:
        print("GeoJSONファイルがありません。data/geojson/japan.geojson を配置してください。")
        return

    # 統計
    pref_df = data["prefectures"]
    dist_df = data["districts"]
    total_districts = int(pref_df["total_smd_seats"].sum()) if not pref_df.empty else 0
    total_candidates = len(dist_df) if not dist_df.empty else 0
    winners = dist_df[dist_df["当選予測"] == 1] if (not dist_df.empty and "当選予測" in dist_df.columns) else pd.DataFrame()
    battleground = int((winners["確信度"] < 0.5).sum()) if not winners.empty else 0
    dominant_counts = pref_df["dominant_party"].value_counts() if not pref_df.empty else pd.Series()
    top_dominant = f"{dominant_counts.index[0]}（{dominant_counts.iloc[0]}都道府県）" if len(dominant_counts) > 0 else "-"

    # 合算議席（小選挙区＋比例代表）
    combined_seats = compute_combined_seats(data)

    # 当選政党の議席数トップ（合算ベース）
    if combined_seats:
        top_combined = max(combined_seats.items(), key=lambda x: x[1]["total"])
        top_party_str = f"{top_combined[0]} {top_combined[1]['total']}議席"
        total_combined = sum(v["total"] for v in combined_seats.values())
    else:
        top_party_str = "-"
        total_combined = 0

    print("グラフ生成中...")
    fig_map = build_prefecture_map(data)
    fig_blocks = build_regional_block_chart(data)
    fig_battle = build_battleground_chart(data)
    fig_party_seats = build_party_seats_chart(data)
    fig_confidence = build_confidence_chart(data)
    fig_combined = build_combined_seats_chart(combined_seats)

    # 共通Plotlyレイアウト
    for fig in [fig_blocks, fig_battle, fig_party_seats, fig_confidence, fig_combined]:
        fig.update_layout(
            template="plotly_white",
            font=dict(family="Hiragino Sans, Noto Sans JP, sans-serif"),
            title_font_size=18,
            hoverlabel=dict(font_size=13),
        )
    fig_map.update_layout(
        font=dict(family="Hiragino Sans, Noto Sans JP, sans-serif"),
        title_font_size=18,
    )

    # チャートHTML
    map_html = fig_map.to_html(full_html=False, include_plotlyjs=False, div_id="map-chart")
    blocks_html = fig_blocks.to_html(full_html=False, include_plotlyjs=False)
    battle_html = fig_battle.to_html(full_html=False, include_plotlyjs=False)
    party_seats_html = fig_party_seats.to_html(full_html=False, include_plotlyjs=False)
    confidence_html = fig_confidence.to_html(full_html=False, include_plotlyjs=False)
    combined_html = fig_combined.to_html(full_html=False, include_plotlyjs=False)

    # 都道府県パネル
    panels_html = generate_prefecture_panels_html(data)
    legend_html = generate_legend_html()

    html_template = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>第51回衆院選 選挙区マップ</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  :root {{
    --primary: #1a1a2e;
    --secondary: #16213e;
    --accent: #0f3460;
    --highlight: #e94560;
    --bg: #f0f2f5;
    --card: #ffffff;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'Hiragino Sans', 'Noto Sans JP', 'Helvetica Neue', sans-serif;
    background: var(--bg);
    color: #333;
  }}
  .header {{
    background: linear-gradient(135deg, #1a1a2e, #0f3460);
    color: white;
    padding: 2rem 2rem 1.5rem;
    text-align: center;
  }}
  .header h1 {{ font-size: 1.8rem; margin-bottom: 0.5rem; }}
  .header p {{ font-size: 0.95rem; opacity: 0.85; }}
  .nav-bar {{
    background: #1a1a2e;
    padding: 0.8rem 2rem;
    text-align: center;
  }}
  .nav-bar a {{
    color: white; text-decoration: none;
    padding: 0.5rem 1.5rem; border-radius: 6px;
    margin: 0 0.3rem; font-size: 0.9rem;
    transition: background 0.2s;
  }}
  .nav-bar a:hover {{ background: rgba(255,255,255,0.15); }}
  .nav-bar a.active {{ background: var(--highlight); }}
  .stats-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem; padding: 1.5rem 2rem;
    max-width: 1400px; margin: -1.5rem auto 0;
  }}
  .stat-card {{
    background: var(--card); border-radius: 12px;
    padding: 1.2rem; text-align: center;
    box-shadow: 0 2px 12px rgba(0,0,0,0.08);
    transition: transform 0.2s;
  }}
  .stat-card:hover {{ transform: translateY(-2px); }}
  .stat-value {{ font-size: 1.8rem; font-weight: 700; color: var(--accent); }}
  .stat-label {{ font-size: 0.85rem; color: #666; margin-top: 0.3rem; }}
  .dashboard {{
    max-width: 1400px; margin: 0 auto;
    padding: 1rem 2rem 3rem;
  }}
  .section-title {{
    font-size: 1.3rem; font-weight: 700; color: var(--primary);
    margin: 2rem 0 1rem; padding-left: 0.8rem;
    border-left: 4px solid var(--highlight);
  }}
  .chart-container {{
    background: var(--card); border-radius: 12px;
    padding: 1rem; margin-bottom: 1.5rem;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
  }}
  .info-box {{
    background: var(--card); border-radius: 12px;
    padding: 1.2rem; margin-bottom: 1.5rem;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    border-left: 4px solid var(--highlight);
  }}
  .info-box p {{ font-size: 0.9rem; color: #555; line-height: 1.6; }}
  .legend-bar {{
    background: var(--card); border-radius: 12px;
    padding: 0.8rem 1.2rem; margin-bottom: 1.5rem;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    text-align: center; font-size: 0.85rem;
  }}
  .pref-detail-container {{
    background: var(--card); border-radius: 12px;
    padding: 1.5rem; margin-bottom: 1.5rem;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    min-height: 100px;
  }}
  .pref-detail-placeholder {{
    text-align: center; color: #999; padding: 2rem;
    font-size: 1rem;
  }}
  .district-table {{
    width: 100%; border-collapse: collapse;
    font-size: 0.85rem;
  }}
  .district-table th {{
    background: #f8f9fa; font-weight: 600;
    padding: 0.5rem 0.6rem; text-align: left;
    border-bottom: 2px solid #dee2e6;
    position: sticky; top: 0;
  }}
  .district-table td {{
    padding: 0.4rem 0.6rem;
    border-bottom: 1px solid #eee;
  }}
  .district-table tr:hover {{
    background: #f0f7ff;
  }}
  .footer {{
    text-align: center; padding: 2rem;
    color: #999; font-size: 0.85rem;
  }}
  @media (max-width: 900px) {{
    .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
  }}
  @media (max-width: 768px) {{
    .dashboard > div[style*="grid-template-columns"] {{
      grid-template-columns: 1fr !important;
    }}
  }}
</style>
</head>
<body>
<div class="nav-bar">
  <a href="election_dashboard.html">YouTube分析</a>
  <a href="news_dashboard.html">ニュース記事分析</a>
  <a href="summary_dashboard.html">まとめ・予測比較</a>
  <a href="map_dashboard.html" class="active">選挙区マップ</a>
</div>

<div class="header">
  <h1>第51回衆院選 選挙区マップ</h1>
  <p>47都道府県 × 289小選挙区 ＋ 比例代表176議席 = 465議席の予測</p>
</div>

<div class="stats-grid">
  <div class="stat-card" style="border-top: 3px solid var(--accent);">
    <div class="stat-value">{total_combined}</div>
    <div class="stat-label">合計予測議席（小選挙区{total_districts} + 比例{PR_TOTAL_SEATS}）</div>
  </div>
  <div class="stat-card" style="border-top: 3px solid var(--highlight);">
    <div class="stat-value">{total_candidates}</div>
    <div class="stat-label">候補者数</div>
  </div>
  <div class="stat-card" style="border-top: 3px solid #F39C12;">
    <div class="stat-value">{battleground}</div>
    <div class="stat-label">接戦・やや優勢区</div>
  </div>
  <div class="stat-card" style="border-top: 3px solid #3CB371;">
    <div class="stat-value">{top_party_str}</div>
    <div class="stat-label">予測最多議席政党（合算）</div>
  </div>
  <div class="stat-card" style="border-top: 3px solid #9B59B6;">
    <div class="stat-value">{top_dominant}</div>
    <div class="stat-label">最多優勢都道府県</div>
  </div>
</div>

<div class="dashboard">
  <div class="info-box">
    <p>
      <strong>選挙区マップについて:</strong>
      都道府県を予測優勢政党の色で表示しています。
      地図上の都道府県をクリックすると、下部に各小選挙区の候補者・当選予測情報が表示されます。
      予測は政党の地域強度・世論調査・現職有利の3要素に基づくモデルで算出しています。
    </p>
  </div>

  <div class="legend-bar">
    <strong>政党カラー:</strong> {legend_html}
  </div>

  <h2 class="section-title">都道府県別 予測優勢政党マップ</h2>
  <div class="chart-container">
    {map_html}
  </div>

  <h2 class="section-title" id="detail-title">選挙区詳細</h2>
  <div class="pref-detail-container" id="pref-detail">
    <div class="pref-detail-placeholder">
      ↑ 地図上の都道府県をクリックすると、選挙区の詳細が表示されます
    </div>
    {panels_html}
  </div>

  <h2 class="section-title">小選挙区＋比例代表 合算議席予測</h2>
  <div class="info-box">
    <p>
      <strong>合算議席について:</strong>
      統合アンサンブルモデル（YouTube分析・ニュース記事・世論調査を複合的に使用したModel 6）による全465議席の予測です。
      小選挙区289議席と比例代表176議席の内訳を積み上げ表示しています。
      濃い色が小選挙区、薄い色が比例代表の議席です。
      ※ 中道改革連合は小選挙区の選挙区予測結果を別途表示しています。
    </p>
  </div>
  <div class="chart-container">
    {combined_html}
  </div>

  <h2 class="section-title">小選挙区 当選予測 集計</h2>
  <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 1.5rem;">
    <div class="chart-container">
      {party_seats_html}
    </div>
    <div class="chart-container">
      {confidence_html}
    </div>
  </div>

  <h2 class="section-title">比例ブロック別 予測議席</h2>
  <div class="chart-container">
    {blocks_html}
  </div>

  <h2 class="section-title">接戦区分析</h2>
  <div class="chart-container">
    {battle_html}
  </div>
</div>

<div class="footer">
  <p>第51回衆議院議員総選挙 選挙区マップ分析プロジェクト</p>
  <p>※ 予測は統計モデルに基づく推計であり、実際の選挙結果を保証するものではありません。</p>
</div>

<script>
// 都道府県クリックで選挙区詳細を表示
var mapDiv = document.getElementById('map-chart');
if (mapDiv) {{
    mapDiv.on('plotly_click', function(eventData) {{
        if (eventData && eventData.points && eventData.points[0]) {{
            var prefCode = eventData.points[0].location;
            showPrefPanel(prefCode);
        }}
    }});
}}

function showPrefPanel(prefCode) {{
    // 全パネルを非表示
    var panels = document.querySelectorAll('.pref-panel');
    panels.forEach(function(p) {{ p.style.display = 'none'; }});

    // プレースホルダーを非表示
    var placeholder = document.querySelector('.pref-detail-placeholder');
    if (placeholder) placeholder.style.display = 'none';

    // 該当パネルを表示
    var panel = document.getElementById('pref-panel-' + prefCode);
    if (panel) {{
        panel.style.display = 'block';
        // スクロール
        document.getElementById('detail-title').scrollIntoView({{ behavior: 'smooth' }});
    }}
}}
</script>

</body>
</html>"""

    output_path = OUTPUT_DIR / "map_dashboard.html"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_template, encoding="utf-8")
    print(f"\n選挙区マップダッシュボード生成完了!")
    print(f"  出力先: {output_path}")
    return output_path


if __name__ == "__main__":
    create_map_dashboard()
