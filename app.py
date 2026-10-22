"""週一チェック モック（Tech0 BootCamp）
起動： streamlit run app.py
- APIキーがなければ台本モード、あれば AI モード（engine.py 参照）
- 記録は mock.db（SQLite）。本番は Azure SQL Database
"""
from datetime import datetime

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

import db
import engine

load_dotenv()

st.set_page_config(page_title="週一チェック（モック）", page_icon="🎙️", layout="wide")
st.markdown("""
<style>
.block-container {padding-top: 3.2rem;}
.badge {display:inline-block;padding:2px 12px;border-radius:999px;font-weight:700;font-size:0.95rem}
.lv-言えた {background:#DCFCE7;color:#166534}
.lv-あと一歩 {background:#FEF3C7;color:#92400E}
.lv-これから {background:#E5E7EB;color:#374151}
.card {border:1px solid #CBD5E1;border-radius:10px;padding:14px 18px;background:#F8FAFC;margin-bottom:10px}
.theme-q {font-size:1.25rem;font-weight:700;color:#0B2A5B}
.small {color:#64748B;font-size:0.85rem}
</style>""", unsafe_allow_html=True)

c = db.init()
MODE = "AI" if engine.ai_client() else "台本"
LV_ORDER = ["言えた", "あと一歩", "これから"]
ANSWER_SEC = 60  # 1回の答えの目安（秒）


def badge(lv):
    return f'<span class="badge lv-{lv}">{lv}</span>'


# ---------------------------------------------------------------- サイドバー（モックのログイン）
with st.sidebar:
    st.markdown("### 🎙️ 週一チェック")
    st.caption("モック（架空データ）")
    role = st.radio("ログイン（モック）", ["受講生", "講師・TA"], horizontal=True)
    if role == "受講生":
        studs = db.students(c)
        names = [s["name"] for s in studs]
        me = st.selectbox("受講生", names, index=2)
        me_id = studs[names.index(me)]["id"]
    st.divider()
    st.caption(f"動作モード：**{MODE}**")
    st.caption("台本＝APIキーなしで、決まったルールで聞き返す。AI＝Azure OpenAI / OpenAI のキーを設定すると本物のAIで動く。")
    st.caption("本番はEntra IDでログイン。受講生は自分の記録だけ、講師・TAは担当期の全員分が見える。")


# ================================================================ 受講生
def student_page():
    theme = db.current_theme(c)
    st.markdown(f"#### {me} さん")
    if not theme:
        st.info("今週のテーマはまだ公開されていません。")
        return
    st.markdown(f"""<div class="card"><div class="small">Week{theme['week']}｜今週のテーマ（観点：{theme['viewpoint']}）</div>
    <div class="theme-q">{theme['question']}</div>
    <div class="small" style="margin-top:8px">「言えた」の目安　① {theme['e1']}　② {theme['e2']}</div></div>""", unsafe_allow_html=True)

    ss = st.session_state
    key = f"{me_id}-{theme['id']}"
    if ss.get("key") != key:
        ss.key, ss.turns, ss.final, ss.started = key, [], None, None
        ss.mic_n, ss.mic_err = 0, None

    left, right = st.columns([3, 2], gap="large")
    with left:
        if not ss.turns:
            st.write("AIの試問官と3分ほど話します。1回の答えは1分ほど、自分のアプリの例を入れて話してください。AIがあなたの答えに合わせて、その場で掘り下げて聞き返します。試問の途中ではヒントは出ません。終わったら、答えの例と解説が返ってきます。")
            if st.button("▶ 試問を始める", type="primary"):
                ss.turns = [{"role": "ai", "text": theme["question"]}]
                ss.started = datetime.now().isoformat()
                ss.mic_err = None
                st.rerun()
        for t in ss.turns:
            with st.chat_message("assistant" if t["role"] == "ai" else "user", avatar=":material/smart_toy:" if t["role"] == "ai" else ":material/person:"):
                st.write(t["text"])

        if MODE == "AI" and ss.turns and not ss.final and ss.turns[-1]["role"] == "ai":
            last = ss.turns[-1]["text"]
            if ss.get("spoken") != last:
                try:
                    ss.voice = engine.speak(engine.ai_client(), last)
                except Exception:
                    ss.voice = None
                ss.spoken = last
            if ss.get("voice"):
                st.audio(ss.voice, format="audio/mp3", autoplay=True)

        if ss.turns and not ss.final:
            _countdown(len(ss.turns), ANSWER_SEC)
            if MODE == "AI":
                # 録音を止めた瞬間にそのまま送信（確認・送信ボタンなし）
                audio = st.audio_input("🎤 マイクで話す（止めるとそのまま送信）", key=f"mic-{ss.get('mic_n', 0)}")
                if ss.get("mic_err"):
                    st.warning(ss.mic_err)
                if audio is not None:
                    ss.mic_n = ss.get("mic_n", 0) + 1
                    ss.mic_err = None
                    try:
                        with st.spinner("……"):
                            text = engine.transcribe(engine.ai_client(), audio.getvalue()).strip()
                    except Exception as e:
                        text, ss.mic_err = "", f"文字起こしに失敗しました: {e}"
                    if text:
                        _answer(theme, text)
                    ss.mic_err = ss.mic_err or "聞き取れませんでした。もう一度話してください。"
                    st.rerun()
            else:
                st.caption("音声入力を使うには `.env` に OpenAI または Azure OpenAI のAPIキーを設定してください。")
            said = st.chat_input("話した内容（モックでは文字で入力できます）")
            if said:
                _answer(theme, said)

        if ss.final:
            f = ss.final
            ans = (f.get("answer") or "").replace("\n", "<br><br>")
            st.markdown(f"""<div class="card"><div class="small">試問の結果（その場でAIが返します）</div>
            <div style="margin:6px 0 10px">{badge(f['level'])}</div>
            <b>足りなかったところ</b><br>{f['reason']}<br><br>
            <b>答えの例と解説</b><br>{ans}<br><br>
            <b>次にやること</b><br>{f['next_step']}</div>""", unsafe_allow_html=True)
            if f.get("warning"):
                st.warning(f["warning"])
            if st.button("もう一度やる"):
                ss.turns, ss.final, ss.started = [], None, None
                st.rerun()

    with right:
        st.markdown("##### これまでの記録")
        hist = db.history(c, me_id)
        if not hist:
            st.caption("まだ記録はありません。")
        for h in hist[::-1]:
            st.markdown(f"""<div class="card"><div class="small">Week{h['week']}｜{h['question']}</div>
            <div style="margin:6px 0">{badge(h['level'])}</div><div style="font-size:0.92rem">{h['next_step']}</div></div>""", unsafe_allow_html=True)
            if h.get("answer"):
                with st.expander("答えの例と解説"):
                    st.write(h["answer"])


