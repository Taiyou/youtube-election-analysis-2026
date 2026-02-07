"""
ニュース記事分析ダッシュボード生成スクリプト
インターネット上のニュース記事データを分析し、別ページのHTMLダッシュボードを生成する
"""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import sys
sys.path.insert(0, str(Path(__file__).parent))
from config import PARTY_COLORS

DATA_DIR = Path(__file__).parent.parent / "data"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUT_DIR = Path(__file__).parent.parent / "output"

SOURCE_TYPE_COLORS = {
    "全国紙": "#1E90FF",
    "公共放送": "#2ECC71",
    "経済紙": "#FF8C00",
    "通信社": "#9B59B6",
    "地方紙": "#E67E22",
    "ポータル": "#E74C3C",
    "経済メディア": "#1ABC9C",
    "Webメディア": "#F39C12",
}


def load_news_data():
    """ニュース関連データを読み込む"""
    data = {}

    articles_path = PROCESSED_DIR / "news_articles.csv"
    if articles_path.exists():
        data["articles"] = pd.read_csv(articles_path)
    else:
        data["articles"] = pd.DataFrame()

    polling_path = PROCESSED_DIR / "news_polling.csv"
    if polling_path.exists():
        data["polling"] = pd.read_csv(polling_path)
    else:
        data["polling"] = pd.DataFrame()

    daily_path = PROCESSED_DIR / "news_daily_coverage.csv"
    if daily_path.exists():
        data["daily_coverage"] = pd.read_csv(daily_path)
    else:
        data["daily_coverage"] = pd.DataFrame()

    return data


def build_daily_coverage(data):
    """日別ニュース報道量の推移"""
    df = data["daily_coverage"]
    if df.empty:
        return go.Figure().update_layout(title="日別報道データなし")

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Bar(
        x=df["date"], y=df["article_count"],
        name="記事数", marker_color="#4169E1", opacity=0.7,
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        x=df["date"], y=df["total_page_views"],
        name="総PV数", line=dict(color="#FF6347", width=2.5),
        fill="tonexty", fillcolor="rgba(255,99,71,0.1)",
    ), secondary_y=True)

    for date_str, color, label in [("2026-01-27", "green", "公示日 (1/27)"),
                                    ("2026-02-08", "red", "投票日 (2/8)")]:
        fig.add_shape(type="line", x0=date_str, x1=date_str, y0=0, y1=1,
                      yref="paper", line=dict(color=color, width=1.5, dash="dash"))
        fig.add_annotation(x=date_str, y=1, yref="paper", text=label,
                           showarrow=False, font=dict(color=color, size=11), yshift=10)

    fig.update_layout(
        title="選挙関連ニュース記事 日別報道量推移",
        xaxis_title="日付", hovermode="x unified", height=450,
    )
    fig.update_yaxes(title_text="記事数", secondary_y=False)
    fig.update_yaxes(title_text="総PV数", secondary_y=True)
    return fig


def build_source_breakdown(data):
    """メディア別の記事数と影響力"""
    df = data["articles"]
    if df.empty:
        return go.Figure().update_layout(title="記事データなし")

    source_stats = df.groupby(["source", "source_type"]).agg(
        article_count=("article_id", "count"),
        total_pv=("page_views", "sum"),
        avg_tone=("tone", "mean"),
        total_shares=("share_count", "sum"),
    ).reset_index().sort_values("total_pv", ascending=True)

    colors = [SOURCE_TYPE_COLORS.get(t, "#888") for t in source_stats["source_type"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=source_stats["source"], x=source_stats["total_pv"],
        orientation="h", marker_color=colors,
        text=[f"{v/10000:.0f}万PV" for v in source_stats["total_pv"]],
        textposition="outside",
        hovertemplate=(
            "<b>%{y}</b><br>"
            "総PV: %{x:,.0f}<br>"
            "<extra></extra>"
        ),
    ))

    fig.update_layout(
        title="メディア別 選挙記事 総アクセス数",
        xaxis_title="総ページビュー数",
        height=max(500, len(source_stats) * 35),
        margin=dict(l=200),
    )
    return fig


