"""記録（モックはSQLite。本番はAzure SQL Database）"""
import json
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB = Path(__file__).with_name("mock.db")

DB_RULES = {
    "e1": ["同時", "上書き", "消え", "デプロイ", "再起動", "検索", "絞り込み", "遅く", "重く", "重い", "型", "整合", "壊れ", "バックアップ", "複数人", "並び替え"],
    "e2": ["予約", "商品", "ユーザー情報", "記事", "投稿", "店舗", "会員", "在庫", "レビュー", "メニュー", "空き枠"],
    "q_e1": "JSONのままだと、具体的に何が困りますか？",
    "q_e2": "それは、あなたのアプリのどの画面の、何のデータで起きますか？",
    "q_deep": "では、JSONのままでいいのは、どんなアプリだと思いますか？",
    "next_e1": "JSONのままだと困る場面を、一般論ではなく具体的に1つ言えるようにしよう。",
    "next_e2": "一覧画面などで何のデータを見せているかを、自分のアプリの名前で言えるようにしよう。",
    "fix_e1": "JSONのままだと困る具体的な場面を1つ言えれば「言えた」。",
    "fix_e2": "自分のアプリのどの画面で何のデータを扱っているかを言えれば「言えた」。",
}
API_RULES = {
    "e1": ["Flask", "Django", "Express", "Node", "Rails", "Laravel", "Spring", "Go", "比べ"],
    "q_e1": "他にどんな選択肢がありましたか？",
    "q_e2": "その決め手は、あなたのアプリのどの機能・画面で効いてきますか？",
    "q_deep": "逆に、FastAPIを選ばない方がいいのは、どんなアプリですか？",
    "next_e1": "比べた案を1つ挙げて、何で比べたかを言えるようにしよう。",
    "next_e2": "決め手が、自分のアプリのどの機能・画面で効くのかを言えるようにしよう。",
    "fix_e1": "比べた案を1つ挙げ、比べて選んだと言えれば「言えた」。",
    "fix_e2": "決め手を自分のアプリの機能・画面と結びつけて言えれば「言えた」。",
}
FLOW_RULES = {
    "e1": ["API", "POST", "GET", "DB", "サーバー", "fetch", "リクエスト"],
    "e2": ["フォーム", "ボタン", "予約", "商品", "投稿", "会員", "一覧画面", "登録画面", "検索画面", "マイページ"],
    "q_e1": "画面で押したあと、データは最初にどこへ送られますか？",
    "q_e2": "それは、あなたのアプリのどの画面のどのボタンの話ですか？",
    "q_deep": "その流れのどこで止まったら、画面に何が起きますか？",
    "next_e1": "画面→API→DB→画面の順に、通る場所を言えるようにしよう。",
    "next_e2": "自分のアプリの具体的な画面とボタンで、流れを説明できるようにしよう。",
    "fix_e1": "通る場所を順に言えれば「言えた」。",
    "fix_e2": "自分のアプリの画面とボタンで説明できれば「言えた」。",
}

ANSWERS = {1: "答えの例：「Flaskと比べて、型を書くだけで入力チェックとAPIの説明書（Swagger）が自動でできるのが決め手。班で商品一覧のAPIを分担して作るので、仕様のずれを防げる」\n解説：技術を選んだ理由は「比べた案」「比べた軸（速さ・書きやすさ・型・ドキュメント・チームの慣れ）」「その軸が自分のアプリのどこで効くか」の3点で言うと伝わります。「速いと聞いた」「AIに勧められた」は、比べた軸になっていません。",
           2: "答えの例：「予約フォームで送信を押すと、画面（JavaScript）がAPIにPOSTで送り、サーバーがDBに保存する。一覧画面を開くと、画面がAPIにGETで問い合わせ、サーバーがDBから取り出して返し、画面に表示する」\n解説：画面→API→サーバー→DB→サーバー→画面の順に、どこで何が起きるかを言えると、仕組みを理解していると言えます。どこで止まると何が起きるか（通信エラー、DBにつながらない、など）まで言えるとさらに良いです。",
           3: "答えの例：「予約アプリでは、2人が同時に予約するとpages.jsonは後から書いた方で丸ごと上書きされ、先の予約が消えることがある。DBなら1件ずつ確実に保存でき、予約一覧も日付や空き枠で絞り込める。だからDBに移した」\n解説：JSONファイルは、ファイル1つを丸ごと読み書きします。そのため、同時の書き込み、件数が増えたときの速さ、条件での検索に弱いです。DBは1件単位で読み書きするので、同時に書き込んでも壊れにくく、条件で探すのも得意です。逆に、1人で使う少量のデータなら、JSONのままでも困りません。"}

