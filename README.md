# 第51回衆議院議員総選挙 YouTube データ分析

2026年2月8日投開票の第51回衆議院議員総選挙に関するYouTube動画データを収集・分析・可視化するプロジェクトです。

## 分析内容

| 分析 | 説明 |
|------|------|
| 動画投稿トレンド | 選挙関連動画の日別投稿数・再生回数の推移 |
| 争点別分析 | 消費税・安全保障・移民等の争点別注目度比較 |
| 政党チャンネル比較 | 各政党の公式YouTube活用状況の比較 |
| コメント感情分析 | 動画コメントのポジティブ/ネガティブ分類 |
| 人気動画ランキング | 再生回数上位動画の特徴分析 |

## プロジェクト構成

```
youtube-visualization/
├── src/
│   ├── config.py              # 設定（検索キーワード、チャンネルID等）
│   ├── collect_data.py        # YouTube API データ収集
│   ├── analyze.py             # データ分析
│   ├── visualize.py           # グラフ出力（matplotlib/seaborn）
│   └── generate_sample_data.py # デモ用サンプルデータ生成
├── notebooks/
│   └── election_analysis_demo.ipynb  # インタラクティブ分析（Plotly）
├── data/
│   ├── raw/                   # API から取得した生データ
│   ├── processed/             # 加工済みデータ
│   └── sample/                # サンプルデータ
├── output/
│   └── figures/               # 出力グラフ画像
├── requirements.txt
├── .env.example
└── README.md
```

## セットアップ

### 1. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 2. YouTube API キーの取得

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作成
2. YouTube Data API v3 を有効化
3. 認証情報から API キーを生成
4. `.env` ファイルを作成:

```bash
cp .env.example .env
# .env を編集して API キーを設定
```

### 3. デモの実行（API キー不要）

```bash
cd src
python generate_sample_data.py
python visualize.py
```

サンプルデータでグラフが `output/figures/` に出力されます。

### 4. 実データでの実行

```bash
cd src
python collect_data.py    # データ収集
python analyze.py         # 分析
python visualize.py       # 可視化
```

### 5. Jupyter Notebook

```bash
jupyter notebook notebooks/election_analysis_demo.ipynb
```

Plotly によるインタラクティブなグラフで分析結果を確認できます。

## 出力されるグラフ

1. **日別動画投稿数推移** - 公示日前後の投稿量の変化
2. **日別累計再生回数** - 選挙への関心の推移
3. **争点別注目度比較** - 動画数と再生回数で争点をランキング
4. **政党チャンネル比較** - 登録者数・動画数・再生回数
5. **政党別動画パフォーマンス** - 選挙期間中の活動量
6. **コメント感情分析** - ポジティブ/ネガティブ/ニュートラルの分布
7. **再生回数トップ動画** - 最も注目された動画

## 選挙の背景

- **高市早苗首相**が2026年1月23日に国会冒頭解散を実施
- 自民党・日本維新の会の連立 vs 中道改革連合（立憲+公明）
- 主な争点: 消費税減税、物価高対策、安全保障、移民政策
- 36年ぶりの真冬選挙（大雪による投票率への影響も注目）

## 注意事項

- YouTube API の1日あたりのクォータ制限に注意してください
- YouTubeのデータは全有権者の意見を代表するものではありません
- アルゴリズムによるレコメンドの偏り、ボットの影響を考慮してください