def build_source_tone(data):
    """メディア別の報道トーン分析"""
    df = data["articles"]
    if df.empty:
        return go.Figure().update_layout(title="記事データなし")

    source_stats = df.groupby("source").agg(
        avg_tone=("tone", "mean"),
        article_count=("article_id", "count"),
        std_tone=("tone", "std"),
    ).reset_index().sort_values("avg_tone")

    colors = ["#E74C3C" if t < -0.1 else "#2ECC71" if t > 0.1 else "#95A5A6"
              for t in source_stats["avg_tone"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=source_stats["source"], x=source_stats["avg_tone"],
        orientation="h", marker_color=colors,
        text=[f"{v:+.2f}" for v in source_stats["avg_tone"]],
        textposition="outside",
        error_x=dict(type="data", array=source_stats["std_tone"].fillna(0), visible=True),
        hovertemplate=(
            "<b>%{y}</b><br>"
            "平均トーン: %{x:+.3f}<br>"
            "<extra></extra>"
        ),
    ))

    fig.add_shape(type="line", x0=0, x1=0, y0=-0.5, y1=len(source_stats) - 0.5,
                  line=dict(color="gray", width=1, dash="dot"))

    fig.update_layout(
        title="メディア別 報道トーン（-1: 批判的 ← 0: 中立 → +1: 肯定的）",
        xaxis_title="平均報道トーン",
        xaxis=dict(range=[-0.8, 0.8]),
        height=max(450, len(source_stats) * 30),
        margin=dict(l=200),
    )
    return fig


def build_party_coverage(data):
    """政党別のニュース報道量（言及回数 × PV）"""
    df = data["articles"]
    if df.empty:
        return go.Figure().update_layout(title="記事データなし")

    # mentioned_parties列を展開
    party_mentions = []
    for _, row in df.iterrows():
        parties = str(row["mentioned_parties"]).split("|")
        for party in parties:
            if party and party != "nan":
                party_mentions.append({
                    "party_name": party,
                    "page_views": row["page_views"],
                    "tone": row["tone"],
                    "source_type": row["source_type"],
                })

    pm_df = pd.DataFrame(party_mentions)
    party_stats = pm_df.groupby("party_name").agg(
        mention_count=("party_name", "count"),
        total_pv=("page_views", "sum"),
        avg_tone=("tone", "mean"),
    ).reset_index().sort_values("total_pv", ascending=True)

    colors = [PARTY_COLORS.get(p, "#888") for p in party_stats["party_name"]]

    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=("政党別 ニュース言及回数", "政党別 ニュース記事PV"),
                        horizontal_spacing=0.15)

    fig.add_trace(go.Bar(
        y=party_stats["party_name"], x=party_stats["mention_count"],
        orientation="h", marker_color=colors,
        text=party_stats["mention_count"], textposition="outside",
        showlegend=False,
    ), row=1, col=1)

    fig.add_trace(go.Bar(
        y=party_stats["party_name"], x=party_stats["total_pv"],
        orientation="h", marker_color=colors,
        text=[f"{v/10000:.0f}万" for v in party_stats["total_pv"]],
        textposition="outside", showlegend=False,
    ), row=1, col=2)

    fig.update_layout(title="政党別 ニュースメディアでの報道量", height=500)
    return fig


