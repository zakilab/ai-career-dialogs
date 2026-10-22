import random
import re
import time
import unicodedata
from google.oauth2.service_account import Credentials
import gspread
from bs4 import BeautifulSoup
import requests

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


def scrape_and_save():
    session = requests.Session()
    jobs_data = []

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
    ]

    try:
        SCOPE = ["https://www.googleapis.com/auth/spreadsheets"]
        SERVICE_ACCOUNT_FILE = "ai-career-diagnosis-dev-44beb324ab3d.json"
        SPREADSHEET_ID = ""

        creds = Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPE
        )
        client = gspread.authorize(creds)

        sheet = client.open_by_key(SPREADSHEET_ID).worksheet("job_db")

        all_values = sheet.get_all_values()
        has_data = any(any(cell.strip() for cell in row) for row in all_values)

        if not has_data:
            sheet.append_row(header_row)

        if jobs_data:
            sheet.append_rows(jobs_data)
            print("Googleスプレッドシートへの書き込みが完了しました！")
        else:
            print("追加するデータがありませんでした。")

    except Exception as e:
        print(f"スプレッドシート書き込み時にエラーが発生しました: {e}")


if __name__ == "__main__":
    scrape_and_save()