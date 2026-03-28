"""
SK Careers 채용공고 스크래퍼
https://www.skcareers.com/Recruit/Index?searchText= 에서
회사명과 공고명을 추출하여 테이블 형태로 출력합니다.

Usage:
  python3 scrape_jobs.py              # 전체 공고
  python3 scrape_jobs.py --it         # IT 관련 공고만
  python3 scrape_jobs.py --markdown   # Markdown 표 출력
"""

import requests
from bs4 import BeautifulSoup
import json
import sys

BASE_URL = "https://www.skcareers.com"
LIST_URL = f"{BASE_URL}/Recruit/Index"

# IT 관련 키워드 (공고명/직무명 기준 필터링)
IT_KEYWORDS = [
    "IT", "SW", "소프트웨어", "개발", "데이터", "AI", "인공지능",
    "클라우드", "보안", "시스템", "네트워크", "인프라", "DT", "디지털",
    "플랫폼", "엔지니어링", "아키텍처", "DevOps", "SRE", "백엔드",
    "프론트엔드", "풀스택", "머신러닝", "딥러닝", "빅데이터", "분석",
    "ERP", "SAP", "CRM", "솔루션", "어플리케이션", "앱", "서비스",
    "정보", "전산", "MES", "SCM", "RPA", "자동화",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": BASE_URL,
}


def is_it_related(job: dict) -> bool:
    """공고명 또는 회사명이 IT 관련 키워드를 포함하는지 확인합니다."""
    text = (job.get("title", "") + " " + job.get("company", "")).upper()
    return any(kw.upper() in text for kw in IT_KEYWORDS)


def fetch_jobs_via_api(search_text: str = "") -> list[dict]:
    """SK Careers API를 통해 채용공고 목록을 가져옵니다."""
    api_url = f"{BASE_URL}/api/Recruit/GetRecruitList"
    payload = {
        "searchText": search_text,
        "pageIndex": 1,
        "pageSize": 200,
        "orderBy": "RECENT",
    }

    resp = requests.post(api_url, json=payload, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    jobs = []
    items = data.get("data", data.get("list", data.get("result", [])))
    if isinstance(items, list):
        for item in items:
            company = (
                item.get("companyName")
                or item.get("company")
                or item.get("corpName")
                or ""
            )
            title = (
                item.get("recruitTitle")
                or item.get("title")
                or item.get("jobTitle")
                or item.get("noticeName")
                or ""
            )
            jobs.append({"company": company.strip(), "title": title.strip()})
    return jobs


def fetch_jobs_via_html(search_text: str = "") -> list[dict]:
    """HTML 파싱을 통해 채용공고 목록을 가져옵니다."""
    session = requests.Session()

    # 메인 페이지 먼저 접근 (쿠키 획득)
    session.get(BASE_URL, headers=HEADERS, timeout=15)

    params = {"searchText": search_text}
    resp = session.get(LIST_URL, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    jobs = []

    # 다양한 CSS 선택자 시도
    selectors = [
        (".recruit-list .recruit-item", ".company-name", ".recruit-title"),
        (".job-list .job-item", ".corp-name", ".job-title"),
        (".list-item", ".company", ".title"),
        ("li.item", ".name", ".subject"),
    ]

    for container_sel, company_sel, title_sel in selectors:
        items = soup.select(container_sel)
        if items:
            for item in items:
                company_el = item.select_one(company_sel)
                title_el = item.select_one(title_sel)
                if company_el and title_el:
                    jobs.append({
                        "company": company_el.get_text(strip=True),
                        "title": title_el.get_text(strip=True),
                    })
            if jobs:
                break

    # JSON 데이터가 스크립트 태그에 포함된 경우
    if not jobs:
        for script in soup.find_all("script"):
            if script.string and "recruitList" in (script.string or ""):
                try:
                    start = script.string.index("recruitList")
                    chunk = script.string[start:]
                    bracket_start = chunk.index("[")
                    # 간단한 JSON 배열 추출
                    depth = 0
                    end = bracket_start
                    for i, ch in enumerate(chunk[bracket_start:], bracket_start):
                        if ch == "[":
                            depth += 1
                        elif ch == "]":
                            depth -= 1
                            if depth == 0:
                                end = i + 1
                                break
                    raw = chunk[bracket_start:end]
                    items = json.loads(raw)
                    for item in items:
                        jobs.append({
                            "company": item.get("companyName", item.get("company", "")),
                            "title": item.get("title", item.get("recruitTitle", "")),
                        })
                    break
                except (ValueError, KeyError):
                    continue

    return jobs


def print_table(jobs: list[dict]) -> None:
    """채용공고 목록을 표 형태로 출력합니다."""
    if not jobs:
        print("채용공고를 찾을 수 없습니다.")
        return

    # 컬럼 너비 계산
    max_company = max(len(j["company"]) for j in jobs)
    max_title = max(len(j["title"]) for j in jobs)
    max_company = max(max_company, len("회사명"))
    max_title = max(max_title, len("공고명"))

    sep = f"+{'-' * (max_company + 2)}+{'-' * (max_title + 2)}+"
    header = f"| {'회사명':<{max_company}} | {'공고명':<{max_title}} |"

    print(sep)
    print(header)
    print(sep)
    for i, job in enumerate(jobs, 1):
        print(f"| {job['company']:<{max_company}} | {job['title']:<{max_title}} |")
    print(sep)
    print(f"\n총 {len(jobs)}건의 채용공고")


def print_markdown_table(jobs: list[dict]) -> None:
    """채용공고 목록을 Markdown 표 형태로 출력합니다."""
    if not jobs:
        print("채용공고를 찾을 수 없습니다.")
        return

    print("| # | 회사명 | 공고명 |")
    print("|---|--------|--------|")
    for i, job in enumerate(jobs, 1):
        print(f"| {i} | {job['company']} | {job['title']} |")
    print(f"\n총 {len(jobs)}건의 채용공고")


def main():
    it_mode = "--it" in sys.argv
    markdown_mode = "--markdown" in sys.argv or "-m" in sys.argv

    # IT 모드일 때 searchText=IT 로 서버 측 필터링 먼저 시도
    search_text = "IT" if it_mode else ""
    label = "IT 관련 " if it_mode else ""
    print(f"SK Careers {label}채용공고를 가져오는 중...\n")

    jobs = []

    # 1단계: API 시도
    try:
        print("[1/2] API 방식으로 시도 중...")
        jobs = fetch_jobs_via_api(search_text)
        if jobs:
            print(f"  -> API에서 {len(jobs)}건 수집 완료")
    except Exception as e:
        print(f"  -> API 실패: {e}")

    # 2단계: HTML 파싱 시도
    if not jobs:
        try:
            print("[2/2] HTML 파싱 방식으로 시도 중...")
            jobs = fetch_jobs_via_html(search_text)
            if jobs:
                print(f"  -> HTML 파싱으로 {len(jobs)}건 수집 완료")
            else:
                print("  -> HTML 파싱에서도 공고를 찾지 못했습니다.")
        except Exception as e:
            print(f"  -> HTML 파싱 실패: {e}")

    # IT 모드: 클라이언트 측 키워드 필터링 (서버 결과에 누락된 경우 대비)
    if it_mode and jobs:
        before = len(jobs)
        jobs = [j for j in jobs if is_it_related(j)]
        print(f"  -> IT 키워드 필터링: {before}건 → {len(jobs)}건\n")
    else:
        print()

    if markdown_mode:
        print_markdown_table(jobs)
    else:
        print_table(jobs)


if __name__ == "__main__":
    main()