def build_party_tone_analysis(data):
    """政党別の報道トーン分析"""
    df = data["articles"]
    if df.empty:
        return go.Figure().update_layout(title="記事データなし")

    party_mentions = []
    for _, row in df.iterrows():
        parties = str(row["mentioned_parties"]).split("|")
        for party in parties:
            if party and party != "nan":
                party_mentions.append({
                    "party_name": party,
                    "tone": row["tone"],
                    "source_type": row["source_type"],
                })

    pm_df = pd.DataFrame(party_mentions)

    # メディアタイプ別 × 政党別の平均トーン
    pivot = pm_df.groupby(["party_name", "source_type"])["tone"].mean().reset_index()
    source_types = sorted(pivot["source_type"].unique())
    parties = sorted(pivot["party_name"].unique(),
                     key=lambda p: pm_df[pm_df["party_name"] == p]["tone"].mean())

    fig = go.Figure()
    for stype in source_types:
        sub = pivot[pivot["source_type"] == stype]
        vals = [float(sub.loc[sub["party_name"] == p, "tone"].iloc[0])
                if p in sub["party_name"].values else 0
                for p in parties]
        fig.add_trace(go.Bar(
            y=parties, x=vals, name=stype, orientation="h",
            marker_color=SOURCE_TYPE_COLORS.get(stype, "#888"),
        ))

    fig.add_shape(type="line", x0=0, x1=0, y0=-0.5, y1=len(parties) - 0.5,
                  line=dict(color="gray", width=1, dash="dot"))

    fig.update_layout(
        title="政党別 × メディアタイプ別 報道トーン",
        xaxis_title="平均トーン（-: 批判的 / +: 肯定的）",
        barmode="group",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        height=550,
    )
    return fig


def build_polling_trends(data):
    """世論調査の支持率推移"""
    df = data["polling"]
    if df.empty:
        return go.Figure().update_layout(title="世論調査データなし")

    df["survey_date"] = pd.to_datetime(df["survey_date"])

    # 各日付・政党で平均を取る（複数社の平均）
    avg_polls = df.groupby(["survey_date", "party_name"])["support_rate"].mean().reset_index()

    # 主要政党のみ表示（支持なし除外）
    main_parties = [p for p in avg_polls["party_name"].unique() if p != "支持なし"]

    fig = go.Figure()
    for party in main_parties:
        sub = avg_polls[avg_polls["party_name"] == party].sort_values("survey_date")
        fig.add_trace(go.Scatter(
            x=sub["survey_date"], y=sub["support_rate"],
            name=party, mode="lines+markers",
            line=dict(color=PARTY_COLORS.get(party, "#888"), width=2.5),
            marker=dict(size=8),
            hovertemplate=f"<b>{party}</b><br>"
                          "日付: %{x|%m/%d}<br>"
                          "支持率: %{y:.1f}%<br>"
                          "<extra></extra>",
        ))

    fig.add_shape(type="line", x0="2026-01-27", x1="2026-01-27", y0=0, y1=1,
                  yref="paper", line=dict(color="green", width=1.5, dash="dash"))
    fig.add_annotation(x="2026-01-27", y=1, yref="paper", text="公示日",
                       showarrow=False, font=dict(color="green", size=11), yshift=10)

    fig.update_layout(
        title="世論調査 政党支持率推移（各社平均）",
        xaxis_title="調査日", yaxis_title="支持率 (%)",
        hovermode="x unified", height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    )
    return fig


def build_polling_comparison(data):
    """メディア各社の世論調査比較（最新）"""
    df = data["polling"]
    if df.empty:
        return go.Figure().update_layout(title="世論調査データなし")

    df["survey_date"] = pd.to_datetime(df["survey_date"])

    # 最新の調査日のデータ
    latest_date = df["survey_date"].max()
    latest = df[df["survey_date"] == latest_date]

    main_parties = [p for p in latest["party_name"].unique() if p != "支持なし"]
    sources = latest["source"].unique()

    fig = go.Figure()
    source_colors = ["#4169E1", "#2ECC71", "#E74C3C", "#9B59B6", "#FF8C00", "#1ABC9C"]

    for i, source in enumerate(sources):
        sub = latest[latest["source"] == source]
        vals = [float(sub.loc[sub["party_name"] == p, "support_rate"].iloc[0])
                if p in sub["party_name"].values else 0
                for p in main_parties]
        fig.add_trace(go.Bar(
            x=main_parties, y=vals, name=source,
            marker_color=source_colors[i % len(source_colors)],
            text=[f"{v:.1f}%" for v in vals], textposition="outside", textfont_size=9,
        ))

    fig.update_layout(
        title=f"世論調査 各社比較（最新: {latest_date.strftime('%Y/%m/%d')}）",
        yaxis_title="支持率 (%)", barmode="group",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        height=500,
    )
    return fig


