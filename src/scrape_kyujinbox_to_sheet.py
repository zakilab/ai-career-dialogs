import json
import os
import random
import re
import time
import unicodedata
from google.oauth2.service_account import Credentials
import gspread
from bs4 import BeautifulSoup
import requests
from urllib.parse import urljoin
from datetime import datetime
from zoneinfo import ZoneInfo

# --- 対象とする5言語とURLエンコード済みパス ---
TARGET_LANGUAGES = {
    "Python": "python%E3%81%AE%E4%BB%95%E4%BA%8B-%E6%9D%B1%E4%BA%AC%E9%83%BD",
    "Java": "java%E3%81%AE%E4%BB%95%E4%BA%8B-%E6%9D%B1%E4%BA%AC%E9%83%BD",
    "JavaScript": "javascript%E3%81%AE%E4%BB%95%E4%BA%8B-%E6%9D%B1%E4%BA%AC%E9%83%BD",
    "TypeScript": "typescript%E3%81%AE%E4%BB%95%E4%BA%8B-%E6%9D%B1%E4%BA%AC%E9%83%BD",
    "Go": "go%E8%A8%80%E8%AA%9E%E3%81%AE%E4%BB%95%E4%BA%8B-%E6%9D%B1%E4%BA%AC%E9%83%BD",
}

BASE_DOMAIN = "https://xn--pckua2a7gp15o89zb.com/"

# --- User-Agent のランダム候補リスト ---
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
]

# --- 技術キーワードのマスター辞書 ---
TECH_MASTER = {
    # ==========================================
    # --- プログラミング言語 ---
    # ==========================================
    # 主要モダン言語
    r"python": "Python",
    r"javascript|js": "JavaScript",
    r"typescript|ts": "TypeScript",
    r"java": "Java",
    r"ruby": "Ruby",
    r"php": "PHP",
    r"go|golang": "Go",
    r"kotlin": "Kotlin",
    r"swift": "Swift",
    r"rust": "Rust",
    r"scala": "Scala",
    r"dart": "Dart",
    # C/C++ 系 (C# / C++ / C言語)
    r"c#|c＃|csharp": "C#",
    r"c\+\+": "C++",
    # C単体（C#やC++、前後の英数字と混同しないよう厳密指定）
    r"(?<![a-zA-Z0-9])c(?![a-zA-Z0-9\+#])|c言語": "C言語",
    # VB / VBA 系 (業務・業務効率化求人で非常に多い)
    r"vba": "VBA",
    r"vb\.net": "VB.NET",
    r"visual basic": "Visual Basic",
    # 業務系・レガシー・プラットフォーム特化言語
    r"cobol": "COBOL",
    r"abap": "ABAP",  # SAP開発
    r"apex": "Apex",  # Salesforce開発
    r"objective-c|obj-c": "Objective-C",
    r"perl": "Perl",
    r"fortran": "Fortran",
    r"delphi|pascal": "Delphi",
    r"assembly|アセンブラ|アセンブリ": "アセンブリ",
    # データ分析・統計・研究系
    # R単体（前後文字と混同防止）
    r"(?<![a-zA-Z0-9])r(?![a-zA-Z0-9])|r言語": "R言語",
    r"julia": "Julia",
    r"matlab": "MATLAB",
    r"sas": "SAS",
    # シェルスクリプト系 (インフラ・自動化)
    r"bash|zsh|powershell|shell|シェルスクリプト": "Shell/Bash",
    # 関数型・その他先進言語
    r"elixir": "Elixir",
    r"erlang": "Erlang",
    r"haskell": "Haskell",
    r"clojure": "Clojure",
    r"f#|f＃": "F#",
    r"groovy": "Groovy",
    r"solidity": "Solidity",  # ブロックチェーン/Web3
    r"lua": "Lua",
    r"lisp": "Lisp",
    # --- フロントエンド ---
    r"html|html5": "HTML",
    r"css|css3": "CSS",
    r"sass|scss": "Sass",
    r"tailwind(?:css)?": "Tailwind CSS",
    r"react": "React",
    r"next(?:\.js)?": "Next.js",
    r"vue(?:\.js)?": "Vue.js",
    r"nuxt(?:\.js)?": "Nuxt.js",
    r"angular": "Angular",
    r"svelte": "Svelte",
    # --- バックエンド・フレームワーク / ランタイム ---
    r"node(?:\.js)?|nodejs": "Node.js",
    r"express": "Express",
    r"nestjs": "NestJS",
    r"django": "Django",
    r"fastapi": "FastAPI",
    r"flask": "Flask",
    r"ruby on rails|rails": "Ruby on Rails",
    r"laravel": "Laravel",
    r"symfony": "Symfony",
    r"spring(?:boot)?": "Spring Boot",
    r"\.net|dotnet": ".NET",
    # --- モバイル / ゲーム開発 ---
    r"ios": "iOS",
    r"android": "Android",
    r"flutter": "Flutter",
    r"react native": "React Native",
    r"unity": "Unity",
    r"unreal(?: engine)?": "Unreal Engine",
    # --- クラウド / インフラ / サーバー ---
    r"aws": "AWS",
    r"azure": "Azure",
    r"gcp|google cloud": "GCP",
    r"docker": "Docker",
    r"kubernetes|k8s": "Kubernetes",
    r"terraform": "Terraform",
    r"ansible": "Ansible",
    r"linux": "Linux",
    r"nginx": "Nginx",
    r"apache": "Apache",
    r"firebase": "Firebase",
    # --- データベース (DB / NoSQL) ---
    r"sql": "SQL",
    r"mysql": "MySQL",
    r"postgres(?:ql)?": "PostgreSQL",
    r"sqlite": "SQLite",
    r"oracle": "Oracle",
    r"sql server|mssql": "SQL Server",
    r"mongodb": "MongoDB",
    r"redis": "Redis",
    r"dynamodb": "DynamoDB",
    # --- AI / 機械学習 / データ分析 ---
    r"pytorch": "PyTorch",
    r"tensorflow": "TensorFlow",
    r"scikit-learn": "scikit-learn",
    r"pandas": "Pandas",
    r"numpy": "NumPy",
    r"llm|生成ai": "LLM/生成AI",
    r"openai": "OpenAI",
    r"langchain": "LangChain",
    # --- バージョン管理 / ツール / CI/CD ---
    r"git": "Git",
    r"github": "GitHub",
    r"gitlab": "GitLab",
    r"jenkins": "Jenkins",
    r"circleci": "CircleCI",
}


