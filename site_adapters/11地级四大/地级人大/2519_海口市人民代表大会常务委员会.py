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
    "rule_id": "2519",
    "page_type": "人物目录详情页",
    "structure_group": "haikou_people_congress_directory_details_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "haikou_people_congress_directory_details_v2",
    "leader_region_selector": 'a[href^="./"][href$=".shtml"], a[href*="/zrzc/"][href$=".shtml"]',
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": 'a[href^="./"][href$=".shtml"], a[href*="/zrzc/"][href$=".shtml"]',
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_current_sentence_or_latest_resume_line",
        "detail_content_selector": ".trs_editor_view, .TRS_UEDITOR.TRS_WEB",
        "max_detail_links": 50,
    },
    "risk_flag": "详情页并存新旧编辑器结构，必须在人物正文内取得现任句或最新履历行",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    text = re.sub(r"[\s\u3000\xa0]+", " ", value).strip()
    return re.sub(r"\s+([，。；：])", r"\1", text)


def _extract_evidence(soup: object, selector: str) -> str:
    content = soup.select_one(selector)
    if content is None:
        return ""
    text = _clean_text(content.get_text(" ", strip=True))
    current = re.search(r"现任[^。]*(?:。|$)", text)
    if current:
        return re.sub(r"[\s\u3000\xa0]+", "", current.group(0)).removeprefix("现任").removesuffix("。").replace("（兼）", "").replace("(兼)", "")
    latest_line = re.search(
        r"\d{4}\.\d{2}\s*--\s*(?:至今\s*)?海口市人大常委会[^。]*。?",
        text,
    )
    return _clean_text(latest_line.group(0)).removesuffix("。") if latest_line else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按主任之窗目录顺序发现详情页并提取当前职务证据。"""
    import requests
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    entry_url = final_url or page_rule["url"]
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(page_rule["detail_link_selector"]):
        name = _clean_text(link.get_text(" ", strip=True)).replace(" ", "")
        if name in seen or not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
            continue
        seen.add(name)
        candidates.append((name, urljoin(entry_url, link["href"])))

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    records: list[object] = []
    for name, detail_url in candidates:
        response = session.get(detail_url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        detail_soup = BeautifulSoup(response.text, "html.parser")
        evidence = _extract_evidence(
            detail_soup,
            page_rule["detail_strategy"]["detail_content_selector"],
        )
        if not evidence:
            raise RuntimeError(f"人物详情正文缺少可验证的现任职务依据：{name}")
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url=detail_url,
                evidence=evidence,
                confidence="high",
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
