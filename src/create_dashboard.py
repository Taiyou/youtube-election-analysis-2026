"""
インタラクティブHTMLダッシュボード生成スクリプト
Plotlyを使用して選挙分析結果を1つのHTMLファイルにまとめる
"""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

DATA_DIR = Path(__file__).parent.parent / "data"
PROCESSED_DIR = DATA_DIR / "processed"
RAW_DIR = DATA_DIR / "raw"
OUTPUT_DIR = Path(__file__).parent.parent / "output"

PARTY_COLORS = {
    "自由民主党": "#E3242B",
    "日本維新の会": "#3CB371",
    "立憲民主党": "#1E90FF",
    "国民民主党": "#FF8C00",
    "日本共産党": "#DC143C",
    "れいわ新選組": "#FF69B4",
    "参政党": "#DAA520",
}

SENTIMENT_COLORS = {
    "positive": "#2ECC71",
    "neutral": "#95A5A6",
    "negative": "#E74C3C",
}

SENTIMENT_LABELS = {
    "positive": "ポジティブ",
    "neutral": "ニュートラル",
    "negative": "ネガティブ",
}


def load_data():
    """全データを読み込む"""
    data = {}
    data["daily_counts"] = pd.read_csv(PROCESSED_DIR / "daily_video_counts.csv")
    data["daily_views"] = pd.read_csv(PROCESSED_DIR / "daily_views.csv")
    data["issue_stats"] = pd.read_csv(PROCESSED_DIR / "issue_stats.csv")
    data["channels"] = pd.read_csv(PROCESSED_DIR / "channel_analysis.csv")
    data["party_stats"] = pd.read_csv(PROCESSED_DIR / "party_video_stats.csv")
    data["sentiment"] = pd.read_csv(PROCESSED_DIR / "sentiment_counts.csv")

    raw_files = sorted(RAW_DIR.glob("video_details_*.csv"), reverse=True)
    if raw_files:
        data["videos"] = pd.read_csv(raw_files[0])
    else:
        data["videos"] = pd.DataFrame()

    raw_comments = sorted(RAW_DIR.glob("comments_*.csv"), reverse=True)
    if raw_comments:
        data["comments"] = pd.read_csv(raw_comments[0])
    else:
        data["comments"] = pd.DataFrame()

    return data


def build_daily_trend(data):
    """日別動画投稿数の推移"""
    df = data["daily_counts"].copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    if len(df) >= 3:
        df["ma3"] = df["video_count"].rolling(3, min_periods=1).mean()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["date"], y=df["video_count"],
        name="投稿数", marker_color="#4169E1", opacity=0.7,
    ))
    if "ma3" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["ma3"],
            name="3日移動平均", line=dict(color="#DC143C", width=2.5),
        ))

    # 公示日と投票日
    for date_str, color, label in [("2026-01-27", "green", "公示日 (1/27)"),
                                    ("2026-02-08", "red", "投票日 (2/8)")]:
        fig.add_shape(type="line", x0=date_str, x1=date_str, y0=0, y1=1,
                      yref="paper", line=dict(color=color, width=1.5, dash="dash"))
        fig.add_annotation(x=date_str, y=1, yref="paper", text=label,
                           showarrow=False, font=dict(color=color, size=11),
                           yshift=10)

    fig.update_layout(
        title="選挙関連YouTube動画 日別投稿数推移",
        xaxis_title="日付", yaxis_title="動画数",
        hovermode="x unified",
    )
    return fig


def build_daily_views(data):
    """日別再生回数の推移"""
    df = data["daily_views"].copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    df["cumulative"] = df["view_count"].cumsum()

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Bar(
        x=df["date"], y=df["view_count"],
        name="日別再生回数", marker_color="#4169E1", opacity=0.5,
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        x=df["date"], y=df["cumulative"],
        name="累計再生回数", line=dict(color="#FF6347", width=2.5),
        fill="tonexty", fillcolor="rgba(255,99,71,0.1)",
    ), secondary_y=True)

    for date_str, color, label in [("2026-01-27", "green", "公示日"),
                                    ("2026-02-08", "red", "投票日")]:
        fig.add_shape(type="line", x0=date_str, x1=date_str, y0=0, y1=1,
                      yref="paper", line=dict(color=color, width=1.5, dash="dash"))
        fig.add_annotation(x=date_str, y=1, yref="paper", text=label,
                           showarrow=False, font=dict(color=color, size=11),
                           yshift=10)

    fig.update_layout(
        title="選挙関連動画 再生回数推移",
        xaxis_title="日付", hovermode="x unified",
    )
    fig.update_yaxes(title_text="日別再生回数", secondary_y=False)
    fig.update_yaxes(title_text="累計再生回数", secondary_y=True)
    return fig