def build_news_vs_youtube(data):
    """ニュース報道量 vs YouTube再生回数の比較"""
    df = data["articles"]
    if df.empty:
        return go.Figure().update_layout(title="記事データなし")

    # ニュースの政党別PV
    party_mentions = []
    for _, row in df.iterrows():
        parties = str(row["mentioned_parties"]).split("|")
        for party in parties:
            if party and party != "nan":
                party_mentions.append({
                    "party_name": party,
                    "page_views": row["page_views"],
                })
    pm_df = pd.DataFrame(party_mentions)
    news_stats = pm_df.groupby("party_name")["page_views"].sum().reset_index()
    news_stats.columns = ["party_name", "news_pv"]

    # YouTubeのデータがあれば比較
    yt_path = PROCESSED_DIR / "party_video_stats.csv"
    if yt_path.exists():
        yt_df = pd.read_csv(yt_path)
        merged = news_stats.merge(yt_df[["party_name", "total_views"]], on="party_name", how="outer").fillna(0)
    else:
        merged = news_stats.copy()
        merged["total_views"] = 0

    merged = merged.sort_values("news_pv", ascending=True)
    colors = [PARTY_COLORS.get(p, "#888") for p in merged["party_name"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=merged["party_name"], x=merged["news_pv"],
        name="ニュース記事PV", orientation="h",
        marker_color="#4169E1",
        text=[f"{v/10000:.0f}万" for v in merged["news_pv"]],
        textposition="inside",
    ))
    fig.add_trace(go.Bar(
        y=merged["party_name"], x=merged["total_views"],
        name="YouTube再生回数", orientation="h",
        marker_color="#FF6347",
        text=[f"{v/10000:.0f}万" for v in merged["total_views"]],
        textposition="inside",
    ))

    fig.update_layout(
        title="政党別 ニュース記事PV vs YouTube再生回数 比較",
        xaxis_title="数値", barmode="group",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        height=500,
    )
    return fig


def build_coverage_tone_scatter(data):
    """報道量 vs トーンの散布図"""
    df = data["articles"]
    if df.empty:
        return go.Figure().update_layout(title="記事データなし")

    party_mentions = []
    for _, row in df.iterrows():
        parties = str(row["mentioned_parties"]).split("|")
        for party in parties:
            if party and party != "nan":
                party_mentions.append({
                    "party_name": party,
                    "page_views": row["page_views"],
                    "tone": row["tone"],
                })
    pm_df = pd.DataFrame(party_mentions)
    stats = pm_df.groupby("party_name").agg(
        mention_count=("party_name", "count"),
        total_pv=("page_views", "sum"),
        avg_tone=("tone", "mean"),
    ).reset_index()

    fig = go.Figure()
    for _, row in stats.iterrows():
        color = PARTY_COLORS.get(row["party_name"], "#888")
        fig.add_trace(go.Scatter(
            x=[row["mention_count"]], y=[row["avg_tone"]],
            mode="markers+text",
            name=row["party_name"],
            text=[row["party_name"]],
            textposition="top center", textfont_size=11,
            marker=dict(
                size=max(15, row["total_pv"] / stats["total_pv"].max() * 60),
                color=color, opacity=0.8,
                line=dict(width=1, color="white"),
            ),
            hovertemplate=(
                f"<b>{row['party_name']}</b><br>"
                f"言及回数: {row['mention_count']}<br>"
                f"平均トーン: {row['avg_tone']:+.3f}<br>"
                f"総PV: {row['total_pv']:,}<br>"
                "<extra></extra>"
            ),
        ))

    fig.add_shape(type="line", x0=0, x1=stats["mention_count"].max() * 1.1,
                  y0=0, y1=0, line=dict(color="gray", width=1, dash="dot"))

    fig.update_layout(
        title="政党別 報道量 vs 報道トーン（バブルサイズ＝総PV）",
        xaxis_title="ニュース言及回数",
        yaxis_title="平均報道トーン（-: 批判的 / +: 肯定的）",
        showlegend=False, height=550,
    )
    return fig