def _countdown(turn, sec):
    """AIが聞くたびにリセットされる回答の残り時間（ブラウザ側で動くのでrerun不要）"""
    components.html(f"""
<div id="t" data-turn="{turn}" style="font:700 15px system-ui;display:flex;align-items:center;gap:10px;color:#0B2A5B">
  <span>⏱ 残り <span id="s">{sec}</span> 秒</span>
  <div style="flex:1;height:6px;background:#E5E7EB;border-radius:3px;overflow:hidden">
    <div id="b" style="height:100%;width:100%;background:#0B2A5B;transition:width 1s linear"></div></div>
</div>
<script>
const end = Date.now() + {sec}*1000, t = document.getElementById("t"),
      s = document.getElementById("s"), b = document.getElementById("b");
const tick = () => {{
  const left = Math.max(0, Math.ceil((end - Date.now())/1000));
  s.textContent = left; b.style.width = (left/{sec}*100) + "%";
  const c = left <= 10 ? "#DC2626" : left <= 20 ? "#D97706" : "#0B2A5B";
  t.style.color = c; b.style.background = c;
  if (left === 0) {{ t.firstElementChild.textContent = "⏱ 時間です。話をまとめてください"; return; }}
  setTimeout(tick, 250);
}};
tick();
</script>""", height=34)


def _answer(theme, text):
    ss = st.session_state
    ss.turns.append({"role": "student", "text": text})
    out = engine.next_turn(theme, ss.turns)
    if out["type"] == "question":
        ss.turns.append({"role": "ai", "text": out["text"], "assess": out.get("assess")})
    else:
        ss.final = out
        db.save_session(c, me_id, theme["id"], ss.turns, out, MODE, ss.started)
    st.rerun()


