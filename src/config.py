"""
設定ファイル - 第51回衆議院議員総選挙 YouTube分析
"""
import os
from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# 選挙関連の検索キーワード
SEARCH_QUERIES = [
    "衆院選 2026",
    "衆議院選挙 2026",
    "高市早苗",
    "野田佳彦",
    "中道改革連合",
    "自民党 維新 連立",
    "消費税 減税 選挙",
    "物価高 対策 選挙",
    "衆院選 争点",
    "選挙 2月8日",
    "チームみらい 安野",
    "AI 政治 チームみらい",
]

# 主要政党・候補者のYouTubeチャンネルID（例）
# 実際のチャンネルIDに置き換えてください
PARTY_CHANNELS = {
    "自由民主党": "UCMKNg6-fy1oJVGakFSsFB7w",
    "日本維新の会": "UCkqlZnKIjLFGMN63ePbrecA",
    "立憲民主党": "UCPhMOR4VGbSvMGmqXPBSiqA",
    "国民民主党": "UCRoamnEPf3JdxTJBhgiMxkQ",
    "日本共産党": "UCY6DTN32PWbVqNMbJOEM1CA",
    "れいわ新選組": "UCgIIlSmbdJ7gQqfby8SO53g",
    "参政党": "UCCPjnIHKaBmSMbOKaHvYMqw",
    "チームみらい": "UC_placeholder_team_mirai",  # 安野たかひろ公式チャンネル
}

# 争点キーワード
ISSUE_KEYWORDS = {
    "消費税・物価高": ["消費税", "物価高", "減税", "食料品", "インフレ"],
    "安全保障": ["安全保障", "防衛", "台湾", "中国", "安保"],
    "移民・外国人": ["移民", "外国人", "技能実習", "入管"],
    "経済政策": ["経済", "賃上げ", "成長戦略", "金融政策"],
    "社会保障": ["年金", "医療", "介護", "少子化", "子育て"],
    "政治改革": ["政治改革", "政治とカネ", "裏金", "政治資金"],
}

# データ収集期間
DATE_RANGE = {
    "start": "2026-01-01T00:00:00Z",  # 選挙前の動向
    "end": "2026-02-08T23:59:59Z",     # 投票日まで
}

# API設定
MAX_RESULTS_PER_QUERY = 50
