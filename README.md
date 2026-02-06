# 第51回衆議院議員総選挙 YouTube データ分析 & 議席予測

2026年2月8日投開票の第51回衆議院議員総選挙に関する **YouTube動画・ニュース記事・世論調査データ** を統合分析し、複数モデルによる議席予測とインタラクティブな可視化を提供するプロジェクトです。

## ダッシュボード一覧

本プロジェクトでは **4つのインタラクティブダッシュボード**（HTML）を生成します。

| ダッシュボード | ファイル | 説明 |
|---|---|---|
| YouTube分析 | `election_dashboard.html` | 動画投稿トレンド・政党別エンゲージメント・感情分析・議席予測 |
| ニュース記事分析 | `news_dashboard.html` | 主要メディアの記事カバレッジ・論調分析・ニュースモデル予測 |
| まとめ・予測比較 | `summary_dashboard.html` | 全7モデル（6予測 + 世論調査ベースライン）の横断比較 |
| 選挙区マップ | `map_dashboard.html` | 日本地図上の都道府県別・選挙区別候補者情報 |

すべてのダッシュボードはナビゲーションバーで相互に移動可能です。

---

## 議席予測モデル

465議席（小選挙区289 + 比例176）を以下の7つのアプローチで予測します。

| # | モデル名 | データソース | アプローチ |
|---|---|---|---|
| 0 | 世論調査ベースライン | 世論調査 | 各社世論調査の加重平均に基づく基準値 |
| 1 | YouTubeエンゲージメント | YouTube | 再生数・いいね・コメント数のシェアから議席配分 |
| 2 | 感情分析加重 | YouTube | エンゲージメント × コメント感情スコアで補正 |
| 3 | 世論調査 + YouTube | YouTube + 世論調査 | 世論調査ベースラインにYouTubeモメンタムで補正 |
| 4 | YouTubeアンサンブル | YouTube + 世論調査 | モデル1〜3の加重平均 |
| 5 | ニュース記事モデル | ニュース + 世論調査 | 記事頻度・論調から議席予測 |
| 6 | 統合アンサンブル | YouTube + ニュース + 世論調査 | モデル4とモデル5の統合 |

## 選挙区マップ機能

- **都道府県コロプレスマップ**: 47都道府県を優勢政党の色で色分け表示
- **クリックでドリルダウン**: 都道府県をクリックすると、その地域の小選挙区一覧と各候補者情報（政党・予測得票率・現職/新人・YouTubeスコア・ニュース言及数）を表示
- **比例ブロック別チャート**: 11比例ブロック（北海道〜九州）の政党別予測議席
- **接戦区ランキング**: 得票差が僅差のトップ20選挙区

---

## プロジェクト構成

```
youtube-visualization/
├── src/
│   ├── config.py                 # 設定（検索キーワード、チャンネルID等）
│   ├── collect_data.py           # YouTube API データ収集
│   ├── analyze.py                # データ分析
│   ├── visualize.py              # グラフ出力（matplotlib/seaborn）
│   ├── generate_sample_data.py   # デモ用サンプルデータ生成
│   ├── predict_seats.py          # 議席予測エンジン（6モデル）
│   ├── create_dashboard.py       # YouTube分析ダッシュボード生成
│   ├── create_news_dashboard.py  # ニュース記事分析ダッシュボード生成
│   ├── create_summary_dashboard.py # まとめ・予測比較ダッシュボード生成
│   └── create_map_dashboard.py   # 選挙区マップダッシュボード生成
├── data/
│   ├── raw/                      # API から取得した生データ
│   ├── processed/                # 加工済みデータ（CSV）
│   ├── sample/                   # サンプルデータ
│   └── geojson/
│       └── japan.geojson         # 日本都道府県境界データ（47都道府県）
├── notebooks/
│   └── election_analysis_demo.ipynb  # インタラクティブ分析（Plotly）
├── output/
│   ├── election_dashboard.html   # YouTube分析ダッシュボード
│   ├── news_dashboard.html       # ニュース記事分析ダッシュボード
│   ├── summary_dashboard.html    # まとめ・予測比較ダッシュボード
│   ├── map_dashboard.html        # 選挙区マップダッシュボード
│   └── figures/                  # 出力グラフ画像（PNG）
├── requirements.txt
├── .env.example
└── README.md
```

## 生成されるデータ

| ファイル | 行数 | 説明 |
|---|---|---|
| `youtube_videos.csv` | 200 | 選挙関連YouTube動画の再生数・いいね・コメント数等 |
| `video_comments.csv` | ~2,000 | 動画コメントのテキストと感情分析結果 |
| `channel_stats.csv` | 8 | 各政党公式チャンネルの統計 |
| `news_articles.csv` | ~500 | 主要メディアの選挙関連記事（論調・キーワード） |
| `seat_predictions.csv` | 10 | 政党×モデル別議席予測結果 |
| `district_candidates.csv` | ~860 | 289小選挙区の候補者データ |
| `prefecture_summary.csv` | 47 | 都道府県別の政党議席集約データ |