# ================================================================ 講師・TA
def teacher_page():
    st.markdown("#### 講師・TAの画面")
    tabs = st.tabs(["一覧（フォローする人）", "会話の全文", "テーマの設定", "週ごとの推移"])
    all_rows = db.latest_sessions(c)
    ths = db.themes(c)
    labels = [f"Week{t['week']}｜{t['question'][:28]}…（{t['status']}）" for t in ths]

    # ---- 一覧
    with tabs[0]:
        sel = st.selectbox("テーマ", labels, index=0, key="t_list")
        th = ths[labels.index(sel)]
        rows = [r for r in all_rows if r["theme_id"] == th["id"]]
        n_all = len(db.students(c))
        cnt = {lv: sum(r["level"] == lv for r in rows) for lv in LV_ORDER}
        m = st.columns(5)
        m[0].metric("実施", f"{len(rows)} / {n_all}人")
        m[1].metric("言えた", cnt["言えた"])
        m[2].metric("あと一歩", cnt["あと一歩"])
        m[3].metric("これから", cnt["これから"])
        m[4].metric("未実施", n_all - len(rows))

        prev = {}
        for r in all_rows:
            if r["week"] == th["week"] - 1:
                prev[r["student_id"]] = r["level"]
        f1, f2 = st.columns([3, 2])
        lv_sel = f1.multiselect("判定", LV_ORDER, default=["あと一歩"])
        only_cont = f2.checkbox("先週も「あと一歩」以下だった人だけ（フォロー優先）", value=False)
        view = [r for r in rows if r["level"] in lv_sel]
        if only_cont:
            view = [r for r in view if prev.get(r["student_id"]) in ("あと一歩", "これから")]
        df = pd.DataFrame([{
            "受講生": r["name"], "班": r["team"], "判定": r["level"], "先週": prev.get(r["student_id"], "―"),
            "判定の理由": r["reason"], "詰まった瞬間": r["stuck"] or "―", "回数": r["tries"],
            "日時": r["ended_at"][5:16].replace("T", " "),
        } for r in view])
        st.caption(f"{len(view)}人。行を選ぶと「会話の全文」で中身を確かめられます。講義やSlackでのフォローに使います。")
        st.dataframe(df, use_container_width=True, hide_index=True, height=430,
                     column_config={"判定の理由": st.column_config.TextColumn(width="large"), "詰まった瞬間": st.column_config.TextColumn(width="medium")})

    # ---- 会話の全文
    with tabs[1]:
        sel2 = st.selectbox("テーマ", labels, index=0, key="t_log")
        th2 = ths[labels.index(sel2)]
        rows2 = [r for r in all_rows if r["theme_id"] == th2["id"]]
        if rows2:
            names = [f"{r['name']}（{r['level']}）" for r in rows2]
            default = next((i for i, r in enumerate(rows2) if r["student_id"] == "s03"), 0)
            pick = st.selectbox("受講生", names, index=default)
            r = rows2[names.index(pick)]
            a, b = st.columns([3, 2], gap="large")
            with a:
                for t in db.turns_of(c, r["id"]):
                    with st.chat_message("assistant" if t["role"] == "ai" else "user", avatar=":material/smart_toy:" if t["role"] == "ai" else ":material/person:"):
                        st.write(t["text"])
            with b:
                st.markdown(f"""<div class="card"><div class="small">判定（AI）</div><div style="margin:6px 0 10px">{badge(r['level'])}</div>
                <b>判定の理由</b><br>{r['reason']}<br><br><b>詰まった瞬間</b><br>{r['stuck'] or '―'}<br><br>
                <b>本人に返した次にやること</b><br>{r['next_step']}<br><br>
                <b>本人に返した答えの例と解説</b><br>{(r.get('answer') or '―').replace(chr(10), '<br><br>')}<br><br>
                <span class="small">試問 {r['tries']}回目｜{r['ended_at'][:16].replace('T', ' ')}｜{r['mode']}モード</span></div>""", unsafe_allow_html=True)
        else:
            st.caption("まだ試問はありません。")

    # ---- テーマの設定
    with tabs[2]:
        st.write("宿題に合わせて、今週のテーマ（問いと「言えた」の目安）を設定します。公開すると、受講生の画面に出ます。")
        with st.form("theme"):
            a, b, cc = st.columns([1, 2, 2])
            week = a.number_input("週", 1, 52, value=max(t["week"] for t in ths) + 1)
            vp = b.selectbox("観点", ["判断", "仕組み", "課題"])
            lb = cc.selectbox("抽象ラベル（期をまたいで比べる用）", ["システム設計", "データ活用", "顧客・課題設定", "UXデザイン"])
            q = st.text_input("問い", placeholder="例：ログイン機能を自作せず、外部の認証を使ったのはなぜ？")
            e1 = st.text_input("「言えた」の目安①", placeholder="例：自作した場合に困る具体的な場面を1つ挙げられる")
            e2 = st.text_input("「言えた」の目安②", placeholder="例：それを自分のアプリの画面・データで説明できる")
            ans = st.text_area("答えの例と解説（試問の最後に受講生に返す。AIは受講生のアプリに合わせて言い換える）", height=110,
                               placeholder="例：答えの例「……」／解説：自作すると、パスワードの保管や漏えい時の対応まで自分で持つことになる……")
            pub = st.checkbox("すぐに公開する（今のテーマは終了になります）")
            if st.form_submit_button("保存", type="primary") and q and e1 and e2:
                db.add_theme(c, int(week), q, vp, lb, e1, e2, ans, pub, "講師A")
                st.success("保存しました。")
                st.rerun()
        st.dataframe(pd.DataFrame([{"週": t["week"], "問い": t["question"], "観点": t["viewpoint"], "抽象ラベル": t["label"],
                                    "目安①": t["e1"], "目安②": t["e2"], "答えの例と解説": (t.get("answer") or "")[:40] + "…", "状態": t["status"]} for t in ths]),
                     use_container_width=True, hide_index=True)

    # ---- 週ごとの推移
    with tabs[3]:
        agg = []
        for t in sorted(ths, key=lambda x: x["week"]):
            rs = [r for r in all_rows if r["theme_id"] == t["id"]]
            if not rs:
                continue
            d = {lv: sum(r["level"] == lv for r in rs) for lv in LV_ORDER}
            agg.append({"週": f"Week{t['week']}", "抽象ラベル": t["label"], **d, "言えた割合": f"{d['言えた'] / len(rs):.0%}"})
        adf = pd.DataFrame(agg)
        st.bar_chart(adf.set_index("週")[LV_ORDER], color=["#22C55E", "#F59E0B", "#9CA3AF"], height=280)
        st.dataframe(adf, use_container_width=True, hide_index=True)


if role == "受講生":
    student_page()
else:
    teacher_page()