THEMES = [
    (1, "このアプリのAPIに、なぜその技術（例：FastAPI）を選んだ？", "判断", "システム設計", "他の案を1つ挙げている", "比べて選んだ理由を、自分のアプリの機能・画面と結びつけて言える", API_RULES),
    (2, "画面で入力した値は、どこを通って画面に表示される？", "仕組み", "データ活用", "通る場所を順に言える", "自分のアプリの画面・ボタンで説明できる", FLOW_RULES),
    (3, "pages.jsonのままでもアプリは動きます。それでもDBに移したのはなぜ？", "判断", "データ活用", "JSONのままだと困る具体的な場面を1つ挙げられる", "それを自分のアプリの画面・データで説明できる", DB_RULES),
]

SAMPLE = {  # 受講生の答えのパターン（判定ごと）。Slackに書くくらいの長さで話す想定
    1: {"言えた": ["FlaskとFastAPIで迷いましたが、FastAPIは型を書くと入力チェックとAPIの説明書が自動で作られるのが決め手でした。うちの班は商品一覧のAPIを3人で分担して作るので、説明書が自動でできると仕様のずれを防げます。それでFastAPIにしました。"],
        "あと一歩": ["Flaskも候補でしたが、FastAPIの方が速いと聞いたのでFastAPIにしました。最近よく使われているので、困ったときに調べられる情報も多いと思います。",
                    "Djangoより軽くて書きやすいからです。Djangoは機能が多すぎて、今回くらいのアプリには重いと感じました。FastAPIなら少ないコードで動かせます。",
                    "商品一覧のAPIを作るのに、FastAPIが作りやすそうだったからです。チュートリアルの通りに進めたら、すぐに一覧が返ってくるところまで動きました。"],
        "これから": ["AIに聞いたらFastAPIが良いと言われたので、そのまま使いました。他の技術とは特に検討していません。動いているので問題ないと思っています。",
                    "えっと、特に理由はないです。講義のサンプルがFastAPIだったので、それに合わせました。"]},
    2: {"言えた": ["予約フォームで送信ボタンを押すと、画面のJavaScriptがAPIにPOSTで送ります。サーバーがそれを受け取ってDBに保存します。一覧画面を開くと、今度はGETでAPIに問い合わせて、DBから取り出した予約が画面に並びます。"],
        "あと一歩": ["画面で入力した値はAPIを通ってDBに入って、それがまた画面に戻ってくると思います。間にサーバーがあって、そこで処理しているはずです。",
                    "画面からサーバーに送られて保存されます。保存されたものを画面が読み込んで表示している、という流れだと思います。",
                    "予約フォームで送信すると、保存されて一覧に出ます。どこで保存しているかまでは、まだ追えていないです。"],
        "これから": ["うーん、そこはちょっと分からないです。AIが書いたコードをそのまま使っているので、中までは見ていません。",
                    "勝手に表示されるイメージです。中の仕組みはあまり見ていません。"]},
    3: {"言えた": ["うちのアプリは美容室の予約アプリで、予約データをpages.jsonに保存していました。テストで2人が同時に予約したら、後から保存した方でファイルが丸ごと上書きされて、先の予約が消えてしまいました。DBにすれば1件ずつ保存されるので消えませんし、予約一覧も日付や空き枠で絞り込めます。それでDBに移しました。"],
        "あと一歩": ["データが増えてくると、JSONファイルだと読み込みがどんどん重くなると思います。特に一覧画面でたくさん表示するときに困るはずです。DBにしておけば検索もしやすいですし、後から機能を増やすときにも対応しやすいので、DBに移しました。",
                    "JSONファイルだと、同時に書き込んだときに上書きされてデータが消えることがあると授業で聞きました。DBならそういうことが起きにくいので安全です。将来使う人が増えたときのことも考えて、早めにDBにしておきました。",
                    "うちのアプリでは、予約一覧の画面で予約データを表示しています。最初はpages.jsonで作っていましたが、DBの方がちゃんとしたアプリっぽいですし、チームでもDBにしようという話になったので移しました。"],
        "これから": ["授業でDBを使うように言われたので、それに合わせてDBに移しました。JSONとの違いは正直あまり意識していなかったです。AIに移行のコードを書いてもらって、そのまま動いたので進めました。",
                    "うーん、なんとなくDBの方が良いと思ってそうしました。理由をちゃんと考えたことはなかったです。"]},
}
FOLLOW = {  # 聞き返しへの2回目以降の答え
    "言えた": "件数が少なくて、自分1人しか使わないようなアプリなら、そこまでしなくても困らないと思います。たとえば個人のメモアプリくらいなら十分です。",
    "あと一歩": ["えっと…そこまでは詰めていなかったです。なんとなく、そうした方がいいと思っていました。",
                "うーん、ちょっとわかんないです。何のデータかと言われると、正直そこまでは考えていなかったです。"],
    "これから": ["わからないです。そこまで考えていませんでした。", "すみません、わからないです。"],
}

