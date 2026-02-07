"""
インタラクティブHTMLダッシュボード生成スクリプト
Plotlyを使用して選挙分析結果を1つのHTMLファイルにまとめる
"""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import sys
sys.path.insert(0, str(Path(__file__).parent))
from config import (
    PARTY_COLORS, MODEL_LABELS, MODEL_COLORS,
    SENTIMENT_COLORS, SENTIMENT_LABELS,
)

DATA_DIR = Path(__file__).parent.parent / "data"
PROCESSED_DIR = DATA_DIR / "processed"
RAW_DIR = DATA_DIR / "raw"
OUTPUT_DIR = Path(__file__).parent.parent / "output"


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

    # メディアチャンネルデータ
    media_path = PROCESSED_DIR / "media_channels.csv"
    if media_path.exists():
        data["media_channels"] = pd.read_csv(media_path)
    else:
        data["media_channels"] = pd.DataFrame()

    media_mentions_path = PROCESSED_DIR / "media_party_mentions.csv"
    if media_mentions_path.exists():
        data["media_mentions"] = pd.read_csv(media_mentions_path)
    else:
        data["media_mentions"] = pd.DataFrame()

    # 議席予測データ
    pred_path = PROCESSED_DIR / "seat_predictions.csv"
    if pred_path.exists():
        data["predictions"] = pd.read_csv(pred_path)
    else:
        data["predictions"] = pd.DataFrame()

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


def build_media_channels(data):
    """メディア・YouTuberチャンネルの選挙報道分析"""
    df = data["media_channels"]
    if df.empty:
        return go.Figure().update_layout(title="メディアデータなし")

    df = df.sort_values("election_view_count", ascending=True)

    category_colors = {
        "テレビ報道": "#1E90FF",
        "ビジネスメディア": "#2ECC71",
        "政治コメンテーター": "#E74C3C",
        "選挙専門メディア": "#9B59B6",
    }
    colors = [category_colors.get(c, "#888") for c in df["category"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=df["channel_name"], x=df["election_view_count"],
        orientation="h", marker_color=colors,
        text=[f"{v/10000:.0f}万回" for v in df["election_view_count"]],
        textposition="outside",
        hovertemplate=(
            "<b>%{y}</b><br>"
            "選挙動画再生: %{x:,.0f}<br>"
            "<extra></extra>"
        ),
    ))

    fig.update_layout(
        title="メディア・YouTuber別 選挙関連動画 再生回数",
        xaxis_title="選挙関連動画 総再生回数",
        height=max(500, len(df) * 35),
        margin=dict(l=250),
    )
    return fig


def build_media_bubble(data):
    """メディアチャンネルのバブルチャート（登録者 vs 選挙動画再生）"""
    df = data["media_channels"]
    if df.empty:
        return go.Figure().update_layout(title="メディアデータなし")

    category_colors = {
        "テレビ報道": "#1E90FF",
        "ビジネスメディア": "#2ECC71",
        "政治コメンテーター": "#E74C3C",
        "選挙専門メディア": "#9B59B6",
    }

    fig = go.Figure()
    for cat, color in category_colors.items():
        mask = df["category"] == cat
        sub = df[mask]
        if sub.empty:
            continue
        fig.add_trace(go.Scatter(
            x=sub["subscriber_count"], y=sub["election_view_count"],
            mode="markers+text",
            name=cat,
            text=sub["channel_name"].str[:10],
            textposition="top center", textfont_size=9,
            marker=dict(
                size=10 + sub["election_video_count"] / sub["election_video_count"].max() * 30,
                color=color, opacity=0.7,
                line=dict(width=1, color="white"),
            ),
            hovertemplate=(
                "<b>%{text}</b><br>"
                "登録者: %{x:,.0f}<br>"
                "選挙動画再生: %{y:,.0f}<br>"
                "<extra></extra>"
            ),
        ))

    fig.update_layout(
        title="メディアチャンネル 登録者数 vs 選挙動画再生数（バブルサイズ＝動画本数）",
        xaxis_title="チャンネル登録者数",
        yaxis_title="選挙関連動画 総再生回数",
        xaxis_type="log",
        height=550,
    )
    return fig