def build_issue_comparison(data):
    """争点別の注目度比較"""
    df = data["issue_stats"].sort_values("total_views", ascending=True)

    fig = make_subplots(rows=1, cols=2, subplot_titles=("争点別 動画数", "争点別 総再生回数"),
                        horizontal_spacing=0.15)

    colors = [f"hsl({i * 360 // len(df)}, 70%, 55%)" for i in range(len(df))]

    fig.add_trace(go.Bar(
        y=df["issue"], x=df["video_count"],
        orientation="h", marker_color=colors,
        text=df["video_count"], textposition="outside",
        showlegend=False,
    ), row=1, col=1)

    fig.add_trace(go.Bar(
        y=df["issue"], x=df["total_views"],
        orientation="h", marker_color=colors,
        text=[f"{v/10000:.1f}万" for v in df["total_views"]],
        textposition="outside", showlegend=False,
    ), row=1, col=2)

    fig.update_layout(title="第51回衆院選 争点別YouTube注目度", height=500)
    return fig


def build_issue_scatter(data):
    """争点別 動画数 vs 平均再生回数"""
    df = data["issue_stats"]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["video_count"], y=df["avg_views"],
        mode="markers+text",
        text=df["issue"], textposition="top center",
        marker=dict(
            size=df["total_views"] / df["total_views"].max() * 60 + 10,
            color=df["total_views"],
            colorscale="Viridis",
            showscale=True,
            colorbar=dict(title="総再生回数"),
        ),
        hovertemplate=(
            "<b>%{text}</b><br>"
            "動画数: %{x}<br>"
            "平均再生回数: %{y:,.0f}<br>"
            "<extra></extra>"
        ),
    ))

    fig.update_layout(
        title="争点別 動画数 vs 平均再生回数（バブルサイズ＝総再生回数）",
        xaxis_title="動画数", yaxis_title="平均再生回数",
    )
    return fig


def build_party_channels(data):
    """政党チャンネル統計"""
    df = data["channels"].dropna(subset=["party_name"])
    if df.empty:
        return go.Figure().update_layout(title="政党チャンネルデータなし")

    df = df.sort_values("subscriber_count", ascending=True)
    colors = [PARTY_COLORS.get(p, "#888") for p in df["party_name"]]

    fig = make_subplots(
        rows=1, cols=3,
        subplot_titles=("チャンネル登録者数", "投稿動画数", "総再生回数"),
        horizontal_spacing=0.12,
    )

    fig.add_trace(go.Bar(
        y=df["party_name"], x=df["subscriber_count"],
        orientation="h", marker_color=colors,
        text=[f"{v/10000:.1f}万" for v in df["subscriber_count"]],
        textposition="outside", showlegend=False,
    ), row=1, col=1)

    fig.add_trace(go.Bar(
        y=df["party_name"], x=df["video_count"],
        orientation="h", marker_color=colors,
        text=df["video_count"], textposition="outside", showlegend=False,
    ), row=1, col=2)

    fig.add_trace(go.Bar(
        y=df["party_name"], x=df["view_count"],
        orientation="h", marker_color=colors,
        text=[f"{v/1e8:.2f}億" for v in df["view_count"]],
        textposition="outside", showlegend=False,
    ), row=1, col=3)

    fig.update_layout(title="政党公式YouTubeチャンネル比較", height=500)
    return fig


def build_party_performance(data):
    """政党別 選挙期間中の動画パフォーマンス"""
    df = data["party_stats"].sort_values("total_views", ascending=False)
    colors = [PARTY_COLORS.get(p, "#888") for p in df["party_name"]]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Bar(
        x=df["party_name"], y=df["total_views"],
        name="総再生回数", marker_color=colors, opacity=0.85,
        text=[f"{v/10000:.1f}万" for v in df["total_views"]],
        textposition="outside",
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        x=df["party_name"], y=df["avg_views"],
        name="平均再生回数", mode="markers+lines",
        marker=dict(size=12, color="#333", symbol="diamond"),
        line=dict(color="#333", dash="dot"),
    ), secondary_y=True)

    fig.update_layout(
        title="政党別 選挙期間中の動画パフォーマンス",
        hovermode="x unified",
    )
    fig.update_yaxes(title_text="総再生回数", secondary_y=False)
    fig.update_yaxes(title_text="平均再生回数", secondary_y=True)
    return fig


