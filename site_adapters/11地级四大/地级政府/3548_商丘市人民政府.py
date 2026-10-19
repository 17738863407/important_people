from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容项目内任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3548",
    "page_type": "人物目录详情页",
    "structure_group": "shangqiu_government_directory_profiles_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page",
    "parser": "shangqiu_government_directory_profiles_v1",
    "leader_region_selector": "#mainSzfld",
    "name_selector": "#mainSzfld h3.title a[href]",
    "duty_selector": ".leaderIntro",
    "detail_link_selector": "#mainSzfld h3.title a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_current_sentence",
        "detail_name_selector": ".mHd h3.title",
        "detail_content_selector": ".leaderIntro",
        "current_sentence_pattern": r"现任.*?。",
        "max_detail_links": 20,
    },
    "risk_flag": "入口权威内容位于原始HTML；增强请求会误跟随页面模板脚本跳转到首页，职务须在各人物详情页简历版块中提取完整现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    """删除网页排版空白和不可见字符。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0\ufeff]+", "", value).strip()


def _is_same_site_detail(entry_url: str, detail_url: str) -> bool:
    """只接受当前站点领导栏目中的真实人物详情页。"""
    entry = urlparse(entry_url)
    detail = urlparse(detail_url)
    return (
        detail.scheme in {"http", "https"}
        and detail.netloc.lower() == entry.netloc.lower()
        and "/szf1/szfld/" in detail.path
        and "/content_" in detail.path
    )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按入口页DOM顺序进入详情页，从简历版块提取完整现任句。"""
    import requests
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    entry_url = final_url or page_rule["url"]
    soup = BeautifulSoup(html, "lxml")
    if soup.select_one(page_rule["leader_region_selector"]) is None:
        return []

    candidates: list[tuple[str, str]] = []
    seen_names: set[str] = set()
    seen_urls: set[str] = set()
    for link in soup.select(page_rule["name_selector"]):
        name = _clean_text(link.get_text(" ", strip=True))
        detail_url = urljoin(entry_url, str(link.get("href") or "").strip())
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
            continue
        if not _is_same_site_detail(entry_url, detail_url):
            continue
        if name in seen_names or detail_url in seen_urls:
            continue
        seen_names.add(name)
        seen_urls.add(detail_url)
        candidates.append((name, detail_url))

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/138.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": entry_url,
            "Upgrade-Insecure-Requests": "1",
        }
    )

    records: list[object] = []
    try:
        for expected_name, detail_url in candidates:
            response = session.get(detail_url, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding or "utf-8"
            detail_soup = BeautifulSoup(response.text, "lxml")

            name_node = detail_soup.select_one(
                page_rule["detail_strategy"]["detail_name_selector"]
            )
            profile_name = _clean_text(
                name_node.get_text(" ", strip=True) if name_node else ""
            )
            biography = detail_soup.select_one(
                page_rule["detail_strategy"]["detail_content_selector"]
            )
            biography_text = _clean_text(
                biography.get_text(" ", strip=True) if biography else ""
            )
            evidence_match = re.search(
                page_rule["detail_strategy"]["current_sentence_pattern"],
                biography_text,
                flags=re.DOTALL,
            )
            if profile_name != expected_name or evidence_match is None:
                raise RuntimeError(
                    f"目录与详情简历无法核对：{expected_name} -> {profile_name or '空'}"
                )

            raw_sentence = evidence_match.group(0)
            evidence = raw_sentence.removeprefix("现任").removesuffix("。").strip()
            if not evidence:
                raise RuntimeError(f"详情页现任句清洗后为空：{expected_name}")
            records.append(
                PersonRecord(
                    organization=page_rule["organization"],
                    url=page_rule["url"],
                    name=profile_name,
                    duty=evidence,
                    detail_url=response.url,
                    evidence=evidence,
                    confidence="high",
                    parser=page_rule["parser"],
                )
            )
    finally:
        session.close()
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
