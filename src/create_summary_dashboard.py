"""
まとめ・予測比較ダッシュボード生成スクリプト
YouTube分析・ニュース分析の全モデル予測を横断的に比較する
"""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

DATA_DIR = Path(__file__).parent.parent / "data"
PROCESSED_DIR = DATA_DIR / "processed"
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
    "その他": "#999999",
}

ALL_MODEL_LABELS = {
    "baseline": "世論調査ベースライン",
    "model1": "YT エンゲージメント",
    "model2": "YT 感情分析加重",
    "model3": "YT 世論調査+勢い",
    "model4": "YT アンサンブル",
    "model5": "ニュース記事モデル",
    "model6": "統合アンサンブル",
}

ALL_MODEL_COLORS = {
    "baseline": "#888888",
    "model1": "#4169E1",
    "model2": "#2ECC71",
    "model3": "#E74C3C",
    "model4": "#9B59B6",
    "model5": "#FF8C00",
    "model6": "#1a1a2e",
}

# モデルのカテゴリ
BASELINE_MODELS = ["baseline"]
YT_MODELS = ["model1", "model2", "model3", "model4"]
NEWS_MODELS = ["model5"]
COMBINED_MODELS = ["model6"]


def load_data():
    """予測データを読み込む"""
    pred_path = PROCESSED_DIR / "seat_predictions.csv"
    if pred_path.exists():
        return pd.read_csv(pred_path)
    return pd.DataFrame()


def _get_model_col(model_key):
    """モデルキーから議席数カラム名を返す"""
    if model_key == "baseline":
        return "polling_baseline"
    return f"{model_key}_total"


def build_all_models_comparison(df):
    """世論調査ベースライン + 全6モデルの議席予測を一覧比較"""
    if df.empty or "model6_total" not in df.columns:
        return go.Figure().update_layout(title="予測データなし")

    party_order = df.sort_values("model6_total", ascending=False)["party_name"].tolist()

    fig = go.Figure()
    for model_key, label in ALL_MODEL_LABELS.items():
        col = _get_model_col(model_key)
        if col not in df.columns:
            continue
        vals = [int(df.loc[df["party_name"] == p, col].iloc[0])
                if p in df["party_name"].values else 0
                for p in party_order]
        fig.add_trace(go.Bar(
            x=party_order, y=vals, name=label,
            marker_color=ALL_MODEL_COLORS[model_key],
            text=vals, textposition="outside", textfont_size=9,
        ))

    fig.add_shape(type="line", x0=-0.5, x1=len(party_order) - 0.5,
                  y0=233, y1=233, line=dict(color="orange", width=2, dash="dot"))
    fig.add_annotation(x=len(party_order) - 1, y=233, text="過半数(233)",
                       showarrow=False, font=dict(color="orange", size=11), yshift=12)

    fig.update_layout(
        title="世論調査ベースライン + 全6モデル 政党別議席予測比較（合計465議席）",
        yaxis_title="予測議席数", barmode="group",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        height=600,
    )
    return fig


def build_yt_vs_news_vs_combined(df):
    """世論調査ベースライン vs YouTube(M4) vs ニュース(M5) vs 統合(M6) の比較"""
    if df.empty or "model6_total" not in df.columns:
        return go.Figure().update_layout(title="予測データなし")

    key_models = {
        "baseline": "世論調査ベースライン",
        "model4": "YouTubeアンサンブル",
        "model5": "ニュース記事モデル",
        "model6": "統合アンサンブル",
    }
    key_colors = {"baseline": "#888888", "model4": "#9B59B6", "model5": "#FF8C00", "model6": "#1a1a2e"}

    party_order = df.sort_values("model6_total", ascending=False)["party_name"].tolist()

    fig = go.Figure()
    for model_key, label in key_models.items():
        col = _get_model_col(model_key)
        if col not in df.columns:
            continue
        vals = [int(df.loc[df["party_name"] == p, col].iloc[0])
                if p in df["party_name"].values else 0
                for p in party_order]
        fig.add_trace(go.Bar(
            x=party_order, y=vals, name=label,
            marker_color=key_colors[model_key],
            text=vals, textposition="outside", textfont_size=10,
        ))

    fig.add_shape(type="line", x0=-0.5, x1=len(party_order) - 0.5,
                  y0=233, y1=233, line=dict(color="orange", width=2, dash="dot"))
    fig.add_annotation(x=len(party_order) - 1, y=233, text="過半数(233)",
                       showarrow=False, font=dict(color="orange", size=11), yshift=12)

    fig.update_layout(
        title="世論調査ベースライン vs YouTube vs ニュース vs 統合 予測比較",
        yaxis_title="予測議席数", barmode="group",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        height=550,
    )
    return fig


