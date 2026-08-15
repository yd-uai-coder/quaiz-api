"""旧Java/Spring版(GW11月発表資料.pdf)のシーディングSQLを現行スキーマに合わせて再現する初期データ投入スクリプト。

`uv run python scripts/seed.py` で実行する。カテゴリ・キーワードは既存があれば再利用し、
ユーザーはメールアドレスの重複があればスキップするため、複数回実行しても安全(冪等)。
クイズ本体は重複チェックをしないため、同じクイズを増やしたくない場合は既存データを確認してから実行すること。
"""

import asyncio

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.user import UserRole
from app.repositories.category import CategoryRepository
from app.repositories.keyword import KeywordRepository
from app.repositories.quiz import QuizRepository
from app.repositories.quiz_attempt import QuizAttemptRepository
from app.repositories.user import UserRepository

CATEGORY_NAMES = [
    "アニメ・ゲーム",
    "美術",
    "観光",
    "スポーツ",
    "政治・経済",
    "音楽",
    "映画",
    "グルメ",
]

KEYWORD_TEXTS = [
    "ゲーム",
    "モンハン",
    "ワイルズ",
    "社会",
    "歴史",
    "音楽",
    "日本",
    "世界遺産",
    "自然",
    "野球",
    "メジャーリーグ",
]

# 旧スキーマにはメールアドレスが存在しないため、旧members.idから
# sample{id}@sample.comを合成する。
USERS = [
    {"username": "nanashi", "password": "monhanbaka", "legacy_id": 1},
    {"username": "kohei", "password": "p@ss", "legacy_id": 2},
    {"username": "hiroyuki", "password": "2chan", "legacy_id": 3},
    {"username": "Douko", "password": "p@ss", "legacy_id": 4},
]