def build_media_party_mentions(data):
    """メディアにおける政党言及の再生回数内訳"""
    df = data["media_mentions"]
    if df.empty:
        return go.Figure().update_layout(title="メディア言及データなし")

    df = df.sort_values("media_mention_views", ascending=True)
    colors = [PARTY_COLORS.get(p, "#888") for p in df["party_name"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=df["party_name"], x=df["tv_media_views"],
        name="テレビ報道", orientation="h",
        marker_color="#1E90FF",
        hovertemplate="テレビ報道: %{x:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        y=df["party_name"], x=df["youtuber_views"],
        name="政治系YouTuber", orientation="h",
        marker_color="#E74C3C",
        hovertemplate="YouTuber: %{x:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        y=df["party_name"], x=df["other_creator_views"],
        name="その他クリエイター", orientation="h",
        marker_color="#95A5A6",
        hovertemplate="その他: %{x:,.0f}<extra></extra>",
    ))

    fig.update_layout(
        title="政党別 第三者メディアでの言及再生回数（全体の85.7%がサードパーティ由来）",
        xaxis_title="再生回数", barmode="stack",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        height=500,
    )
    return fig


def build_media_vs_official(data):
    """公式チャンネル vs メディア再生回数の比較"""
    df_mentions = data["media_mentions"]
    df_party = data["party_stats"]

    if df_mentions.empty or df_party.empty:
        return go.Figure().update_layout(title="データなし")

    # 公式チャンネルの再生回数とメディア言及を比較
    merged = df_party.merge(
        df_mentions[["party_name", "media_mention_views"]],
        on="party_name", how="inner",
    )
    merged = merged.sort_values("media_mention_views", ascending=True)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=merged["party_name"], x=merged["total_views"],
        name="公式チャンネル再生数", orientation="h",
        marker_color="#4169E1",
        text=[f"{v/10000:.0f}万" for v in merged["total_views"]],
        textposition="inside",
    ))
    fig.add_trace(go.Bar(
        y=merged["party_name"], x=merged["media_mention_views"],
        name="第三者メディア言及再生数", orientation="h",
        marker_color="#FF6347",
        text=[f"{v/10000:.0f}万" for v in merged["media_mention_views"]],
        textposition="inside",
    ))

    fig.update_layout(
        title="政党別 公式チャンネル vs 第三者メディア 再生回数比較",
        xaxis_title="再生回数", barmode="group",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        height=500,
    )
    return fig


def _get_yt_model_col(model_key):
    """モデルキーからカラム名を返す"""
    if model_key == "baseline":
        return "polling_baseline"
    return f"{model_key}_total"


def build_prediction_comparison(data):
    """世論調査ベースライン + 4モデルの議席予測比較"""
    df = data["predictions"]
    if df.empty:
        return go.Figure().update_layout(title="予測データなし")

    party_order = df.sort_values("model4_total", ascending=False)["party_name"].tolist()

    fig = go.Figure()
    for model_key, label in MODEL_LABELS.items():
        col = _get_yt_model_col(model_key)
        if col not in df.columns:
            continue
        vals = [int(df.loc[df["party_name"] == p, col].iloc[0]) if p in df["party_name"].values else 0
                for p in party_order]
        fig.add_trace(go.Bar(
            x=party_order, y=vals, name=label,
            marker_color=MODEL_COLORS[model_key],
            text=vals, textposition="outside", textfont_size=10,
        ))

    # 過半数ライン
    fig.add_shape(type="line", x0=-0.5, x1=len(party_order) - 0.5,
                  y0=233, y1=233, line=dict(color="orange", width=2, dash="dot"))
    fig.add_annotation(x=len(party_order) - 1, y=233, text="過半数 (233)",
                       showarrow=False, font=dict(color="orange", size=11), yshift=12)

    fig.update_layout(
        title="世論調査ベースライン + 政党別 議席予測モデル比較（合計465議席）",
        yaxis_title="予測議席数", barmode="group",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        height=550,
    )
    return fig


def build_prediction_breakdown(data):
    """SMD vs 比例の議席内訳（アンサンブルモデル）"""
    df = data["predictions"]
    if df.empty:
        return go.Figure().update_layout(title="予測データなし")

    df = df.sort_values("model4_total", ascending=True)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=df["party_name"], x=df["model4_smd"],
        name="小選挙区", orientation="h",
        marker_color="#4169E1",
        text=df["model4_smd"], textposition="inside",
    ))
    fig.add_trace(go.Bar(
        y=df["party_name"], x=df["model4_pr"],
        name="比例代表", orientation="h",
        marker_color="#FF6347",
        text=df["model4_pr"], textposition="inside",
    ))

    fig.update_layout(
        title="アンサンブル予測 小選挙区 vs 比例代表 内訳",
        xaxis_title="議席数", barmode="stack",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        height=500,
    )
    return fig