def build_combined_breakdown(df):
    """統合アンサンブル(M6) の小選挙区/比例内訳"""
    if df.empty or "model6_total" not in df.columns:
        return go.Figure().update_layout(title="予測データなし")

    df = df.sort_values("model6_total", ascending=True)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=df["party_name"], x=df["model6_smd"],
        name="小選挙区", orientation="h",
        marker_color="#4169E1",
        text=df["model6_smd"], textposition="inside",
    ))
    fig.add_trace(go.Bar(
        y=df["party_name"], x=df["model6_pr"],
        name="比例代表", orientation="h",
        marker_color="#FF6347",
        text=df["model6_pr"], textposition="inside",
    ))

    fig.update_layout(
        title="統合アンサンブル予測 小選挙区 vs 比例代表 内訳",
        xaxis_title="議席数", barmode="stack",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        height=500,
    )
    return fig


def build_model_divergence(df):
    """モデル間の予測差異（最大-最小のレンジ）- ベースライン含む"""
    if df.empty or "model6_total" not in df.columns:
        return go.Figure().update_layout(title="予測データなし")

    model_cols = [_get_model_col(m) for m in ALL_MODEL_LABELS.keys() if _get_model_col(m) in df.columns]
    df = df.copy()
    df["min_pred"] = df[model_cols].min(axis=1)
    df["max_pred"] = df[model_cols].max(axis=1)
    df["range"] = df["max_pred"] - df["min_pred"]
    df["m6"] = df["model6_total"]
    df = df.sort_values("range", ascending=True)

    fig = go.Figure()

    # レンジバー（最小-最大）
    for i, (_, row) in enumerate(df.iterrows()):
        fig.add_trace(go.Scatter(
            x=[row["min_pred"], row["max_pred"]],
            y=[row["party_name"], row["party_name"]],
            mode="lines",
            line=dict(color="#CCCCCC", width=8),
            showlegend=False,
            hoverinfo="skip",
        ))

    # 各モデルのドット（ベースライン含む）
    for model_key, label in ALL_MODEL_LABELS.items():
        col = _get_model_col(model_key)
        if col not in df.columns:
            continue
        fig.add_trace(go.Scatter(
            x=df[col], y=df["party_name"],
            mode="markers", name=label,
            marker=dict(color=ALL_MODEL_COLORS[model_key], size=10,
                        line=dict(width=1, color="white")),
            hovertemplate=f"<b>{label}</b><br>" + "%{y}: %{x}議席<extra></extra>",
        ))

    fig.update_layout(
        title="モデル間の予測差異（各ドット＝モデル予測、灰色バー＝レンジ）※世論調査ベースライン含む",
        xaxis_title="予測議席数",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        height=max(450, len(df) * 45),
    )
    return fig


def build_coalition_combined(df):
    """連立ブロック別 統合予測（ベースライン/M4/M5/M6比較）"""
    if df.empty or "model6_total" not in df.columns:
        return go.Figure().update_layout(title="予測データなし")

    coalitions = {
        "与党連合\n(自民+維新)": ["自由民主党", "日本維新の会"],
        "中道改革連合\n(立憲+公明)": ["立憲民主党", "公明党"],
        "国民民主党": ["国民民主党"],
        "チームみらい": ["チームみらい"],
        "その他野党\n(共産+れいわ+参政)": ["日本共産党", "れいわ新選組", "参政党"],
        "その他/無所属": ["その他"],
    }

    key_models = {
        "baseline": "世論調査ベースライン",
        "model4": "YouTubeアンサンブル",
        "model5": "ニュース記事モデル",
        "model6": "統合アンサンブル",
    }
    key_colors = {"baseline": "#888888", "model4": "#9B59B6", "model5": "#FF8C00", "model6": "#1a1a2e"}

    fig = go.Figure()
    for model_key, label in key_models.items():
        col = _get_model_col(model_key)
        if col not in df.columns:
            continue
        names = []
        values = []
        for coalition_name, parties in coalitions.items():
            seats = sum(
                int(df.loc[df["party_name"] == p, col].iloc[0])
                for p in parties if p in df["party_name"].values
            )
            names.append(coalition_name)
            values.append(seats)

        fig.add_trace(go.Bar(
            x=values, y=names, orientation="h",
            name=label, marker_color=key_colors[model_key],
            text=[f"{v}議席" for v in values], textposition="outside",
        ))

    fig.add_shape(type="line", x0=233, x1=233, y0=-0.5, y1=len(coalitions) - 0.5,
                  line=dict(color="orange", width=2, dash="dot"))
    fig.add_annotation(x=233, y=len(coalitions) - 0.5, text="過半数\n(233)", showarrow=False,
                       font=dict(color="orange", size=10), xshift=-5, yshift=15)

    fig.add_shape(type="line", x0=310, x1=310, y0=-0.5, y1=len(coalitions) - 0.5,
                  line=dict(color="red", width=2, dash="dot"))
    fig.add_annotation(x=310, y=len(coalitions) - 0.5, text="2/3\n(310)", showarrow=False,
                       font=dict(color="red", size=10), xshift=-5, yshift=15)

    fig.update_layout(
        title="連立ブロック別 予測比較（YouTube / ニュース / 統合）",
        xaxis_title="議席数", barmode="group",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        height=500,
    )
    return fig