def build_news_prediction(data):
    """ニュース記事モデル(Model 5)の議席予測 + 世論調査ベースライン比較"""
    pred_path = PROCESSED_DIR / "seat_predictions.csv"
    if not pred_path.exists():
        return go.Figure().update_layout(title="予測データなし")

    df = pd.read_csv(pred_path)
    if "model5_total" not in df.columns:
        return go.Figure().update_layout(title="ニュース予測モデルなし")

    df = df.sort_values("model5_total", ascending=True)

    fig = go.Figure()

    # 世論調査ベースライン（灰色の点線マーカー）
    if "polling_baseline" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["polling_baseline"], y=df["party_name"],
            mode="markers+text", name="世論調査ベースライン",
            marker=dict(color="#888888", size=12, symbol="diamond",
                        line=dict(width=1, color="white")),
            text=df["polling_baseline"].astype(int).astype(str),
            textposition="middle right", textfont=dict(size=9, color="#888"),
        ))

    # Model 5 stacked bar
    fig.add_trace(go.Bar(
        y=df["party_name"], x=df["model5_smd"],
        name="ニュースM5: 小選挙区", orientation="h",
        marker_color="#4169E1",
        text=df["model5_smd"], textposition="inside",
    ))
    fig.add_trace(go.Bar(
        y=df["party_name"], x=df["model5_pr"],
        name="ニュースM5: 比例代表", orientation="h",
        marker_color="#FF6347",
        text=df["model5_pr"], textposition="inside",
    ))

    # 過半数ライン
    fig.add_shape(type="line", x0=233, x1=233, y0=-0.5, y1=len(df) - 0.5,
                  line=dict(color="orange", width=2, dash="dot"))
    fig.add_annotation(x=233, y=len(df) - 0.5, text="過半数(233)",
                       showarrow=False, font=dict(color="orange", size=10), xshift=-5, yshift=15)

    fig.update_layout(
        title="ニュース記事モデル 議席予測 vs 世論調査ベースライン（◆＝ベースライン）",
        xaxis_title="議席数", barmode="stack",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        height=500,
    )
    return fig


def generate_news_stats(data):
    """ニュース分析のサマリー統計"""
    articles = data["articles"]
    polling = data["polling"]

    total_articles = len(articles) if not articles.empty else 0
    total_pv = int(articles["page_views"].sum()) if not articles.empty else 0
    n_sources = articles["source"].nunique() if not articles.empty else 0
    avg_tone = float(articles["tone"].mean()) if not articles.empty else 0

    # 最新世論調査の第一党
    top_party = ""
    top_rate = 0
    if not polling.empty:
        polling["survey_date"] = pd.to_datetime(polling["survey_date"])
        latest = polling[polling["survey_date"] == polling["survey_date"].max()]
        latest_avg = latest[latest["party_name"] != "支持なし"].groupby("party_name")["support_rate"].mean()
        if not latest_avg.empty:
            top_party = latest_avg.idxmax()
            top_rate = latest_avg.max()

    # ニュースモデル予測の第一党
    news_pred_party = ""
    news_pred_seats = 0
    pred_path = PROCESSED_DIR / "seat_predictions.csv"
    if pred_path.exists():
        pred_df = pd.read_csv(pred_path)
        if "model5_total" in pred_df.columns:
            top_row = pred_df.loc[pred_df["model5_total"].idxmax()]
            news_pred_party = top_row["party_name"]
            news_pred_seats = int(top_row["model5_total"])

    return {
        "total_articles": total_articles,
        "total_pv": total_pv,
        "n_sources": n_sources,
        "avg_tone": avg_tone,
        "top_party": top_party,
        "top_rate": top_rate,
        "news_pred_party": news_pred_party,
        "news_pred_seats": news_pred_seats,
    }