def extract_tech_keywords(title, tag_text):
    combined_text = f"{title} {tag_text}"
    normalized_text = unicodedata.normalize("NFKC", combined_text)

    extracted = []

    for pattern, canonical_name in TECH_MASTER.items():
        if canonical_name == "Java":
            regex = r"(?<![a-zA-Z0-9])java(?![a-zA-Z0-9])(?!\s*script)"
        elif canonical_name in ["C言語", "R言語"]:
            regex = pattern
        else:
            regex = r"(?<![a-zA-Z0-9])(" + pattern + r")(?![a-zA-Z0-9])"

        if re.search(regex, normalized_text, flags=re.IGNORECASE):
            extracted.append(canonical_name)

    unique_techs = list(dict.fromkeys(extracted))
    return ", ".join(unique_techs) if unique_techs else "指定なし"


def parse_salary(salary_text):
    if not salary_text or "記載なし" in salary_text:
        return "不明", "", ""

    salary_type = "不明"
    if "年収" in salary_text:
        salary_type = "年収"
    elif "月給" in salary_text:
        salary_type = "月給"
    elif "時給" in salary_text:
        salary_type = "時給"

    has_range = True if ("〜" in salary_text or "～" in salary_text) else False

    man_numbers = re.findall(r"(\d+(?:\.\d+)?)\s*万", salary_text)
    if man_numbers:
        values = [int(float(n) * 10000) for n in man_numbers]
        min_val = values[0] if len(values) > 0 and has_range else ""
        max_val = values[1] if len(values) > 1 else values[0]
        return salary_type, min_val, max_val

    yen_numbers = re.findall(r"([\d,]+)\s*円", salary_text)
    if yen_numbers:
        values = [int(n.replace(",", "")) for n in yen_numbers]
        min_val = values[0] if len(values) > 0 and has_range else ""
        max_val = values[1] if len(values) > 1 else values[0]
        return salary_type, min_val, max_val

    return salary_type, "", ""