def build_sentiment(data):
    """コメント感情分析"""
    df = data["sentiment"]
    colors = [SENTIMENT_COLORS.get(s, "#888") for s in df["sentiment"]]
    labels = [SENTIMENT_LABELS.get(s, s) for s in df["sentiment"]]

    fig = make_subplots(
        rows=1, cols=2,
        specs=[[{"type": "pie"}, {"type": "bar"}]],
        subplot_titles=("感情分布", "感情別コメント数"),
    )

    fig.add_trace(go.Pie(
        labels=labels, values=df["count"],
        marker=dict(colors=colors),
        textinfo="label+percent", textfont_size=14,
        hole=0.35,
    ), row=1, col=1)

    fig.add_trace(go.Bar(
        x=labels, y=df["count"],
        marker_color=colors, text=df["count"], textposition="outside",
        showlegend=False,
    ), row=1, col=2)

    fig.update_layout(title="選挙関連動画コメントの感情分析", height=450)
    return fig


def build_top_videos(data, top_n=15):
    """再生回数トップ動画"""
    df = data["videos"]
    if df.empty:
        return go.Figure().update_layout(title="動画データなし")

    df = df.nlargest(top_n, "view_count")
    df = df.sort_values("view_count", ascending=True)

    labels = [t[:35] + "…" if len(str(t)) > 35 else str(t) for t in df["title"]]
    colors = [f"hsl({i * 240 // len(df)}, 65%, 50%)" for i in range(len(df))]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=labels, x=df["view_count"],
        orientation="h", marker_color=colors,
        text=[f"{v/10000:.1f}万回" for v in df["view_count"]],
        textposition="outside",
        hovertemplate=(
            "<b>%{y}</b><br>"
            "再生回数: %{x:,.0f}<br>"
            "<extra></extra>"
        ),
    ))

    fig.update_layout(
        title=f"再生回数トップ{top_n}動画",
        xaxis_title="再生回数",
        height=max(500, top_n * 40),
        margin=dict(l=300),
    )
    return fig


def build_engagement_scatter(data):
    """動画のエンゲージメント分析（再生回数 vs いいね率）"""
    df = data["videos"]
    if df.empty:
        return go.Figure().update_layout(title="動画データなし")

    df = df.copy()
    df["like_rate"] = df["like_count"] / df["view_count"] * 100
    df["comment_rate"] = df["comment_count"] / df["view_count"] * 100
    df["published_at"] = pd.to_datetime(df["published_at"])
    df["short_title"] = df["title"].str[:30]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["view_count"], y=df["like_rate"],
        mode="markers",
        marker=dict(
            size=8 + df["comment_count"] / df["comment_count"].max() * 25,
            color=df["published_at"].astype(int) / 1e18,
            colorscale="Plasma",
            showscale=True,
            colorbar=dict(title="投稿日"),
            opacity=0.7,
        ),
        text=df["short_title"],
        hovertemplate=(
            "<b>%{text}</b><br>"
            "再生回数: %{x:,.0f}<br>"
            "いいね率: %{y:.2f}%<br>"
            "<extra></extra>"
        ),
    ))

    fig.update_layout(
        title="動画エンゲージメント分析（バブルサイズ＝コメント数）",
        xaxis_title="再生回数", yaxis_title="いいね率 (%)",
        xaxis_type="log",
    )
    return fig


def generate_summary_stats(data):
    """サマリー統計を生成"""
    videos = data["videos"]
    channels = data["channels"].dropna(subset=["party_name"])
    sentiment = data["sentiment"]

    total_videos = len(videos) if not videos.empty else 0
    total_views = int(videos["view_count"].sum()) if not videos.empty else 0
    avg_views = int(videos["view_count"].mean()) if not videos.empty else 0
    total_channels = len(channels)

    pos_count = int(sentiment.loc[sentiment["sentiment"] == "positive", "count"].sum())
    total_comments = int(sentiment["count"].sum())
    pos_rate = pos_count / total_comments * 100 if total_comments > 0 else 0

    return {
        "total_videos": total_videos,
        "total_views": total_views,
        "avg_views": avg_views,
        "total_channels": total_channels,
        "total_comments": total_comments,
        "pos_rate": pos_rate,
    }