def create_news_dashboard():
    """ニュース分析HTMLダッシュボード（別ページ）を生成"""
    print("ニュースデータ読み込み中...")
    data = load_news_data()
    stats = generate_news_stats(data)

    print("ニュースグラフ生成中...")
    figs = {}
    figs["daily_coverage"] = build_daily_coverage(data)
    figs["source_breakdown"] = build_source_breakdown(data)
    figs["source_tone"] = build_source_tone(data)
    figs["party_coverage"] = build_party_coverage(data)
    figs["party_tone"] = build_party_tone_analysis(data)
    figs["polling_trends"] = build_polling_trends(data)
    figs["polling_comparison"] = build_polling_comparison(data)
    figs["news_vs_youtube"] = build_news_vs_youtube(data)
    figs["coverage_tone_scatter"] = build_coverage_tone_scatter(data)
    figs["news_prediction"] = build_news_prediction(data)

    # 共通レイアウト設定
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

    tone_label = "中立" if abs(stats["avg_tone"]) < 0.1 else ("やや肯定的" if stats["avg_tone"] > 0 else "やや批判的")

    html_template = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>第51回衆院選 ニュース記事分析</title>
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
    background: linear-gradient(135deg, #2c3e50, #3498db);
    color: white;
    padding: 2rem 2rem 1.5rem;
    text-align: center;
  }}
  .header h1 {{
    font-size: 1.8rem;
    margin-bottom: 0.5rem;
  }}
  .header p {{
    font-size: 0.95rem;
    opacity: 0.85;
  }}
  .nav-bar {{
    background: #2c3e50;
    padding: 0.8rem 2rem;
    text-align: center;
  }}
  .nav-bar a {{
    color: white;
    text-decoration: none;
    padding: 0.5rem 1.5rem;
    border-radius: 6px;
    margin: 0 0.3rem;
    font-size: 0.9rem;
    transition: background 0.2s;
  }}
  .nav-bar a:hover {{
    background: rgba(255,255,255,0.15);
  }}
  .nav-bar a.active {{
    background: #3498db;
  }}
  .stats-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 1rem;
    padding: 1.5rem 2rem;
    max-width: 1400px;
    margin: -1.5rem auto 0;
  }}
  .stat-card {{
    background: var(--card);
    border-radius: 12px;
    padding: 1.2rem;
    text-align: center;
    box-shadow: 0 2px 12px rgba(0,0,0,0.08);
    transition: transform 0.2s;
  }}
  .stat-card:hover {{
    transform: translateY(-2px);
    box-shadow: 0 4px 20px rgba(0,0,0,0.12);
  }}
  .stat-value {{
    font-size: 1.8rem;
    font-weight: 700;
    color: var(--accent);
  }}
  .stat-label {{
    font-size: 0.85rem;
    color: #666;
    margin-top: 0.3rem;
  }}
  .dashboard {{
    max-width: 1400px;
    margin: 0 auto;
    padding: 1rem 2rem 3rem;
  }}
  .section-title {{
    font-size: 1.3rem;
    font-weight: 700;
    color: var(--primary);
    margin: 2rem 0 1rem;
    padding-left: 0.8rem;
    border-left: 4px solid #3498db;
  }}
  .chart-container {{
    background: var(--card);
    border-radius: 12px;
    padding: 1rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
  }}
  .info-box {{
    background: var(--card);
    border-radius: 12px;
    padding: 1.2rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    border-left: 4px solid #3498db;
  }}
  .info-box p {{
    font-size: 0.9rem;
    color: #555;
    line-height: 1.6;
  }}
  .footer {{
    text-align: center;
    padding: 2rem;
    color: #999;
    font-size: 0.85rem;
  }}
  @media (max-width: 900px) {{
    .stats-grid {{
      grid-template-columns: repeat(2, 1fr);
    }}
  }}