def fetch_html_with_retry(session, url, max_retries=3):
    """リトライ・User-Agentランダム化・指数バックオフ付きで安全にHTMLを取得する関数"""
    for attempt in range(max_retries):
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        }

        try:
            response = session.get(url, headers=headers, timeout=12)

            # 429 (Too Many Requests) や 503 (Service Unavailable) などのアクセス制限検知時
            if response.status_code in [429, 503]:
                wait_time = (attempt + 1) * 60  # 60秒, 120秒... と延長
                print(
                    f"⚠️ アクセス制限検知 (Status: {response.status_code})。{wait_time}秒待機して再トライします... (試行 {attempt + 1}/{max_retries})"
                )
                time.sleep(wait_time)
                continue

            response.raise_for_status()
            response.encoding = response.apparent_encoding
            return response.text

        except requests.RequestException as e:
            print(
                f"通信エラー: {e} (試行 {attempt + 1}/{max_retries})"
            )
            time.sleep(5)

    return None

def extract_job_url(card, page_url):
    """求人タイトルに関連するリンクから求人URLを取り出す。"""
    title_tag = card.select_one("h2, h3, [class*='title']")

    if title_tag is None:
        return None

    # タイトルの内側にリンクがある場合
    link_tag = title_tag.find("a", href=True)

    # タイトル全体がリンクで囲まれている場合
    if link_tag is None:
        link_tag = title_tag.find_parent("a", href=True)

    if link_tag is None:
        return None

    href = link_tag.get("href", "").strip()

    if not href or href.startswith(("#", "javascript:", "mailto:")):
        return None

    job_url = urljoin(page_url, href)

    if not job_url.startswith(("https://", "http://")):
        return None

    return job_url

def save_jobs_by_url(sheet, header_row, jobs_data):
    """同じ求人URLは更新し、新しいURLは追加する。"""
    if not jobs_data:
        raise ValueError("取得求人が0件のため、保存を中止します。")

    width = len(header_row)
    url_index = header_row.index("求人URL")
    language_index = header_row.index("検索言語")

    existing_values = sheet.get_all_values()
    jobs_by_url = {}

    # 既存データをURLで検索できる形にする
    if existing_values:
        if existing_values[0] != header_row:
            raise ValueError("保存先シートの見出しが想定と異なります。")

        for row in existing_values[1:]:
            if not any(str(cell).strip() for cell in row):
                continue

            if len(row) > width:
                raise ValueError("保存先に想定外の列があります。")

            row = row + [""] * (width - len(row))
            job_url = row[url_index].strip()

            if not job_url:
                raise ValueError("保存先に求人URLがない行があります。")
            if job_url in jobs_by_url:
                raise ValueError("保存先に同じ求人URLが複数あります。")

            row[url_index] = job_url
            jobs_by_url[job_url] = row

    # 今回の取得分も、同じURLを1件にまとめる
    collected_by_url = {}

    for source_row in jobs_data:
        if len(source_row) != width:
            raise ValueError("取得データの列数が見出しと一致しません。")

        row = list(source_row)
        job_url = str(row[url_index]).strip()

        if not job_url:
            raise ValueError("取得データに求人URLがありません。")

        row[url_index] = job_url

        if job_url in collected_by_url:
            previous = collected_by_url[job_url]
            languages = (
                str(previous[language_index]).split(",")
                + str(row[language_index]).split(",")
            )
            row[language_index] = ", ".join(
                dict.fromkeys(
                    value.strip() for value in languages if value.strip()
                )
            )

        collected_by_url[job_url] = row

    added = sum(url not in jobs_by_url for url in collected_by_url)
    updated = len(collected_by_url) - added

    # 既存URLは置き換え、新しいURLは追加する
    jobs_by_url.update(collected_by_url)
    values = [header_row] + list(jobs_by_url.values())

    # 必要な行数・列数を確保する
    if sheet.row_count < len(values) or sheet.col_count < width:
        sheet.resize(
            rows=max(sheet.row_count, len(values)),
            cols=max(sheet.col_count, width),
        )

    sheet.update(
        range_name=f"A1:L{len(values)}",
        values=values,
        value_input_option="RAW",
    )

    print(
        f"保存完了：新規 {added} 件、更新対象 {updated} 件、"
        f"保存総数 {len(jobs_by_url)} 件"
    )