def build_data_source_radar(df):
    """統合予測の根拠データソース比較（レーダーチャート）"""
    if df.empty or "model6_total" not in df.columns:
        return go.Figure().update_layout(title="予測データなし")

    # 上位5政党のみ
    top5 = df.nlargest(5, "model6_total")

    fig = go.Figure()
    categories = ["世論調査BL", "YTエンゲージ", "YT感情", "世論調査+YT", "YTアンサンブル", "ニュース", "統合"]

    for _, row in top5.iterrows():
        party = row["party_name"]
        values = [
            row.get("polling_baseline", 0),
            row.get("model1_total", 0),
            row.get("model2_total", 0),
            row.get("model3_total", 0),
            row.get("model4_total", 0),
            row.get("model5_total", 0),
            row.get("model6_total", 0),
        ]
        values.append(values[0])  # close the polygon

        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=categories + [categories[0]],
            name=party,
            line=dict(color=PARTY_COLORS.get(party, "#888"), width=2),
            fill="toself", opacity=0.2,
        ))

    fig.update_layout(
        title="上位5政党 モデル別予測レーダーチャート",
        polar=dict(radialaxis=dict(visible=True, range=[0, df["model6_total"].max() * 1.2])),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
        height=550,
    )
    return fig


def create_summary_dashboard():
    """まとめ・予測比較HTMLダッシュボードを生成"""
    print("予測データ読み込み中...")
    df = load_data()

    if df.empty or "model6_total" not in df.columns:
        print("統合予測データがありません。先に predict_seats.py を実行してください。")
        return

    # 統計
    m6_top = df.loc[df["model6_total"].idxmax()]
    m6_top_party = m6_top["party_name"]
    m6_top_seats = int(m6_top["model6_total"])

    m4_top = df.loc[df["model4_total"].idxmax()]
    m5_top = df.loc[df["model5_total"].idxmax()]

    ruling_m6 = sum(
        int(df.loc[df["party_name"] == p, "model6_total"].iloc[0])
        for p in ["自由民主党", "日本維新の会"] if p in df["party_name"].values
    )

    # モデル間の最大差異（ベースライン含む）
    model_cols = [_get_model_col(m) for m in ALL_MODEL_LABELS.keys() if _get_model_col(m) in df.columns]
    max_range = int((df[model_cols].max(axis=1) - df[model_cols].min(axis=1)).max())

    print("グラフ生成中...")
    figs = {
        "all_comparison": build_all_models_comparison(df),
        "yt_vs_news": build_yt_vs_news_vs_combined(df),
        "combined_breakdown": build_combined_breakdown(df),
        "divergence": build_model_divergence(df),
        "coalition": build_coalition_combined(df),
        "radar": build_data_source_radar(df),
    }

    for fig in figs.values():
        fig.update_layout(
            template="plotly_white",
            font=dict(family="Hiragino Sans, Noto Sans JP, sans-serif"),
            title_font_size=18,
            hoverlabel=dict(font_size=13),
        )

    chart_divs = []
    for key, fig in figs.items():
        html = fig.to_html(full_html=False, include_plotlyjs=False)
        chart_divs.append(f'<div class="chart-container" id="chart-{key}">{html}</div>')

    # 世論調査ベースライン統計
    bl_top = df.loc[df["polling_baseline"].idxmax()]
    bl_top_party = bl_top["party_name"]
    bl_top_seats = int(bl_top["polling_baseline"])

    # モデル概要テーブル
    model_table_rows = ""
    for model_key, label in ALL_MODEL_LABELS.items():
        col = _get_model_col(model_key)
        if col not in df.columns:
            continue
        top_row = df.loc[df[col].idxmax()]
        top_p = top_row["party_name"]
        top_s = int(top_row[col])
        if model_key == "baseline":
            source_tag = "世論調査"
        elif model_key in ["model1", "model2", "model3", "model4"]:
            source_tag = "YouTube"
        elif model_key == "model5":
            source_tag = "ニュース"
        else:
            source_tag = "統合"
        color = ALL_MODEL_COLORS[model_key]
        model_table_rows += (
            f'<tr>'
            f'<td><span style="color:{color};">&#9632;</span> {label}</td>'
            f'<td>{source_tag}</td>'
            f'<td><strong>{top_p} {top_s}議席</strong></td>'
            f'</tr>'
        )

    html_template = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>第51回衆院選 まとめ・予測比較</title>
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
    background: linear-gradient(135deg, #1a1a2e, #e94560);
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
  .model-table {{
    width: 100%; border-collapse: collapse;
    margin: 1rem 0; font-size: 0.9rem;
  }}
  .model-table th, .model-table td {{
    padding: 0.6rem 1rem; text-align: left;
    border-bottom: 1px solid #eee;
  }}
  .model-table th {{ background: #f8f9fa; font-weight: 600; }}
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
  <a href="summary_dashboard.html" class="active">まとめ・予測比較</a>
  <a href="map_dashboard.html">選挙区マップ</a>
</div>

<div class="header">
  <h1>第51回衆院選 まとめ・予測比較ダッシュボード</h1>
  <p>YouTube分析 × ニュース記事分析 — 全6モデルの予測を横断比較</p>
</div>

<div class="stats-grid">
  <div class="stat-card" style="border-top: 3px solid #888888;">
    <div class="stat-value">{bl_top_seats}</div>
    <div class="stat-label">世論調査BL1位: {bl_top_party}</div>
  </div>
  <div class="stat-card" style="border-top: 3px solid #1a1a2e;">
    <div class="stat-value">{m6_top_seats}</div>
    <div class="stat-label">統合予測1位: {m6_top_party}</div>
  </div>
  <div class="stat-card" style="border-top: 3px solid #9B59B6;">
    <div class="stat-value">{int(m4_top['model4_total'])}</div>
    <div class="stat-label">YT予測1位: {m4_top['party_name']}</div>
  </div>
  <div class="stat-card" style="border-top: 3px solid #FF8C00;">
    <div class="stat-value">{int(m5_top['model5_total'])}</div>
    <div class="stat-label">ニュース予測1位: {m5_top['party_name']}</div>
  </div>
  <div class="stat-card" style="border-top: 3px solid var(--highlight);">
    <div class="stat-value">{ruling_m6}</div>
    <div class="stat-label">与党連合 統合予測</div>
  </div>
  <div class="stat-card">
    <div class="stat-value">{max_range}</div>
    <div class="stat-label">モデル間最大差異</div>
  </div>
</div>

<div class="dashboard">
  <div class="info-box">
    <p>
      <strong>世論調査ベースライン + 6つの予測モデル:</strong> 世論調査に基づく議席配分をベースラインとし、
      YouTube分析・ニュース記事分析それぞれ独立したモデルに加え、両方を統合したアンサンブル予測を行っています。
    </p>
    <table class="model-table">
      <tr><th>モデル</th><th>データソース</th><th>第一党予測</th></tr>
      {model_table_rows}
    </table>
  </div>

  <h2 class="section-title">全モデル横断比較</h2>
  {chart_divs[0]}

  <h2 class="section-title">世論調査ベースライン vs YouTube vs ニュース vs 統合</h2>
  <div class="info-box" style="border-left-color: #9B59B6;">
    <p>
      <span style="color:#888888;">&#9632;</span> <strong>世論調査ベースライン</strong>:
      世論調査の支持率をもとにした議席配分（キューブ法則＋ドント方式を適用しない単純配分）<br>
      <span style="color:#9B59B6;">&#9632;</span> <strong>YouTubeアンサンブル (M4)</strong>:
      エンゲージメント・感情分析・世論調査+YT勢いの加重平均（M1:20% + M2:25% + M3:55%）<br>
      <span style="color:#FF8C00;">&#9632;</span> <strong>ニュース記事モデル (M5)</strong>:
      世論調査(55%) + メディア報道量(30%) + 報道トーン(15%)<br>
      <span style="color:#1a1a2e;">&#9632;</span> <strong>統合アンサンブル (M6)</strong>:
      YouTube(45%) + ニュース(55%) の最終予測
    </p>
  </div>
  {chart_divs[1]}
  {chart_divs[2]}

  <h2 class="section-title">モデル間の予測差異</h2>
  {chart_divs[3]}
  {chart_divs[5]}

  <h2 class="section-title">連立ブロック分析</h2>
  {chart_divs[4]}
</div>

<div class="footer">
  <p>第51回衆議院議員総選挙 統合分析プロジェクト</p>
  <p>※ サンプルデータによるデモ表示です。実データではYouTube Data API v3 + ニュースAPI/スクレイピングの利用が必要です。</p>
</div>
</body>
</html>"""

    output_path = OUTPUT_DIR / "summary_dashboard.html"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_template, encoding="utf-8")
    print(f"\nまとめダッシュボード生成完了!")
    print(f"  出力先: {output_path}")
    return output_path


if __name__ == "__main__":
    create_summary_dashboard()