QUIZZES = [
    {
        "title": "ゲームの発売予定日",
        "question": "モンスターハンターワイルドの発売日は？",
        "category": "アニメ・ゲーム",
        "creator": "nanashi",
        "difficulty_level_id": 2,
        "commentary": "ゲーム好きならではの問題。",
        "options": [
            ("2025年2月28日", True),
            ("2024年12月25日", False),
            ("2025年1月13日", False),
            ("2025年2月23日", False),
        ],
        "keywords": ["ゲーム", "モンハン", "ワイルズ"],
        "attempt": {"is_correct": True, "is_favorite": True, "review": None},
    },
    {
        "title": "有名画家",
        "question": (
            "「最後の晩餐」「モナリザ」で知られるルネッサンスを代表する人物と言えば誰でしょう？"
        ),
        "category": "美術",
        "creator": "kohei",
        "difficulty_level_id": 1,
        "commentary": (
            "レオナルドはルネサンス期を代表する芸術家であり、「飽くなき探究心」と「尽きることのない独創性」を"
            "兼ね備えた人物といわれている。史上最高の画家の一人と評されるとともに、人類史上で最も多才との呼び声も"
            "高い人物である。アメリカ人美術史家ヘレン・ガードナー（英語版）は、レオナルドが関心を持っていた領域の"
            "広さと深さは空前のもので「レオナルドの知性と性格は超人的、神秘的かつ隔絶的なものである」とした。彼の"
            "絵画作品の『モナ=リザ』と、『最後の晩餐』に知名度の点で比肩しうる絵画作品はほとんどないだろう。"
        ),
        "options": [
            ("ゴッホ", False),
            ("レオナルド・ダ・ビンチ", True),
            ("ノーベル", False),
            ("ロダン", False),
        ],
        "keywords": ["社会", "歴史", "音楽"],
        "attempt": {"is_correct": True, "is_favorite": False, "review": "面白かった"},
    },
    {
        "title": "日本の秘境！世界遺産の自然クイズ",
        "question": (
            "手つかずの自然と豊かな生態系を誇る、日本の世界遺産はどこでしょうか？ "
            "ヒントとして、この地域は、独自の進化を遂げた固有種も多く生息し、学術的な価値も非常に高いと"
            "言われています。また、標高差が大きく、多様な植生が見られることも特徴です。"
        ),
        "category": "観光",
        "creator": "hiroyuki",
        "difficulty_level_id": 3,
        "commentary": (
            "白神山地は、青森県と秋田県にまたがる世界遺産で、広大なブナ原生林がその最大の特徴です。"
            "面積の広さ、ブナの樹齢、そして手つかずの自然の広がりは、世界でも類を見ない規模を誇ります。"
        ),
        "options": [
            ("白神山地", True),
            ("屋久島", False),
            ("知床", False),
            ("富士山", False),
        ],
        "keywords": ["日本", "世界遺産", "自然"],
        "attempt": {"is_correct": True, "is_favorite": True, "review": None},
    },
    {
        "title": "ダルビッシュ有投手のメジャーリーグでの軌跡",
        "question": (
            "メジャーリーグで活躍したダルビッシュ有投手。テキサス・レンジャーズ、ロサンゼルス・ドジ"
            "ャース、シカゴ・カブスとチームを渡り歩き、その卓越した投球術で多くのファンを魅了しまし"
            "た。彼のメジャーリーグでのキャリアを振り返ってみましょう。  レンジャーズ時代は、圧倒的"
            "な球威と多彩な変化球を武器に、多くの勝利を挙げましたが、度重なる故障や、チームの戦略と"
            "の噛み合わなさに苦しむ場面も見られました。ドジャース移籍後も、ケガの影響は続きましたが"
            "、ポストシーズンでは持ち前の経験と実力を発揮。カブス移籍後は、チームの主力投手として活"
            "躍する一方、稀代の変化球投手としての評価を確固たるものとしました。彼のメジャーリーグで"
            "の通算成績は、勝利数、防御率、奪三振数など、様々な数字で評価できますが、特に注目すべき"
            "は、彼の変化球のレパートリーと、その高度なコントロールにあります。高速シンカー、スライ"
            "ダー、フォーク、カーブ、ツーシームなど、多くの球種を操り、打者を翻弄しました。  では、"
            "ダルビッシュ有投手がメジャーリーグで初めてノーヒットノーランを達成したのは、どのチーム"
            "に所属していた時でしょうか？  彼のメジャーリーグでの輝かしいキャリアを改めて振り返り、"
            "その偉業を達成した瞬間を思い出してみてください。"
        ),
        "category": "スポーツ",
        "creator": "Douko",
        "difficulty_level_id": 4,
        "commentary": (
            "ダルビッシュ有投手は、メジャーリーグでノーヒットノーランを達成していません。  問題文は"
            "、彼のメジャーリーグでの活躍ぶりを詳細に記述することで、ノーヒットノーランを達成したか"
            "のような錯覚を誘導する意図がありました。  実際には、彼はメジャーリーグで非常に優れた成"
            "績を残していますが、ノーヒットノーランという快挙は達成していません。  彼のキャリアを振"
            "り返る際には、その素晴らしい投球術だけでなく、ケガとの戦い、チーム事情、そして、常に高"
            "いレベルを求め続ける彼のストイックな姿勢にも注目する必要があります。"
        ),
        "options": [
            ("メジャーでは達成していない", True),
            ("テキサス・レンジャーズ", False),
            ("シカゴ・カブス", False),
            ("ロサンゼルス・ドジャース", False),
        ],
        "keywords": ["野球", "メジャーリーグ"],
        "attempt": {
            "is_correct": True,
            "is_favorite": False,
            "review": "大谷選手の投手成績に期待します。",
        },
    },
]


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        category_repo = CategoryRepository(session)
        keyword_repo = KeywordRepository(session)
        user_repo = UserRepository(session)
        quiz_repo = QuizRepository(session)
        attempt_repo = QuizAttemptRepository(session)

        categories = {
            name: await category_repo.get_or_create(lookup={"name": name})
            for name in CATEGORY_NAMES
        }
        keywords = {text: await keyword_repo.get_or_create(text) for text in KEYWORD_TEXTS}

        users = {}
        for u in USERS:
            email = f"sample{u['legacy_id']}@sample.com"
            existing = await user_repo.get_by_email(email)
            if existing is not None:
                users[u["username"]] = existing
                continue
            users[u["username"]] = await user_repo.create(
                email=email,
                hashed_password=hash_password(u["password"]),
                full_name=u["username"],
                role=UserRole.ADMIN,
            )

        for q in QUIZZES:
            quiz = await quiz_repo.create(
                title=q["title"],
                question=q["question"],
                commentary=q["commentary"],
                category_id=categories[q["category"]].id,
                created_by_id=users[q["creator"]].id,
                difficulty_level_id=q["difficulty_level_id"],
                options=q["options"],
                keywords=[keywords[text] for text in q["keywords"]],
            )
            await attempt_repo.upsert(
                quiz_id=quiz.id,
                user_id=users[q["creator"]].id,
                is_correct=q["attempt"]["is_correct"],
                favorite=q["attempt"]["is_favorite"],
                review=q["attempt"]["review"],
            )

        await session.commit()
        print(
            f"シード完了: カテゴリ{len(categories)}件 / キーワード{len(keywords)}件 / "
            f"ユーザー{len(users)}件 / クイズ{len(QUIZZES)}件"
        )


if __name__ == "__main__":
    asyncio.run(seed())
