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
    "rule_id": "0213",
    "page_type": "人物目录详情页",
    "structure_group": "changsha_government_structured_profiles_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "changsha_government_structured_profiles_v2",
    "leader_region_selector": "#list .right_list > ul",
    "name_selector": "li",
    "duty_selector": "",
    "detail_link_selector": 'li > a[href*="t20"]',
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_structured_profile",
        "detail_region_selector": ".wrap_right",
        "profile_label": "简历",
        "max_detail_links": 50,
    },
    "risk_flag": "列表姓名是空锚点后的li直接文本，详情工作分工不得混入现任职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    text = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value).strip()
    return re.sub(r"\s+([，。；：])", r"\1", text)


def _field_value(region: object, label: str) -> str:
    for group in region.select("dl"):
        values = [_clean_text(node.get_text(" ", strip=True)) for node in group.find_all("dd")]
        if len(values) >= 2 and re.sub(r"\s+", "", values[0]) == label:
            return values[1]
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按列表li顺序发现详情，并在结构化简历字段内提取现任原句。"""
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
    for item in region.find_all("li", recursive=False):
        link = item.select_one('a[href*="t20"]')
        if link is None:
            continue
        name = re.sub(
            r"[\s\u2000-\u200b\u3000\xa0]+",
            "",
            item.get_text(" ", strip=True),
        )
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
        detail_region = detail_soup.select_one(
            page_rule["detail_strategy"]["detail_region_selector"]
        )
        profile = (
            _field_value(detail_region, page_rule["detail_strategy"]["profile_label"])
            if detail_region is not None
            else ""
        )
        evidence_match = re.search(r"现任[^。]*。", profile)
        if evidence_match is None:
            raise RuntimeError(f"人物详情简历字段缺少可验证的现任职务依据：{name}")
        evidence = re.sub(
            r"[\s\u2000-\u200b\u3000\xa0]+",
            "",
            evidence_match.group(0),
        )
        evidence = re.sub(r"^现任\s*", "", evidence)
        evidence = re.sub(r"[。．]\s*$", "", evidence)
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
