"""
選挙区マップダッシュボード生成スクリプト
日本地図（都道府県レベル）に選挙区をマッピングし、候補者情報を表示する
"""
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

DATA_DIR = Path(__file__).parent.parent / "data"
PROCESSED_DIR = DATA_DIR / "processed"
GEOJSON_DIR = DATA_DIR / "geojson"
OUTPUT_DIR = Path(__file__).parent.parent / "output"

PARTY_COLORS = {
    "自由民主党": "#E3242B",
    "日本維新の会": "#3CB371",
    "立憲民主党": "#1E90FF",
    "国民民主党": "#FF8C00",
    "日本共産党": "#DC143C",
    "れいわ新選組": "#FF69B4",
    "参政党": "#DAA520",
    "公明党": "#F5A623",
    "チームみらい": "#00BCD4",
    "無所属": "#999999",
    "その他": "#999999",
}

# 政党を数値IDにマッピング（コロプレス用）
PARTY_ID_MAP = {
    "自由民主党": 0, "立憲民主党": 1, "日本維新の会": 2,
    "国民民主党": 3, "公明党": 4, "日本共産党": 5,
    "れいわ新選組": 6, "参政党": 7, "チームみらい": 8, "無所属": 9,
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


def load_map_data():
    """マップ用データを読み込む"""
    data = {}

    pref_path = PROCESSED_DIR / "prefecture_summary.csv"
    data["prefectures"] = pd.read_csv(pref_path) if pref_path.exists() else pd.DataFrame()

    dist_path = PROCESSED_DIR / "district_candidates.csv"
    data["districts"] = pd.read_csv(dist_path) if dist_path.exists() else pd.DataFrame()

    geojson_path = GEOJSON_DIR / "japan.geojson"
    if geojson_path.exists():
        with open(geojson_path, encoding="utf-8") as f:
            data["geojson"] = json.load(f)
    else:
        data["geojson"] = None

    return data


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
    party_cols = ["自由民主党", "立憲民主党", "日本維新の会", "国民民主党",
                  "公明党", "日本共産党", "れいわ新選組", "参政党", "チームみらい", "無所属"]
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
    parties_ordered = ["自由民主党", "立憲民主党", "日本維新の会", "国民民主党",
                       "公明党", "日本共産党", "れいわ新選組", "参政党", "チームみらい", "無所属"]
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

    party_cols = ["自由民主党", "立憲民主党", "日本維新の会", "国民民主党",
                  "公明党", "日本共産党", "れいわ新選組", "参政党", "チームみらい"]

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
    """接戦区分析（得票差5%以内の選挙区）"""
    dist_df = data["districts"]
    if dist_df.empty:
        return go.Figure().update_layout(title="データなし")

    # 当選予測者のみ（rank=1）でmargin < 0.05
    winners = dist_df[dist_df["predicted_rank"] == 1].copy()
    close = winners[winners["margin"] < 0.05].sort_values("margin")

    if close.empty:
        close = winners.nsmallest(15, "margin")

    close = close.head(20)

    colors = [PARTY_COLORS.get(p, "#999") for p in close["party"]]

    fig = go.Figure(go.Bar(
        y=close["district_name"],
        x=close["margin"] * 100,
        orientation="h",
        marker_color=colors,
        text=[f"{m*100:.1f}% ({p})" for m, p in zip(close["margin"], close["party"])],
        textposition="outside",
        hovertemplate=(
            "<b>%{y}</b><br>"
            "当選予測: %{customdata[0]} (%{customdata[1]})<br>"
            "得票率差: %{x:.1f}%<extra></extra>"
        ),
        customdata=list(zip(close["candidate_name"], close["party"])),
    ))

    fig.update_layout(
        title="接戦区ランキング（当選者と次点の得票率差が小さい選挙区）",
        xaxis_title="得票率差 (%)",
        height=max(400, len(close) * 30),
    )
    return fig


def generate_prefecture_panels_html(data):
    """47都道府県の選挙区詳細パネルHTML（JavaScriptで切り替え用）"""
    dist_df = data["districts"]
    if dist_df.empty:
        return ""

    panels_html = ""
    for pref_code in sorted(dist_df["prefecture_code"].unique()):
        pref_data = dist_df[dist_df["prefecture_code"] == pref_code].copy()
        pref_name = pref_data["prefecture_name"].iloc[0]

        # 選挙区ごとにグループ化
        table_rows = ""
        for dist_num in sorted(pref_data["district_number"].unique()):
            dist_data = pref_data[pref_data["district_number"] == dist_num].sort_values("predicted_rank")
            dist_name = dist_data["district_name"].iloc[0]

            for _, row in dist_data.iterrows():
                party = row["party"]
                color = PARTY_COLORS.get(party, "#999")
                rank_badge = "🥇" if row["predicted_rank"] == 1 else (
                    "🥈" if row["predicted_rank"] == 2 else "")
                incumbent = "現" if row["is_incumbent"] else ""

                table_rows += f"""<tr style="{'background:#f8f9fa;' if row['predicted_rank'] == 1 else ''}">
                    <td>{dist_name}</td>
                    <td>{rank_badge} {row['candidate_name']}</td>
                    <td><span style="color:{color}; font-weight:bold;">●</span> {party}</td>
                    <td style="text-align:right;">{row['predicted_vote_share']*100:.1f}%</td>
                    <td style="text-align:center;">{incumbent}</td>
                    <td style="text-align:right;">{row['age']}</td>
                    <td style="text-align:right;">{row['youtube_score']:.2f}</td>
                    <td style="text-align:right;">{row['news_mentions']}</td>
                </tr>"""

        # パネルHTML
        panels_html += f"""
        <div id="pref-panel-{pref_code}" class="pref-panel" style="display:none;">
            <h3 style="margin: 0 0 1rem 0; color: #1a1a2e;">
                {pref_name} の小選挙区一覧
                <span style="font-size: 0.8rem; color: #666; font-weight: normal;">
                    （{len(pref_data[pref_data['predicted_rank']==1])}選挙区）
                </span>
            </h3>
            <div style="overflow-x: auto;">
            <table class="district-table">
                <thead>
                    <tr>
                        <th>選挙区</th>
                        <th>候補者名</th>
                        <th>政党</th>
                        <th>予測得票率</th>
                        <th>現職</th>
                        <th>年齢</th>
                        <th>YTスコア</th>
                        <th>ニュース</th>
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
    total_districts = int(pref_df["total_smd_seats"].sum())
    total_candidates = len(dist_df) if not dist_df.empty else 0
    winners = dist_df[dist_df["predicted_rank"] == 1] if not dist_df.empty else pd.DataFrame()
    battleground = int(winners[winners["margin"] < 0.05].shape[0]) if not winners.empty else 0
    dominant_counts = pref_df["dominant_party"].value_counts()
    top_dominant = f"{dominant_counts.index[0]}（{dominant_counts.iloc[0]}都道府県）" if len(dominant_counts) > 0 else "-"

    print("グラフ生成中...")
    fig_map = build_prefecture_map(data)
    fig_blocks = build_regional_block_chart(data)
    fig_battle = build_battleground_chart(data)

    # 共通Plotlyレイアウト
    for fig in [fig_blocks, fig_battle]:
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
  <p>47都道府県 × 289小選挙区の候補者・予測情報</p>
</div>

<div class="stats-grid">
  <div class="stat-card" style="border-top: 3px solid var(--accent);">
    <div class="stat-value">{total_districts}</div>
    <div class="stat-label">小選挙区数</div>
  </div>
  <div class="stat-card" style="border-top: 3px solid var(--highlight);">
    <div class="stat-value">{total_candidates}</div>
    <div class="stat-label">候補者数</div>
  </div>
  <div class="stat-card" style="border-top: 3px solid #FF8C00;">
    <div class="stat-value">{battleground}</div>
    <div class="stat-label">接戦区（差5%以内）</div>
  </div>
  <div class="stat-card" style="border-top: 3px solid #3CB371;">
    <div class="stat-value">{top_dominant}</div>
    <div class="stat-label">最多優勢政党</div>
  </div>
</div>

<div class="dashboard">
  <div class="info-box">
    <p>
      <strong>選挙区マップについて:</strong>
      都道府県を予測優勢政党の色で表示しています。
      地図上の都道府県をクリックすると、下部に各小選挙区の候補者情報が表示されます。
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
  <p>※ サンプルデータによるデモ表示です。候補者名・予測結果はすべて架空のものです。</p>
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
