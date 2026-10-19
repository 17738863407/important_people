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
    "rule_id": "0455",
    "page_type": "人物目录详情页",
    "structure_group": "dalian_government_leader_groups_details_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "dalian_government_leader_groups_details_v2",
    "leader_region_selector": ".leader-box",
    "name_selector": ".leader-list li a[href] span",
    "duty_selector": ".leader-list .leader-title",
    "detail_link_selector": ".leader-list li a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_current_sentence",
        "detail_content_selector": ".zolt .p1",
        "max_detail_links": 50,
    },
    "risk_flag": "列表分组提供简职，完整现任职务以人物详情个人简介为准",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    text = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value).strip()
    return re.sub(r"\s+([，。；：])", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按领导分组DOM顺序发现详情，并提取个人简介中的现任原句。"""
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
    for group in region.select(".leader-list"):
        role_node = group.select_one(".leader-title")
        if role_node is None or not _clean_text(role_node.get_text(" ", strip=True)):
            continue
        for link in group.select("li a[href]"):
            name_node = link.select_one("span")
            name = (
                re.sub(
                    r"[\s\u2000-\u200b\u3000\xa0]+",
                    "",
                    name_node.get_text(" ", strip=True),
                )
                if name_node is not None
                else ""
            )
            href = str(link.get("href") or "").strip()
            if name in seen or not href or not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
                continue
            seen.add(name)
            candidates.append((name, urljoin(entry_url, href)))

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    records: list[object] = []
    for name, detail_url in candidates:
        response = session.get(detail_url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        detail_soup = BeautifulSoup(response.text, "html.parser")
        content = detail_soup.select_one(
            page_rule["detail_strategy"]["detail_content_selector"]
        )
        detail_text = _clean_text(content.get_text(" ", strip=True)) if content else ""
        evidence_match = re.search(r"现任[^。]*。", detail_text)
        if evidence_match is None:
            raise RuntimeError(f"人物详情简介缺少可验证的现任职务依据：{name}")
        evidence = re.sub(
            r"[\s\u2000-\u200b\u3000\xa0]+",
            "",
            evidence_match.group(0),
        )
        evidence = re.sub(r"^现任\s*", "", evidence)
        evidence = re.sub(r"[（(]\s*挂职\s*[）)]", "", evidence).removesuffix("。").strip()
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
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
