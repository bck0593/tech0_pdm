"""試問エンジン
- 台本モード（APIキーなし）：キーワードのルールで聞き返しと判定を返す
- AIモード（APIキーあり）：Azure OpenAI / OpenAI で聞き返しと判定を生成する
"""
import json
import os
import re

MAX_FOLLOWUPS = 3
STUCK_WORDS = ["わからない", "わかんない", "分からない", "分かんない", "わかりません", "分かりません", "考えていなかった", "考えていません"]
APP_WORDS = ["画面", "一覧", "登録", "投稿", "予約", "商品", "ユーザー", "店舗", "記事", "フォーム", "マイページ", "検索画面", "件", "カート", "会員"]


# ---------------------------------------------------------------- 台本モード
def _has(text, words):
    return any(w in text for w in words)


def _rules(theme):
    """テーマごとのキーワード。講師が作った新しいテーマは汎用ルールで動く"""
    r = theme.get("rules") or {}
    return {
        "e1": r.get("e1", ["から", "ため", "ので"]),
        "e2": r.get("e2", APP_WORDS),
        "generic": r.get("generic", ["一般的", "拡張性", "管理しやすい", "本格的", "スケール", "なんとなく"]),
        "q_e1": r.get("q_e1", "それを選んだ決め手を、具体的に言うと？"),
        "q_e2": r.get("q_e2", "それは、あなたのアプリのどの画面の、どのデータで効いてきますか？"),
        "q_deep": r.get("q_deep", "では逆に、そうしなくてもいいのは、どんな場合だと思いますか？"),
        "next_e1": r.get("next_e1", "決め手を、一般論ではなく具体的な場面で1つ言えるようにしよう。"),
        "next_e2": r.get("next_e2", "自分のアプリのどの画面・どのデータの話かを、名前で言えるようにしよう。"),
        "fix_e1": r.get("fix_e1", "決め手を具体的な場面で1つ言えれば「言えた」。"),
        "fix_e2": r.get("fix_e2", "自分のアプリのどの画面・どのデータかを名前で言えれば「言えた」。"),
    }


def _judge_scripted(theme, answers):
    R = _rules(theme)
    joined = " ".join(answers)
    e1 = _has(joined, R["e1"])
    e2 = _has(joined, R["e2"])
    only_generic = _has(joined, R["generic"]) and not e1
    return e1 and not only_generic, e2


def scripted_turn(theme, turns):
    """turns: [{"role": "ai"|"student", "text": str}]
    戻り値: {"type": "question", "text"} または {"type": "final", ...}"""
    R = _rules(theme)
    answers = [t["text"] for t in turns if t["role"] == "student"]
    asked = [t["text"] for t in turns if t["role"] == "ai"]
    followups = len(asked) - 1  # 最初の問いを除く
    e1, e2 = _judge_scripted(theme, answers)
    last = answers[-1] if answers else ""
    stuck_now = _has(last, STUCK_WORDS) or len(last.strip()) < 6

    done = followups >= MAX_FOLLOWUPS or (e1 and e2 and R["q_deep"] in asked) or (stuck_now and followups >= 2)
    if not done:
        if not e1 and R["q_e1"] not in asked:
            return {"type": "question", "text": R["q_e1"]}
        if not e2 and R["q_e2"] not in asked:
            return {"type": "question", "text": R["q_e2"]}
        if e1 and e2 and R["q_deep"] not in asked:
            return {"type": "question", "text": R["q_deep"]}
        if not (e1 and e2):
            return {"type": "question", "text": "もう少し具体的に、あなたのアプリの例で教えてください。"}

    # ---- 判定
    if e1 and e2:
        level = "言えた"
        reason = "①と②の両方を、自分のアプリの具体と結びつけて言えている。"
        nxt = "言えています。そうしなくてもよい場合との線引きまで言えると、さらに強い答えになります。"
    elif e1 or e2:
        level = "あと一歩"
        miss = "②" if e1 else "①"
        have = "①" if e1 else "②"
        reason = f"{have}は言えたが、{miss}が足りない。" + (R["fix_e2"] if e1 else R["fix_e1"])
        nxt = (R["next_e2"] if e1 else R["next_e1"])
    else:
        level = "これから"
        reason = "①②とも、自分の言葉ではまだ言えていない。"
        nxt = "まずは宿題で自分が書いたコードを開き、どこでデータを読み書きしているかを1つ指さして説明できるようにしよう。"

    stuck = ""
    for i, t in enumerate(turns):
        if t["role"] == "student" and (_has(t["text"], STUCK_WORDS) or len(t["text"].strip()) < 6) and i > 0:
            stuck = turns[i - 1]["text"]
            break
    return {"type": "final", "level": level, "reason": reason, "next_step": nxt, "answer": theme.get("answer") or "", "stuck": stuck}