def build_coalition_analysis(data):
    """連立ブロック別の議席分析"""
    df = data["predictions"]
    if df.empty:
        return go.Figure().update_layout(title="予測データなし")

    coalitions = {
        "与党連合\n(自民+維新)": ["自由民主党", "日本維新の会"],
        "中道改革連合\n(立憲+公明)": ["立憲民主党", "公明党"],
        "国民民主党": ["国民民主党"],
        "チームみらい": ["チームみらい"],
        "その他野党\n(共産+れいわ+参政)": ["日本共産党", "れいわ新選組", "参政党"],
        "その他/無所属": ["その他"],
    }

    coalition_colors = ["#E3242B", "#1E90FF", "#FF8C00", "#9B59B6", "#999999"]

    fig = go.Figure()

    for model_key, label in MODEL_LABELS.items():
        col = _get_yt_model_col(model_key)
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
            name=label, marker_color=MODEL_COLORS[model_key],
            text=[f"{v}議席" for v in values], textposition="outside",
        ))

    # 過半数・特別多数ライン
    fig.add_shape(type="line", x0=233, x1=233, y0=-0.5, y1=len(coalitions) - 0.5,
                  line=dict(color="orange", width=2, dash="dot"))
    fig.add_annotation(x=233, y=len(coalitions) - 0.5, text="過半数\n(233)", showarrow=False,
                       font=dict(color="orange", size=10), xshift=-5, yshift=15)

    fig.add_shape(type="line", x0=310, x1=310, y0=-0.5, y1=len(coalitions) - 0.5,
                  line=dict(color="red", width=2, dash="dot"))
    fig.add_annotation(x=310, y=len(coalitions) - 0.5, text="2/3\n(310)", showarrow=False,
                       font=dict(color="red", size=10), xshift=-5, yshift=15)

    fig.update_layout(
        title="連立ブロック別 議席予測比較",
        xaxis_title="議席数", barmode="group",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        height=500,
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

    # 予測統計を追加
    has_predictions = not data["predictions"].empty
    if has_predictions:
        pred = data["predictions"]
        ensemble_top = pred.loc[pred["model4_total"].idxmax()]
        ruling = sum(
            int(pred.loc[pred["party_name"] == p, "model4_total"].iloc[0])
            for p in ["自由民主党", "日本維新の会"]
            if p in pred["party_name"].values
        )
        stats["ensemble_top_party"] = ensemble_top["party_name"]
        stats["ensemble_top_seats"] = int(ensemble_top["model4_total"])
        stats["ruling_coalition"] = ruling

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

    # メディア分析チャート
    has_media = not data["media_channels"].empty
    if has_media:
        figs["media_channels"] = build_media_channels(data)
        figs["media_bubble"] = build_media_bubble(data)
        figs["media_mentions"] = build_media_party_mentions(data)
        figs["media_vs_official"] = build_media_vs_official(data)

    if has_predictions:
        figs["pred_comparison"] = build_prediction_comparison(data)
        figs["pred_breakdown"] = build_prediction_breakdown(data)
        figs["pred_coalition"] = build_coalition_analysis(data)

    # 共通レイアウト設定
    for fig in figs.values():
        fig.update_layout(
            template="plotly_white",
            font=dict(family="Hiragino Sans, Noto Sans JP, sans-serif"),
            title_font_size=18,
            hoverlabel=dict(font_size=13),
        )

    # 予測用HTMLパーツを事前構築（chart_divs不要部分のみ）
    pred_stats_html = ""
    pred_section_html = ""
    media_section_html = ""
    if has_predictions:
        top_party = stats["ensemble_top_party"]
        top_seats = stats["ensemble_top_seats"]
        ruling = stats["ruling_coalition"]
        pred_stats_html = (
            f'<div class="stat-card" style="border-top: 3px solid var(--highlight);">'
            f'<div class="stat-value">{top_seats}</div>'
            f'<div class="stat-label">最多予測: {top_party}</div></div>'
            f'<div class="stat-card" style="border-top: 3px solid var(--highlight);">'
            f'<div class="stat-value">{ruling}</div>'
            f'<div class="stat-label">与党連合予測議席</div></div>'
        )

    # HTMLパーツを生成
    chart_divs = []
    for key, fig in figs.items():
        html = fig.to_html(full_html=False, include_plotlyjs=False)
        chart_divs.append(f'<div class="chart-container" id="chart-{key}">{html}</div>')

    # メディア分析HTMLパーツを構築
    if has_media:
        media_start_idx = 9  # 0-8がベースチャート、9からメディア
        media_section_html = (
            '<h2 class="section-title">メディア・YouTuber 選挙報道分析</h2>'
            '<div class="chart-container" style="padding: 1.2rem; margin-bottom: 1rem; '
            'background: linear-gradient(135deg, #f0f7ff, #e8f4fd); border-left: 4px solid #1E90FF;">'
            '<p style="font-size: 0.9rem; color: #555; line-height: 1.6;">'
            '<strong>第三者メディアの影響力:</strong> '
            '選挙関連YouTube動画の再生回数のうち<strong>85.7%</strong>が'
            '政党公式チャンネル以外（テレビ報道、政治系YouTuber、匿名クリエイター）による動画です。<br>'
            '<span style="color: #1E90FF;">&#9632;</span> テレビ報道（ANNnewsCH, TBS NEWS DIG 等）'
            '<span style="color: #2ECC71; margin-left: 1rem;">&#9632;</span> ビジネスメディア（PIVOT, ReHacQ 等）'
            '<span style="color: #E74C3C; margin-left: 1rem;">&#9632;</span> 政治コメンテーター（高橋洋一, ホリエモン 等）'
            '<span style="color: #9B59B6; margin-left: 1rem;">&#9632;</span> 選挙専門メディア（選挙ドットコム 等）'
            '</p></div>'
        )
        for i in range(4):
            idx = media_start_idx + i
            if idx < len(chart_divs):
                media_section_html += chart_divs[idx]

    if has_predictions:
        blc = MODEL_COLORS["baseline"]
        m1c = MODEL_COLORS["model1"]
        m2c = MODEL_COLORS["model2"]
        m3c = MODEL_COLORS["model3"]
        m4c = MODEL_COLORS["model4"]
        # 予測チャートのインデックス: ベース9 + メディア4(if present) = 13 or 9
        pred_start = 9 + (4 if has_media else 0)
        pred_section_html = (
            '<h2 class="section-title">議席予測分析</h2>'
            '<div class="chart-container" style="padding: 1.2rem; margin-bottom: 1rem; '
            'background: linear-gradient(135deg, #f8f9fa, #e9ecef); border-left: 4px solid #9B59B6;">'
            '<p style="font-size: 0.9rem; color: #555; line-height: 1.6;">'
            '<strong>予測手法:</strong> 世論調査ベースラインに加え、4つのモデルで議席数を予測しています。<br>'
            f'<span style="color: {blc};">&#9632;</span> <strong>世論調査ベースライン</strong>: '
            '世論調査の支持率に基づく議席配分（歴史的SMD比率で小選挙区/比例を分割）<br>'
            f'<span style="color: {m1c};">&#9632;</span> <strong>YouTube指標モデル</strong>: '
            'エンゲージメント（再生数・いいね・登録者数）のシェアで配分<br>'
            f'<span style="color: {m2c};">&#9632;</span> <strong>感情分析加重モデル</strong>: '
            'YouTube指標 + コメント感情（ポジ/ネガ）で補正<br>'
            f'<span style="color: {m3c};">&#9632;</span> <strong>世論調査+YTモデル</strong>: '
            '世論調査ベースライン(70%) + YouTube勢い(30%)<br>'
            f'<span style="color: {m4c};">&#9632;</span> <strong>アンサンブル予測</strong>: '
            '3モデルの加重平均（M1:20%, M2:25%, M3:55%）<br>'
            '<em>※ 小選挙区はキューブ法則（指数2.5）、比例はドント方式で配分</em>'
            '</p></div>'
        )
        for i in range(3):
            idx = pred_start + i
            if idx < len(chart_divs):
                pred_section_html += chart_divs[idx]

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
  .nav-bar {{
    background: #1a1a2e;
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
    background: var(--highlight);
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
<div class="nav-bar">
  <a href="election_dashboard.html" class="active">YouTube分析</a>
  <a href="news_dashboard.html">ニュース記事分析</a>
  <a href="summary_dashboard.html">まとめ・予測比較</a>
  <a href="map_dashboard.html">選挙区マップ</a>
</div>

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
  {pred_stats_html}
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

  {media_section_html}

  {pred_section_html}
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
