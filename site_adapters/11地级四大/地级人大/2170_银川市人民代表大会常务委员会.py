from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2170",
    "page_type": "人物目录详情页",
    "structure_group": "yinchuan_people_congress_directory_details_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "yinchuan_people_congress_directory_details_v2",
    "leader_region_selector": ".left3 .con > ul",
    "name_selector": "li:not(.m) > a[href]",
    "duty_selector": "li.m",
    "detail_link_selector": "li:not(.m) > a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "dynamic_current_sentence",
        "detail_content_selector": ".article .con .view",
        "max_detail_links": 50,
    },
    "risk_flag": "目录分组标签可能晚于对应人物更新，详情正文现任原句优先",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    text = re.sub(r"[\s\u3000\xa0]+", " ", value).strip()
    return re.sub(r"\s+([，。；：])", r"\1", text)


def _extract_current_sentence(soup: object, selector: str) -> str:
    content = soup.select_one(selector)
    if content is None:
        return ""
    text = _clean_text(content.get_text(" ", strip=True))
    match = re.search(r"现任[^。]*。", text)
    return re.sub(r"[\s\u3000\xa0]+", "", match.group(0)).removeprefix("现任").removesuffix("。").rstrip() if match else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """继承目录顺序，并在当前人物详情正文内动态取得现任职务依据。"""
    import requests
    from bs4 import BeautifulSoup, Comment

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    for comment in soup.find_all(string=lambda node: isinstance(node, Comment)):
        comment.extract()
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    entry_url = final_url or page_rule["url"]
    current_duty = ""
    candidates: list[tuple[str, str, str]] = []
    for item in region.find_all("li", recursive=False):
        if "m" in (item.get("class") or []):
            current_duty = _clean_text(item.get_text(" ", strip=True))
            continue
        link = item.find("a", href=True, recursive=False)
        if link is None or not current_duty:
            continue
        name = re.sub(r"[\s\u3000\xa0]+", "", link.get_text(" ", strip=True))
        if re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
            candidates.append((name, current_duty, urljoin(entry_url, link["href"])))

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    records: list[object] = []
    for name, directory_duty, candidate_url in candidates:
        evidence = ""
        detail_url = "" if candidate_url.rstrip("/") == entry_url.rstrip("/") else candidate_url
        try:
            if candidate_url.rstrip("/") == entry_url.rstrip("/"):
                detail_soup = soup
            else:
                response = session.get(candidate_url, timeout=30)
                response.raise_for_status()
                response.encoding = response.apparent_encoding or response.encoding
                detail_soup = BeautifulSoup(response.text, "html.parser")
            evidence = _extract_current_sentence(
                detail_soup,
                page_rule["detail_strategy"]["detail_content_selector"],
            )
        except requests.RequestException:
            evidence = ""
        if not evidence:
            evidence = directory_duty
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url=detail_url,
                evidence=evidence,
                confidence="high" if evidence.startswith("现任") else "medium",
                parser=page_rule["parser"],
            )
        )
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