def create_dashboard():
    """HTMLダッシュボードを生成"""
    print("データ読み込み中...")
    data = load_data()
    stats = generate_summary_stats(data)

    print("グラフ生成中...")
    figs = {
        "daily_trend": build_daily_trend(data),
        "daily_views": build_daily_views(data),
        "issue_comparison": build_issue_comparison(data),
        "issue_scatter": build_issue_scatter(data),
        "party_channels": build_party_channels(data),
        "party_performance": build_party_performance(data),
        "sentiment": build_sentiment(data),
        "top_videos": build_top_videos(data),
        "engagement": build_engagement_scatter(data),
    }

    # 共通レイアウト設定
    for fig in figs.values():
        fig.update_layout(
            template="plotly_white",
            font=dict(family="Hiragino Sans, Noto Sans JP, sans-serif"),
            title_font_size=18,
            hoverlabel=dict(font_size=13),
        )

    # HTMLパーツを生成
    chart_divs = []
    for key, fig in figs.items():
        html = fig.to_html(full_html=False, include_plotlyjs=False)
        chart_divs.append(f'<div class="chart-container" id="chart-{key}">{html}</div>')

    charts_html = "\n".join(chart_divs)

    html_template = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>第51回衆院選 YouTube分析ダッシュボード</title>
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
    background: linear-gradient(135deg, var(--primary), var(--accent));
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
    border-left: 4px solid var(--highlight);
  }}
  .chart-container {{
    background: var(--card);
    border-radius: 12px;
    padding: 1rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
  }}
  .chart-row {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5rem;
  }}
  .footer {{
    text-align: center;
    padding: 2rem;
    color: #999;
    font-size: 0.85rem;
  }}
  @media (max-width: 900px) {{
    .chart-row {{
      grid-template-columns: 1fr;
    }}
    .stats-grid {{
      grid-template-columns: repeat(2, 1fr);
    }}
  }}
</style>
</head>
<body>
<div class="header">
  <h1>第51回衆議院議員総選挙 YouTube分析ダッシュボード</h1>
  <p>分析期間: 2026年1月1日 〜 2月8日 ｜ 公示日: 1月27日 ｜ 投票日: 2月8日</p>
</div>

<div class="stats-grid">
  <div class="stat-card">
    <div class="stat-value">{stats['total_videos']}</div>
    <div class="stat-label">分析対象動画数</div>
  </div>
  <div class="stat-card">
    <div class="stat-value">{stats['total_views'] // 10000}万</div>
    <div class="stat-label">総再生回数</div>
  </div>
  <div class="stat-card">
    <div class="stat-value">{stats['avg_views']:,}</div>
    <div class="stat-label">平均再生回数</div>
  </div>
  <div class="stat-card">
    <div class="stat-value">{stats['total_channels']}</div>
    <div class="stat-label">政党公式チャンネル</div>
  </div>
  <div class="stat-card">
    <div class="stat-value">{stats['total_comments']:,}</div>
    <div class="stat-label">分析コメント数</div>
  </div>
  <div class="stat-card">
    <div class="stat-value">{stats['pos_rate']:.1f}%</div>
    <div class="stat-label">ポジティブ率</div>
  </div>
</div>

<div class="dashboard">
  <h2 class="section-title">投稿トレンド分析</h2>
  {chart_divs[0]}
  {chart_divs[1]}

  <h2 class="section-title">争点別分析</h2>
  {chart_divs[2]}
  {chart_divs[3]}

  <h2 class="section-title">政党チャンネル分析</h2>
  {chart_divs[4]}
  {chart_divs[5]}

  <h2 class="section-title">コメント感情分析</h2>
  {chart_divs[6]}

  <h2 class="section-title">動画パフォーマンス</h2>
  {chart_divs[7]}
  {chart_divs[8]}
</div>

<div class="footer">
  <p>第51回衆議院議員総選挙 YouTube分析プロジェクト</p>
  <p>※ サンプルデータによるデモ表示です。実データの取得にはYouTube Data API v3のキーが必要です。</p>
</div>
</body>
</html>"""

    output_path = OUTPUT_DIR / "election_dashboard.html"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_template, encoding="utf-8")
    print(f"\nダッシュボード生成完了!")
    print(f"  出力先: {output_path}")
    return output_path


if __name__ == "__main__":
    create_dashboard()
