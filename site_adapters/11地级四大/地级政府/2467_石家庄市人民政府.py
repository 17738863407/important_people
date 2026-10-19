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
    "rule_id": "2467",
    "page_type": "人物目录详情页",
    "structure_group": "shijiazhuang_government_cards_profiles_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "shijiazhuang_government_cards_profiles_v2",
    "leader_region_selector": ".zcnrbd",
    "name_selector": "a.ldejhv .ldejbgwz2, .ldejbgs .ldejbgwz2s a.ldejhvs[href]",
    "duty_selector": "#jszc",
    "detail_link_selector": "a.ldejhv[href], .ldejbgs .ldejbgwz2s a.ldejhvs[href]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_current_sentence",
        "detail_content_selector": "#jszc",
        "max_detail_links": 20,
    },
    "risk_flag": "首两名领导与其余领导使用两套卡片类名，页面另有三个非领导数据iframe",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按两类领导卡片的网页顺序抓取详情页完整现任句。"""
    import requests
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    entry_url = final_url or page_rule["url"]
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()
    for link in region.select("a.ldejhv[href]"):
        name_node = link.select_one(".ldejbgwz2")
        name = _clean_text(name_node.get_text(" ", strip=True)) if name_node else ""
        if re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) and name not in seen:
            seen.add(name)
            candidates.append((name, urljoin(entry_url, link["href"])))
    for card in region.select("div.ldejbgs"):
        link = card.select_one(".ldejbgwz2s a.ldejhvs[href]")
        name = _clean_text(link.get_text(" ", strip=True)) if link else ""
        if link and re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) and name not in seen:
            seen.add(name)
            candidates.append((name, urljoin(entry_url, link["href"])))

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": entry_url})
    records: list[object] = []
    for expected_name, detail_url in candidates:
        response = session.get(detail_url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        detail_soup = BeautifulSoup(response.text, "html.parser")
        biography = detail_soup.select_one(
            page_rule["detail_strategy"]["detail_content_selector"]
        )
        biography_text = _clean_text(biography.get_text(" ", strip=True)) if biography else ""
        evidence_match = re.search(r"现任[^。]*。", biography_text)
        if expected_name not in biography_text or evidence_match is None:
            raise RuntimeError(f"人物详情现任信息无法核对：{expected_name}")
        evidence = re.sub(r"^现任\s*", "", evidence_match.group(0))
        evidence = re.sub(r"[（(]\s*挂职\s*[）)]", "", evidence)
        evidence = evidence.strip(" ，,。；;：: ")
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=expected_name,
                duty=evidence,
                detail_url=response.url,
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