</style>
</head>
<body>
<div class="nav-bar">
  <a href="election_dashboard.html">YouTube分析</a>
  <a href="news_dashboard.html" class="active">ニュース記事分析</a>
  <a href="summary_dashboard.html">まとめ・予測比較</a>
  <a href="map_dashboard.html">選挙区マップ</a>
</div>

<div class="header">
  <h1>第51回衆院選 ニュース記事分析ダッシュボード</h1>
  <p>主要メディア{stats['n_sources']}社のオンライン記事 + 世論調査データを分析</p>
</div>

<div class="stats-grid">
  <div class="stat-card">
    <div class="stat-value">{stats['total_articles']}</div>
    <div class="stat-label">分析記事数</div>
  </div>
  <div class="stat-card">
    <div class="stat-value">{stats['total_pv'] // 10000}万</div>
    <div class="stat-label">総ページビュー</div>
  </div>
  <div class="stat-card">
    <div class="stat-value">{stats['n_sources']}</div>
    <div class="stat-label">メディアソース数</div>
  </div>
  <div class="stat-card">
    <div class="stat-value">{tone_label}</div>
    <div class="stat-label">全体報道トーン</div>
  </div>
  <div class="stat-card" style="border-top: 3px solid #3498db;">
    <div class="stat-value">{stats['top_rate']:.1f}%</div>
    <div class="stat-label">最新支持率1位: {stats['top_party']}</div>
  </div>
  <div class="stat-card" style="border-top: 3px solid #e94560;">
    <div class="stat-value">{stats['news_pred_seats']}</div>
    <div class="stat-label">ニュース予測1位: {stats['news_pred_party']}</div>
  </div>
</div>

<div class="dashboard">
  <div class="info-box">
    <p>
      <strong>ニュース記事分析について:</strong>
      NHK、朝日新聞、読売新聞、毎日新聞、産経新聞、日本経済新聞などの主要メディアに加え、
      Yahoo!ニュース、東洋経済オンライン、文春オンラインなどのWebメディアの選挙関連記事を分析しています。<br>
      <strong>報道トーン</strong>は記事の論調を数値化したもので、-1（批判的）〜 0（中立）〜 +1（肯定的）で表現しています。
      YouTubeとニュースメディアでは有権者へのリーチ層が異なるため、両方の分析を比較することで選挙の全体像が見えてきます。
    </p>
  </div>

  <h2 class="section-title">報道量の推移</h2>
  {chart_divs[0]}

  <h2 class="section-title">メディア別分析</h2>
  {chart_divs[1]}
  {chart_divs[2]}

  <h2 class="section-title">政党別報道分析</h2>
  {chart_divs[3]}
  {chart_divs[4]}
  {chart_divs[8]}

  <h2 class="section-title">世論調査</h2>
  {chart_divs[5]}
  {chart_divs[6]}

  <h2 class="section-title">ニュース × YouTube クロス分析</h2>
  {chart_divs[7]}

  <h2 class="section-title">ニュース記事ベース議席予測</h2>
  <div class="info-box" style="border-left-color: #e94560;">
    <p>
      <strong>ニュース記事モデル（Model 5）:</strong>
      世論調査データ（55%）、メディア報道量（30%）、報道トーン（15%）を組み合わせて議席数を予測します。
      小選挙区は歴史的なSMD比率で配分。YouTube分析とは独立したモデルです。<br>
      <em>※ まとめページでYouTubeモデルとの比較・統合予測が確認できます。</em>
    </p>
  </div>
  {chart_divs[9]}
</div>

<div class="footer">
  <p>第51回衆議院議員総選挙 ニュース記事分析プロジェクト</p>
  <p>※ サンプルデータによるデモ表示です。実データの取得にはWebスクレイピングまたはニュースAPIの利用が必要です。</p>
</div>
</body>
</html>"""

    output_path = OUTPUT_DIR / "news_dashboard.html"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_template, encoding="utf-8")
    print(f"\nニュースダッシュボード生成完了!")
    print(f"  出力先: {output_path}")
    return output_path


if __name__ == "__main__":
    create_news_dashboard()
