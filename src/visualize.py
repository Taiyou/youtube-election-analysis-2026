"""
可視化スクリプト
分析結果をグラフとして出力する
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import seaborn as sns

plt.rcParams["font.family"] = "Hiragino Sans"

import sys
sys.path.insert(0, str(Path(__file__).parent))
from config import PARTY_COLORS

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "figures"
DATA_DIR = Path(__file__).parent.parent / "data" / "processed"

# スタイル設定
sns.set_theme(style="whitegrid", font_scale=1.2, rc={"font.family": "Hiragino Sans"})


def plot_daily_video_trend(df):
    """日別動画投稿数の推移"""
    fig, ax = plt.subplots(figsize=(14, 6))
    df["date"] = pd.to_datetime(df["date"])

    ax.bar(df["date"], df["video_count"], color="#4169E1", alpha=0.7, label="投稿数")

    # 移動平均線
    if len(df) >= 3:
        df["ma3"] = df["video_count"].rolling(3, min_periods=1).mean()
        ax.plot(df["date"], df["ma3"], color="#DC143C", linewidth=2, label="3日移動平均")

    ax.set_title("選挙関連YouTube動画 日別投稿数推移", fontsize=16, fontweight="bold")
    ax.set_xlabel("日付")
    ax.set_ylabel("動画数")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=3))
    plt.xticks(rotation=45)
    ax.legend()
    plt.tight_layout()

    path = OUTPUT_DIR / "01_daily_video_trend.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  保存: {path.name}")


def plot_daily_views(df):
    """日別累計再生回数の推移"""
    fig, ax = plt.subplots(figsize=(14, 6))
    df["date"] = pd.to_datetime(df["date"])

    ax.fill_between(df["date"], df["view_count"], alpha=0.3, color="#4169E1")
    ax.plot(df["date"], df["view_count"], color="#4169E1", linewidth=2)

    ax.set_title("選挙関連動画 日別累計再生回数", fontsize=16, fontweight="bold")
    ax.set_xlabel("日付")
    ax.set_ylabel("再生回数")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=3))
    plt.xticks(rotation=45)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x/10000:.0f}万"))
    plt.tight_layout()

    path = OUTPUT_DIR / "02_daily_views.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  保存: {path.name}")


def plot_issue_comparison(df):
    """争点別の注目度比較"""
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    # 動画数
    colors = sns.color_palette("Set2", len(df))
    axes[0].barh(df["issue"], df["video_count"], color=colors)
    axes[0].set_title("争点別 動画数", fontsize=14, fontweight="bold")
    axes[0].set_xlabel("動画数")
    axes[0].invert_yaxis()

    # 総再生回数
    axes[1].barh(df["issue"], df["total_views"], color=colors)
    axes[1].set_title("争点別 総再生回数", fontsize=14, fontweight="bold")
    axes[1].set_xlabel("総再生回数")
    axes[1].xaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, _: f"{x/10000:.0f}万")
    )
    axes[1].invert_yaxis()

    plt.suptitle(
        "第51回衆院選 争点別YouTube注目度", fontsize=16, fontweight="bold", y=1.02
    )
    plt.tight_layout()

    path = OUTPUT_DIR / "03_issue_comparison.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  保存: {path.name}")


def plot_party_channel_stats(df):
    """政党チャンネルの統計比較"""
    df = df.dropna(subset=["party_name"])
    if df.empty:
        print("  政党チャンネルデータなし、スキップ")
        return

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    colors = [PARTY_COLORS.get(p, "#888") for p in df["party_name"]]

    # 登録者数
    axes[0].barh(df["party_name"], df["subscriber_count"], color=colors)
    axes[0].set_title("チャンネル登録者数", fontsize=14, fontweight="bold")
    axes[0].xaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, _: f"{x/10000:.0f}万")
    )

    # 動画数
    axes[1].barh(df["party_name"], df["video_count"], color=colors)
    axes[1].set_title("投稿動画数", fontsize=14, fontweight="bold")

    # 総再生回数
    axes[2].barh(df["party_name"], df["view_count"], color=colors)
    axes[2].set_title("総再生回数", fontsize=14, fontweight="bold")
    axes[2].xaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, _: f"{x/1e8:.1f}億")
    )

    plt.suptitle(
        "政党公式YouTubeチャンネル比較", fontsize=16, fontweight="bold", y=1.02
    )
    plt.tight_layout()

    path = OUTPUT_DIR / "04_party_channels.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  保存: {path.name}")


def plot_party_video_performance(df):
    """政党別の動画パフォーマンス"""
    if df.empty:
        print("  政党動画データなし、スキップ")
        return

    fig, ax = plt.subplots(figsize=(12, 7))
    colors = [PARTY_COLORS.get(p, "#888") for p in df["party_name"]]

    x = range(len(df))
    width = 0.35
    bars1 = ax.bar(
        [i - width / 2 for i in x],
        df["total_views"],
        width,
        label="総再生回数",
        color=colors,
        alpha=0.8,
    )
    ax2 = ax.twinx()
    bars2 = ax2.bar(
        [i + width / 2 for i in x],
        df["video_count"],
        width,
        label="動画数",
        color=colors,
        alpha=0.4,
        hatch="//",
    )

    ax.set_xticks(x)
    ax.set_xticklabels(df["party_name"], rotation=30, ha="right")
    ax.set_ylabel("総再生回数")
    ax2.set_ylabel("動画数")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x/10000:.0f}万"))

    ax.set_title(
        "政党別 選挙期間中の動画パフォーマンス", fontsize=16, fontweight="bold"
    )

    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc="upper right")

    plt.tight_layout()

    path = OUTPUT_DIR / "05_party_performance.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  保存: {path.name}")


def plot_sentiment(df):
    """コメント感情分析の結果"""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    colors_map = {"positive": "#2ECC71", "neutral": "#95A5A6", "negative": "#E74C3C"}
    colors = [colors_map.get(s, "#888") for s in df["sentiment"]]

    # 円グラフ
    axes[0].pie(
        df["count"],
        labels=df["sentiment"],
        colors=colors,
        autopct="%1.1f%%",
        startangle=90,
        textprops={"fontsize": 12},
    )
    axes[0].set_title("感情分布", fontsize=14, fontweight="bold")

    # 棒グラフ
    axes[1].bar(df["sentiment"], df["count"], color=colors)
    axes[1].set_title("感情別コメント数", fontsize=14, fontweight="bold")
    axes[1].set_ylabel("コメント数")

    plt.suptitle(
        "選挙関連動画コメントの感情分析", fontsize=16, fontweight="bold", y=1.02
    )
    plt.tight_layout()

    path = OUTPUT_DIR / "06_sentiment.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  保存: {path.name}")


def plot_top_videos(df_details, top_n=15):
    """再生回数トップ動画"""
    df = pd.read_csv(df_details) if isinstance(df_details, (str, Path)) else df_details
    df = df.nlargest(top_n, "view_count")

    fig, ax = plt.subplots(figsize=(14, 8))

    # タイトルを短縮
    labels = [t[:30] + "..." if len(str(t)) > 30 else str(t) for t in df["title"]]
    colors = sns.color_palette("viridis", len(df))

    ax.barh(range(len(df)), df["view_count"], color=colors)
    ax.set_yticks(range(len(df)))
    ax.set_yticklabels(labels, fontsize=10)
    ax.invert_yaxis()
    ax.set_title(
        f"再生回数トップ{top_n}動画", fontsize=16, fontweight="bold"
    )
    ax.set_xlabel("再生回数")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x/10000:.0f}万"))

    plt.tight_layout()

    path = OUTPUT_DIR / "07_top_videos.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  保存: {path.name}")


def create_all_visualizations():
    """全可視化を実行"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("可視化を実行中...")
    print("=" * 60)

    try:
        daily_counts = pd.read_csv(DATA_DIR / "daily_video_counts.csv")
        plot_daily_video_trend(daily_counts)
    except FileNotFoundError:
        print("  daily_video_counts.csv が見つかりません、スキップ")

    try:
        daily_views = pd.read_csv(DATA_DIR / "daily_views.csv")
        plot_daily_views(daily_views)
    except FileNotFoundError:
        print("  daily_views.csv が見つかりません、スキップ")

    try:
        issue_stats = pd.read_csv(DATA_DIR / "issue_stats.csv")
        plot_issue_comparison(issue_stats)
    except FileNotFoundError:
        print("  issue_stats.csv が見つかりません、スキップ")

    try:
        channel_stats = pd.read_csv(DATA_DIR / "channel_analysis.csv")
        plot_party_channel_stats(channel_stats)
    except FileNotFoundError:
        print("  channel_analysis.csv が見つかりません、スキップ")

    try:
        party_stats = pd.read_csv(DATA_DIR / "party_video_stats.csv")
        plot_party_video_performance(party_stats)
    except FileNotFoundError:
        print("  party_video_stats.csv が見つかりません、スキップ")

    try:
        sentiment = pd.read_csv(DATA_DIR / "sentiment_counts.csv")
        plot_sentiment(sentiment)
    except FileNotFoundError:
        print("  sentiment_counts.csv が見つかりません、スキップ")

    try:
        from pathlib import Path as P
        raw_dir = Path(__file__).parent.parent / "data" / "raw"
        files = sorted(raw_dir.glob("video_details_*.csv"), reverse=True)
        if files:
            plot_top_videos(files[0])
    except FileNotFoundError:
        print("  video_details が見つかりません、スキップ")

    print("\n可視化完了!")
    print(f"出力先: {OUTPUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    create_all_visualizations()