# ---------------------------------------------------------------- AIモード
def ai_client():
    """環境変数があればクライアントを返す。なければ None（台本モード）"""
    try:
        if os.getenv("AZURE_OPENAI_ENDPOINT") and os.getenv("AZURE_OPENAI_API_KEY"):
            from openai import AzureOpenAI
            return AzureOpenAI(azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"], api_key=os.environ["AZURE_OPENAI_API_KEY"],
                               api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")), os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
        if os.getenv("OPENAI_API_KEY"):
            from openai import OpenAI
            return OpenAI(), os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    except Exception:
        return None
    return None


AI_MAX_FOLLOWUPS = 5  # AIモードは会話に応じて深掘りするので台本より多め。3分に収まるようAI側でも配分する

SYSTEM = """あなたはTech0 BootCampの「口頭試問官」です。受講生と3分ほど、本物の面接官のように声で対話し、理解の現在地を確かめます。
あなたの発言はそのまま読み上げられます。話し言葉で、短く（1〜2文、60字程度まで）。

【今週のテーマ】{question}
【「言えた」の目安】①{e1} ②{e2}
目安は判定のゴールであって、質問の台本ではありません。目安に向かいながら、受講生が実際に言ったことに合わせて柔軟に聞きます。

【毎ターンの考え方】
1. 直前の答えを聞いて、①②それぞれの状態を更新する：「未」（まだ出ていない）／「浅い」（触れたが一般論・あいまい・借り物の言葉）／「済」（自分のアプリの具体で言えた）。一般論（どのアプリにも言えること）は「浅い」止まり。
2. 状態と答えの中身を見て、次の一手を1つ選ぶ：
   - 掘る：答えの中のあいまいな言葉・専門用語をそのまま拾って「〇〇って、具体的には？」「それはなぜ？」と聞く
   - 具体化：「あなたのアプリだと、どの画面のどのデータで？」と自分のアプリに引き寄せる
   - 揺さぶる：①②が済になったら、反例・逆の場合・別の選択肢・規模が変わったら、で理解の深さを確かめる（1回まで）
   - 確かめる：答えが前と食い違う／誤解がありそうなら、正解は言わずに「さっき〇〇と言っていましたが…」と本人に気づかせる
   - 足場をかける：詰まったら、問いを小さく分ける・場面を限定する（「たとえばユーザーが登録ボタンを押した直後は？」）。答えやキーワードは言わない
   - 切り替える：同じ点で2回詰まったら深追いせず、もう一方の目安に移る
3. 受講生の言葉を短く受けてから聞く（例：「予約画面ですね。」「なるほど。」）。オウム返しは一言だけ、褒めすぎない。
4. 1回に聞くのは1問だけ。前に聞いたことと同じ聞き方を繰り返さない。

【終える条件】次のどれかで final を出す。
- ①②とも「済」で、揺さぶりにも答えた（または揺さぶりで深さが確かめられた）
- 同じ点で詰まり、足場をかけても進まない
- 聞き返しが{maxf}回に達した（残り回数：{left}回）。残りが少ないときは、まだ「未」の目安を優先して聞く
試問の途中では、正解・ヒント・判定を言わない。

【終了時】受講生のアプリに合わせた答えの例と、なぜそうなるかの解説まで必ず示す。

【出力】JSONのみ。assess は受講生には見せない内部メモ。
続ける：{{"type":"question","assess":{{"e1":"未|浅い|済","e2":"未|浅い|済","move":"掘る|具体化|揺さぶる|確かめる|足場|切り替え","why":"この一手を選んだ理由を一言"}},"text":"受け＋聞き返し"}}
終える：{{"type":"final","assess":{{"e1":"未|浅い|済","e2":"未|浅い|済"}},"level":"言えた|あと一歩|これから","reason":"何があれば言えたになるかの形で1文","next_step":"次にやることを1〜2文","answer":"答えの例（受講生のアプリに合わせて2〜3文）と、なぜそうなるかの解説（2〜3文）","stuck":"受講生が詰まった問いかけを1つ引用（なければ空）"}}"""


def ai_turn(client_model, theme, turns):
    client, model = client_model
    followups = len([t for t in turns if t["role"] == "ai"]) - 1
    left = max(0, AI_MAX_FOLLOWUPS - followups)
    sys = SYSTEM.format(question=theme["question"], e1=theme["e1"], e2=theme["e2"], maxf=AI_MAX_FOLLOWUPS, left=left)
    if theme.get("answer"):
        sys += "\n【講師が用意した答えの例と解説（参考。試問中は口に出さない）】" + theme["answer"]
    msgs = [{"role": "system", "content": sys}]
    for t in turns:
        msgs.append({"role": "assistant" if t["role"] == "ai" else "user", "content": t["text"]})
    # 前のターンの見立てを渡し、続きから判断させる
    prev = next((t.get("assess") for t in reversed(turns) if t.get("assess")), None)
    if prev:
        msgs.append({"role": "system", "content": f"前のターンでの見立て：{json.dumps(prev, ensure_ascii=False)}。直前の答えでどう変わったかを踏まえて次の一手を選ぶこと。"})
    if left == 0:
        msgs.append({"role": "system", "content": "聞き返しの上限に達しました。finalを出力してください。"})
    # 形のくずれた返事が来たら、何が足りないかを伝えて1回だけ出し直させる。だめなら台本に戻す（next_turn）
    for _ in range(2):
        res = client.chat.completions.create(model=model, messages=msgs, response_format={"type": "json_object"}, temperature=0.5)
        raw = res.choices[0].message.content
        out = json.loads(raw)
        problem = _check_ai_out(out, must_final=left == 0)
        if not problem:
            return out
        msgs += [{"role": "assistant", "content": raw},
                 {"role": "system", "content": f"出力の形が正しくありません（{problem}）。【出力】の形どおりのJSONだけを出し直してください。"}]
    raise ValueError(f"AIの出力の形が正しくありません：{problem}")


def _check_ai_out(out, must_final=False):
    """問題があればその内容を返す。問題なければ空文字"""
    kind = out.get("type")
    if kind == "question" and not must_final:
        return "" if str(out.get("text") or "").strip() else "textが空"
    if kind == "final":
        missing = [k for k in ("level", "reason", "next_step", "answer") if not str(out.get(k) or "").strip()]
        if missing:
            return "finalに " + "・".join(missing) + " がない"
        if out["level"] not in ("言えた", "あと一歩", "これから"):
            return f"levelが「{out['level']}」になっている（言えた／あと一歩／これから のどれか）"
        return ""
    return "上限に達したのでtypeはfinalにする" if must_final else f"typeが「{kind}」になっている（questionかfinal）"


def transcribe(client_model, audio_bytes):
    client, _ = client_model
    model = os.getenv("TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe")
    r = client.audio.transcriptions.create(model=model, file=("answer.wav", audio_bytes), language="ja")
    return r.text


def speak(client_model, text):
    """AIの聞き返しを音声にする（AIモードのみ）"""
    client, _ = client_model
    r = client.audio.speech.create(model=os.getenv("TTS_MODEL", "gpt-4o-mini-tts"), voice=os.getenv("TTS_VOICE", "alloy"),
                                   input=text, response_format="mp3")
    return r.read() if hasattr(r, "read") else r.content


def next_turn(theme, turns):
    cm = ai_client()
    if cm:
        try:
            return ai_turn(cm, theme, turns)
        except Exception as e:  # AIが失敗したら台本に戻す
            out = scripted_turn(theme, turns)
            out["warning"] = f"AIの呼び出しに失敗したため台本で続けています：{e}"
            return out
    return scripted_turn(theme, turns)
