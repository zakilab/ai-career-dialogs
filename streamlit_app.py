"""Streamlitの入力画面から既存の求人分析・キャリア診断を実行する。"""

import os
import re

import streamlit as st
from google.genai import errors

from src.career_advisor_rag import (
    generate_career_plan,
    load_spreadsheet_data_authenticated,
    retrieve_relevant_context,
)


def get_setting(name, default=None):
    try:
        return st.secrets.get(name, os.environ.get(name, default))
    except FileNotFoundError:
        return os.environ.get(name, default)


def split_items(value):
    return list(dict.fromkeys(
        item.strip() for item in re.split(r"[,、\n]", value) if item.strip()
    ))


def main():
    st.set_page_config(page_title="AIキャリアアドバイス", page_icon="🌱", layout="centered")
    st.title("AIキャリアアドバイス")
    st.write("経験と希望を入力すると、求人データをもとにキャリアプランを提案します。")
    st.caption("入力内容は診断のためにGoogle Geminiへ送信されます。氏名や連絡先は入力不要です。")

    with st.form("career_profile"):
        st.subheader("現在の状況")
        age = st.number_input("年齢", min_value=18, max_value=100, value=30, key="age")
        role = st.text_input("役割・職種", placeholder="例：開発エンジニア、インフラ、PM/PL", max_chars=200, key="role")
        price_type = st.selectbox("入力金額の種類", ["月給（額面）", "契約月単価（SES・フリーランス）"], key="price_type")
        current = st.number_input("現在の月額（万円）", min_value=0.0, max_value=1000.0, value=30.0, step=1.0, key="current")
        qualifications = st.text_input("資格（任意）", placeholder="例：基本情報技術者、AWS SAA", max_chars=1000, key="qualifications")
        skills = st.text_area("業務経験のある技術・環境", placeholder="例：Python、SQL、AWS", max_chars=2000, key="skills")
        domain = st.text_area("最も成果を出した・得意な領域", placeholder="例：要件定義、障害対応、顧客との仕様調整", max_chars=2000, key="domain")

        st.subheader("希望するキャリア")
        st.caption("目標金額は、上で選択した金額の種類で入力してください。")
        minimum = st.number_input("目標月額：最低ライン（万円）", min_value=0.0, max_value=1000.0, value=40.0, step=1.0, key="minimum")
        ideal = st.number_input("目標月額：理想（万円）", min_value=0.0, max_value=1000.0, value=50.0, step=1.0, key="ideal")
        hours = st.number_input("週に学習できる時間", min_value=0, max_value=80, value=5, key="hours")
        interests = st.text_area("興味がある技術・領域", placeholder="例：AWS、AI、Python", max_chars=2000, key="interests")
        st.caption("技術・資格はカンマ、読点、改行で区切れます。")
        submitted = st.form_submit_button("キャリア診断開始", type="primary")

    if submitted:
        # 再診断失敗時に前回の結果を新しい結果として表示しない。
        st.session_state.pop("diagnosis", None)
        if not all([role.strip(), split_items(skills), domain.strip(), split_items(interests)]):
            st.error("役割・職種、経験技術、得意な領域、興味がある技術・領域を入力してください。")
            return
        if ideal < minimum:
            st.error("理想の目標月額は、最低ライン以上にしてください。")
            return

        api_key = get_setting("GEMINI_API_KEY")
        spreadsheet_key = get_setting("SPREADSHEET_KEY")
        if not api_key or not spreadsheet_key:
            st.error("診断の設定が未完了です。管理者はGEMINI_API_KEYとSPREADSHEET_KEYを設定してください。")
            return

        profile = {
            "age": age, "current_role": role.strip(), "price_type": price_type,
            "current_monthly_price_man": current,
            "qualifications": split_items(qualifications),
            "experienced_techs": split_items(skills), "strong_domain": domain.strip(),
            "target_min_monthly_price_man": minimum,
            "target_ideal_monthly_price_man": ideal,
            "weekly_learning_hours": hours, "interested_techs": split_items(interests),
        }
        with st.spinner("求人データを読み込んでいます…"):
            try:
                account = get_setting("gcp_service_account")
                jobs = load_spreadsheet_data_authenticated(
                    spreadsheet_key,
                    worksheet_name=get_setting("WORKSHEET_NAME") or None,
                    service_account_info=dict(account) if account is not None else None,
                    raise_on_error=True,
                )
            except Exception:
                st.error("求人データを取得できませんでした。管理者はGoogle認証、シートID、共有設定を確認してください。")
                return
        if jobs.empty:
            st.warning("求人データがありません。スプレッドシートにデータを追加してから再試行してください。")
            return
        required = {"給与種別", "下限給与(円)", "上限給与(円)", "抽出技術"}
        missing = required - set(jobs.columns)
        if missing:
            st.error("求人データに必要な列がありません：" + "、".join(sorted(missing)))
            return

        with st.spinner("キャリアプランを作成しています…"):
            try:
                context = retrieve_relevant_context(jobs, profile["interested_techs"])
                plan = generate_career_plan(profile, context, api_key=api_key)
            except errors.APIError as error:
                if error.code in (500, 502, 503, 504):
                    #st.error("Geminiが混雑しているか、一時的に応答できません。最大3回試しましたが診断できませんでした。少し時間をおいて再試行してください。")
                    st.error(
                        f"Gemini APIで一時的なエラーが発生しました"
                        # f"（HTTP {error.code}）。最大3回試行しました。"
                        f"（HTTP {error.code}）。1回実行しました。再試行は行っていません。"
                    )   
                elif error.code == 429:
                    st.error("Gemini APIの利用上限に達しました。管理者は割り当て・請求設定を確認してください。")
                elif error.code in (401, 403):
                    st.error("Gemini APIの認証またはアクセス権限に問題があります。管理者はAPIキーと権限設定を確認してください。")
                elif error.code == 404:
                    st.error("指定したGeminiモデルを利用できません。管理者はモデル名と利用可能なモデルを確認してください。")
                else:
                    st.error(f"Gemini APIでエラーが発生しました（HTTP {error.code}）。管理者はAPI設定を確認してください。")
                return
            except Exception:
                st.error("診断に失敗しました。時間をおいて再試行してください。続く場合は管理者がGemini APIの設定・利用状況と求人データを確認してください。")
                return
        st.session_state["diagnosis"] = {"plan": plan, "context": context}

    if "diagnosis" in st.session_state:
        result = st.session_state["diagnosis"]
        stats = result["context"]["market_stats"]
        st.subheader("キャリア診断結果")
        st.markdown(result["plan"])
        with st.expander("診断に使った求人データ"):
            st.write(f"取得求人：{stats['total_jobs']}件 ／ 月給の集計対象：{stats['valid_salary_jobs']}件")
            if stats["valid_salary_jobs"]:
                st.write(f"月給からの平均換算年収：{stats['overall_avg_salary_man']}万円（賞与を除く）")
            else:
                st.write("月給の給与データがなく、平均換算年収は算出できません。")
            st.text(result["context"]["retrieved_jobs_text"])


if __name__ == "__main__":
    main()