def scrape_and_save():
    session = requests.Session()
    jobs_data = []
    fetched_at = datetime.now(ZoneInfo("Asia/Tokyo")).isoformat()

    total_langs = len(TARGET_LANGUAGES)

    for idx, (lang_name, lang_path) in enumerate(
        TARGET_LANGUAGES.items(), start=1
    ):
        print(
            f"\n==================== [{idx}/{total_langs}] {lang_name} の取得開始 ===================="
        )
        base_url = f"{BASE_DOMAIN}{lang_path}"

        for page in range(1, 5):
            url = base_url if page == 1 else f"{base_url}?pg={page}"
            print(f"[{lang_name} - {page}/4 ページ目] リクエスト中: {url}")

            html = fetch_html_with_retry(session, url)
            if not html:
                print(
                    f"❌ {url} の取得に失敗したため、このページをスキップします。"
                )
                continue

            soup = BeautifulSoup(html, "html.parser")
            job_cards = soup.select("section[class*='result']")

            for card in job_cards:
                job_url = extract_job_url(card, url)

                if job_url is None:
                    raise ValueError(
                        f"求人URLを取得できませんでした。保存を中止します: {url}"
                    )

                title_tag = card.select_one("h2, h3, [class*='title']")
                company_tag = card.select_one("[class*='area']")
                salary_tag = card.select_one(
                    "[class*='income'], [class*='salary'], [class*='pay']"
                )
                employ_type_tag = card.select_one("[class*='employType']")
                tag_elements = card.select("[class*='tag_feature']")

                tag_texts = list(
                    dict.fromkeys(
                        el.get_text(strip=True)
                        for el in (tag_elements or [])
                        if el.get_text(strip=True)
                    )
                )

                title = title_tag.text.strip() if title_tag else "タイトルなし"
                company = (
                    company_tag.text.strip() if company_tag else "会社名記載なし"
                )
                raw_salary = (
                    salary_tag.text.strip() if salary_tag else "給料記載なし"
                )
                employ_type = (
                    employ_type_tag.text.strip()
                    if employ_type_tag
                    else "雇用形態記載なし"
                )
                tag = ", ".join(tag_texts) if tag_texts else "タグ記載なし"

                salary_type, min_salary, max_salary = parse_salary(raw_salary)
                extracted_tech = extract_tech_keywords(title, tag)

                jobs_data.append(
                    [
                        title,
                        company,
                        raw_salary,
                        employ_type,
                        tag,
                        lang_name,  # 検索キーワード（検索言語）
                        extracted_tech,
                        salary_type,
                        min_salary,
                        max_salary,
                        job_url,
                        fetched_at,
                    ]
                )

            # --- ページ間のランダムスリープ（3.0〜6.0秒） ---
            page_sleep = random.uniform(3.0, 6.0)
            print(
                f"  └ ページ間調整のため {page_sleep:.1f} 秒待機..."
            )
            time.sleep(page_sleep)

        # --- 言語切り替え時のランダムスリープ（10.0〜15.0秒） ---
        if idx < total_langs:
            lang_sleep = random.uniform(10.0, 15.0)
            print(
                f"\n次言語へ切り替えるため {lang_sleep:.1f} 秒待機します..."
            )
            time.sleep(lang_sleep)

    print(
        f"\n全言語の取得完了。合計 {len(jobs_data)} 件のデータをクレンジングしました。"
    )

    # --- 2. Googleスプレッドシートへ保存 ---
    header_row = [
        "タイトル",
        "会社名",
        "給与",
        "雇用形態",
        "タグ",
        "検索言語",
        "抽出技術",
        "給与種別",
        "下限給与(円)",
        "上限給与(円)",
        "求人URL",
        "最終取得日時", 
    ]

    try:
        SCOPE = ["https://www.googleapis.com/auth/spreadsheets"]
        SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "").strip()
        service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")

        if not SPREADSHEET_ID:
            raise ValueError("環境変数 SPREADSHEET_ID が設定されていません。")

        if service_account_json:
            # GitHub Actionsでは、Secretsから渡された認証JSONを使う
            service_account_info = json.loads(service_account_json)
            creds = Credentials.from_service_account_info(
                service_account_info,
                scopes=SCOPE,
            )
        else:
            # ローカルでは、既存の認証JSONファイルを使う
            credentials_path = os.environ.get(
                "GOOGLE_APPLICATION_CREDENTIALS",
                "ai-career-diagnosis-dev-44beb324ab3d.json",
            )
            creds = Credentials.from_service_account_file(
                credentials_path,
                scopes=SCOPE,
            )
        client = gspread.authorize(creds)

        sheet = client.open_by_key(SPREADSHEET_ID).worksheet("job_db_v2")
        save_jobs_by_url(sheet, header_row, jobs_data)

    except Exception as e:
        print(f"スプレッドシート書き込み時にエラーが発生しました: {e}")
        raise


if __name__ == "__main__":
    scrape_and_save()