FIRST_S03 = {1: SAMPLE[1]["これから"][0], 2: SAMPLE[2]["あと一歩"][0], 3: SAMPLE[3]["あと一歩"][0]}


def conn():
    c = sqlite3.connect(DB, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init(reset=False):
    if reset and DB.exists():
        DB.unlink()
    c = conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS students(id TEXT PRIMARY KEY, name TEXT, team TEXT);
    CREATE TABLE IF NOT EXISTS themes(id INTEGER PRIMARY KEY AUTOINCREMENT, week INTEGER, question TEXT, viewpoint TEXT,
        label TEXT, e1 TEXT, e2 TEXT, answer TEXT, rules TEXT, status TEXT, created_by TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS sessions(id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT, theme_id INTEGER,
        started_at TEXT, ended_at TEXT, level TEXT, reason TEXT, next_step TEXT, answer TEXT, stuck TEXT, attempt INTEGER, mode TEXT);
    CREATE TABLE IF NOT EXISTS turns(id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER, idx INTEGER, role TEXT, text TEXT, at TEXT);
    """)
    if c.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 0:
        _seed(c)
    c.commit()
    return c


def _seed(c):
    rnd = random.Random(13)
    for i in range(1, 91):
        c.execute("INSERT INTO students VALUES(?,?,?)", (f"s{i:02d}", f"受講生{i:02d}", f"{(i - 1) // 3 % 26 + 1}班"))
    base = datetime(2026, 9, 28, 20, 0)
    for w, q, vp, lb, e1, e2, rules in THEMES:
        status = "公開中" if w == 3 else "終了"
        c.execute("INSERT INTO themes(week,question,viewpoint,label,e1,e2,answer,rules,status,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                  (w, q, vp, lb, e1, e2, ANSWERS[w], json.dumps(rules, ensure_ascii=False), status, "講師A", (base + timedelta(days=7 * (w - 1))).isoformat()))
    themes = {r["week"]: dict(r) for r in c.execute("SELECT * FROM themes")}
    for i in range(1, 91):
        sid = f"s{i:02d}"
        tier = "上" if i % 5 == 1 else ("下" if i % 5 == 0 else "中")
        for w in (1, 2, 3):
            if w == 3 and i > 62:
                continue  # 今週はまだ途中
            if rnd.random() < 0.06:
                continue  # 未実施
            p = {"上": [0.75, 0.2, 0.05], "中": [0.12 + 0.08 * w, 0.62, 0.26 - 0.08 * w], "下": [0.03, 0.27, 0.7]}[tier]
            lv = rnd.choices(["言えた", "あと一歩", "これから"], p)[0]
            if sid == "s03":
                lv = {1: "これから", 2: "あと一歩", 3: "あと一歩"}[w]
            _seed_session(c, rnd, sid, themes[w], lv, base + timedelta(days=7 * (w - 1) + rnd.randint(0, 4), hours=rnd.randint(0, 3), minutes=rnd.randint(0, 59)))


def _seed_session(c, rnd, sid, theme, lv, at):
    from engine import scripted_turn
    rules = json.loads(theme["rules"])
    th = {**theme, "rules": rules}
    first = FIRST_S03.get(theme["week"]) if sid == "s03" else rnd.choice(SAMPLE[theme["week"]][lv])
    turns = [{"role": "ai", "text": theme["question"]}, {"role": "student", "text": first}]
    follow = FOLLOW[lv] if isinstance(FOLLOW[lv], list) else [FOLLOW[lv]]
    out = scripted_turn(th, turns)
    k = 0
    while out["type"] == "question":
        turns.append({"role": "ai", "text": out["text"]})
        turns.append({"role": "student", "text": follow[min(k, len(follow) - 1)]})
        k += 1
        out = scripted_turn(th, turns)
    attempt = 1 + (rnd.random() < 0.15)
    cur = c.execute("INSERT INTO sessions(student_id,theme_id,started_at,ended_at,level,reason,next_step,answer,stuck,attempt,mode) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (sid, theme["id"], at.isoformat(), (at + timedelta(minutes=3)).isoformat(), out["level"],
                     out["reason"], out["next_step"], out["answer"], out["stuck"], attempt, "台本"))
    for j, t in enumerate(turns):
        c.execute("INSERT INTO turns(session_id,idx,role,text,at) VALUES(?,?,?,?,?)", (cur.lastrowid, j, t["role"], t["text"], (at + timedelta(seconds=25 * j)).isoformat()))


# ---------------------------------------------------------------- 読み書き
def students(c):
    return [dict(r) for r in c.execute("SELECT * FROM students ORDER BY id")]


def themes(c):
    return [dict(r) for r in c.execute("SELECT * FROM themes ORDER BY week DESC, id DESC")]


def current_theme(c):
    r = c.execute("SELECT * FROM themes WHERE status='公開中' ORDER BY week DESC, id DESC LIMIT 1").fetchone()
    if not r:
        return None
    d = dict(r)
    d["rules"] = json.loads(d["rules"]) if d["rules"] else {}
    return d


def add_theme(c, week, question, viewpoint, label, e1, e2, answer, publish, by):
    if publish:
        c.execute("UPDATE themes SET status='終了' WHERE status='公開中'")
    c.execute("INSERT INTO themes(week,question,viewpoint,label,e1,e2,answer,rules,status,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
              (week, question, viewpoint, label, e1, e2, answer, json.dumps({}), "公開中" if publish else "下書き", by, datetime.now().isoformat()))
    c.commit()


def save_session(c, sid, theme_id, turns, final, mode, started):
    n = c.execute("SELECT COUNT(*) FROM sessions WHERE student_id=? AND theme_id=?", (sid, theme_id)).fetchone()[0]
    cur = c.execute("INSERT INTO sessions(student_id,theme_id,started_at,ended_at,level,reason,next_step,answer,stuck,attempt,mode) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (sid, theme_id, started, datetime.now().isoformat(), final["level"], final["reason"], final["next_step"], final.get("answer", ""), final.get("stuck", ""), n + 1, mode))
    for j, t in enumerate(turns):
        c.execute("INSERT INTO turns(session_id,idx,role,text,at) VALUES(?,?,?,?,?)", (cur.lastrowid, j, t["role"], t["text"], datetime.now().isoformat()))
    c.commit()


def latest_sessions(c, theme_id=None):
    """受講生×テーマごとに最新の試問だけを返す"""
    q = """SELECT s.*, st.name, st.team, th.week, th.question, th.label,
             (SELECT COUNT(*) FROM sessions s2 WHERE s2.student_id=s.student_id AND s2.theme_id=s.theme_id) AS tries
           FROM sessions s JOIN students st ON st.id=s.student_id JOIN themes th ON th.id=s.theme_id
           WHERE s.id IN (SELECT MAX(id) FROM sessions GROUP BY student_id, theme_id)"""
    args = ()
    if theme_id:
        q += " AND s.theme_id=?"
        args = (theme_id,)
    return [dict(r) for r in c.execute(q + " ORDER BY st.id", args)]


def turns_of(c, session_id):
    return [dict(r) for r in c.execute("SELECT * FROM turns WHERE session_id=? ORDER BY idx", (session_id,))]


def history(c, sid):
    return [dict(r) for r in c.execute("""SELECT s.*, th.week, th.question FROM sessions s JOIN themes th ON th.id=s.theme_id
        WHERE s.student_id=? AND s.id IN (SELECT MAX(id) FROM sessions WHERE student_id=? GROUP BY theme_id) ORDER BY th.week""", (sid, sid))]
