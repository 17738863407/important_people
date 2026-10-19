from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3057",
    "domain": "xfj.jl.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "jilin_petition_list_with_optional_profile_duty_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_jilin_petition_list_with_optional_profile_duty_v2",
    "detail_strategy": {"required": False, "mode": "empty_list_duty_to_detail"},
    "risk_flag": "增强requests误跳无障碍页并伪成功；个别列表职务为空时须读取当前人物简介",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩HTML排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def fetch_detail_html(session: requests.Session, detail_url: str) -> str:
    """直接在线抓取当前人物详情原始HTML，并有限重试。"""
    last_error: requests.RequestException | None = None
    for _ in range(3):
        try:
            response = session.get(detail_url, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            return response.text
        except requests.RequestException as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise RuntimeError("详情页在线抓取未执行")


def extract_current_duty(detail_html: str, name: str) -> tuple[str, str]:
    """只在对应人物“个人简介”区域提取完整现任句。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    scope = soup.select_one(".leader_profile > .Profile:first-of-type .text")
    if scope is None:
        return "", ""
    text = clean_text(scope.get_text(" ", strip=True))
    if name not in re.sub(r"\s+", "", text):
        return "", ""
    match = re.search(r"现任\s*([^。]+)\s*。", text)
    if match is None:
        return "", ""
    duty = re.sub(r"\s+", "", match.group(1)).strip("，,。 ")
    return (duty, duty) if duty else ("", "")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """继承领导列表顺序，列表职务为空时在线读取对应简介。"""
    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in soup.select(".listldjs li"):
        link = item.select_one("a[href]")
        if link is None:
            continue
        name = re.sub(r"\s+", "", clean_text(link.get_text(" ", strip=True)))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or name in seen:
            continue
        duty_node = item.select_one("span")
        duty = clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        evidence = duty
        detail_url = urljoin(final_url, str(link.get("href", "")))
        if not duty:
            try:
                detail_html = fetch_detail_html(session, detail_url)
            except requests.RequestException:
                continue
            duty, evidence = extract_current_duty(detail_html, name)
        if not duty:
            continue
        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")) or final_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；list=.listldjs li；"
                    "fields=a-name+span-duty；empty-duty=detail-profile-current-sentence"
                ),
            }
        )

    return records


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