---

## セットアップ

### 1. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 2. デモの実行（API キー不要）

サンプルデータで全ダッシュボードを生成できます。

```bash
# サンプルデータ生成
python src/generate_sample_data.py

# 議席予測
python src/predict_seats.py

# ダッシュボード生成（4ページ）
python src/create_dashboard.py
python src/create_news_dashboard.py
python src/create_summary_dashboard.py
python src/create_map_dashboard.py

# ブラウザで開く
open output/election_dashboard.html
```

### 3. YouTube API キーの取得（実データ利用時）

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作成
2. YouTube Data API v3 を有効化
3. 認証情報から API キーを生成
4. `.env` ファイルを作成:

```bash
cp .env.example .env
# .env を編集して API キーを設定
```

### 4. 実データでの実行

```bash
python src/collect_data.py    # YouTube APIデータ収集
python src/analyze.py         # データ分析
python src/predict_seats.py   # 議席予測
python src/create_dashboard.py
python src/create_news_dashboard.py
python src/create_summary_dashboard.py
python src/create_map_dashboard.py
```

### 5. Jupyter Notebook

```bash
jupyter notebook notebooks/election_analysis_demo.ipynb
```

Plotly によるインタラクティブなグラフで分析結果を確認できます。

---

## ダッシュボード詳細

### YouTube分析ダッシュボード

- 日別動画投稿数・累計再生回数の推移
- 争点別注目度比較（消費税・安全保障・移民等）
- 政党チャンネル比較（登録者数・動画数・再生回数）
- 政党別動画パフォーマンス
- コメント感情分析（ポジティブ/ネガティブ/ニュートラル分布）
- 再生回数トップ動画ランキング
- 4モデル（YouTubeベース + ベースライン）の議席予測

### ニュース記事分析ダッシュボード

- メディア別記事数・報道量の比較
- 政党別カバレッジとメディア注目度ヒートマップ
- 記事論調（ポジティブ/ネガティブ）の時系列推移
- キーワード・争点別分析
- ニュースモデルによる議席予測（世論調査ベースライン対比）

### まとめ・予測比較ダッシュボード

- 全7モデルの議席予測を棒グラフで横断比較
- YouTube系 vs ニュース系 vs 統合モデルの対比
- モデル間のばらつき（乖離度）分析
- 連立シミュレーション（与党連立 vs 野党連合）
- データソース別レーダーチャート
- モデル一覧テーブル

### 選挙区マップダッシュボード

- 日本全国の都道府県別コロプレスマップ（Plotly Choroplethmapbox）
- クリックで選挙区・候補者の詳細テーブルを表示
- 11比例ブロック別の政党別議席積み上げチャート
- 接戦区（マージンが小さい選挙区）トップ20ランキング

---

## 対象政党

| 政党名 | カラーコード |
|---|---|
| 自由民主党 | `#D7000F` |
| 日本維新の会 | `#008542` |
| 立憲民主党 | `#1E90FF` |
| 公明党 | `#F39800` |
| 国民民主党 | `#FFC000` |
| 日本共産党 | `#FF0000` |
| れいわ新選組 | `#ED6DB2` |
| 参政党 | `#C8A23E` |
| チームみらい | `#00B7CE` |

## 選挙の背景

- **高市早苗首相**が2026年1月23日に国会冒頭解散を実施
- 自民党・日本維新の会の連立 vs 中道改革連合（立憲+公明）
- 主な争点: 消費税減税、物価高対策、安全保障、移民政策
- 36年ぶりの真冬選挙（大雪による投票率への影響も注目）

## 技術スタック

- **Python 3.9+**
- **Plotly** — インタラクティブチャート・コロプレスマップ
- **Pandas** — データ処理・集計
- **matplotlib / seaborn** — 静的グラフ出力
- **GeoJSON** — 日本都道府県境界データ（[dataofjapan/land](https://github.com/dataofjapan/land)）
- **YouTube Data API v3** — 動画・コメントデータ収集

## 注意事項

- YouTube API の1日あたりのクォータ制限に注意してください
- YouTubeのデータは全有権者の意見を代表するものではありません
- アルゴリズムによるレコメンドの偏り、ボットの影響を考慮してください
- 本プロジェクトの予測はデータ分析の学習を目的としたものであり、実際の選挙結果を保証するものではありません

## ライセンス

MIT License
