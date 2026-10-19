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
    "rule_id": "0750",
    "page_type": "人物目录详情页",
    "structure_group": "guiyang_government_leader_navigation_details_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page",
    "parser": "guiyang_government_leader_navigation_details_v2",
    "leader_region_selector": "#gy_lmy_left",
    "name_selector": ".main_3132[href]",
    "duty_selector": "",
    "detail_link_selector": ".main_3132[href]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_current_sentence",
        "detail_content_selector": ".main_32321",
        "max_detail_links": 50,
    },
    "risk_flag": "仅解析左侧领导导航，详情新闻和信箱链接不得作为人物候选",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    text = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value).strip()
    return re.sub(r"\s+([，。；：])", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按左侧领导导航顺序发现详情，并提取简历区域现任原句。"""
    import requests
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    links = soup.select(".main_3132[href]")
    if not links:
        return []

    entry_url = final_url or page_rule["url"]
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()
    for link in links:
        name = re.sub(
            r"[\s\u2000-\u200b\u3000\xa0]+",
            "",
            link.get_text(" ", strip=True),
        )
        if name in seen or not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
            continue
        seen.add(name)
        candidates.append((name, urljoin(entry_url, link["href"])))

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": entry_url})
    records: list[object] = []
    for name, candidate_url in candidates:
        response = session.get(candidate_url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        detail_soup = BeautifulSoup(response.text, "html.parser")
        contents = detail_soup.select(
            page_rule["detail_strategy"]["detail_content_selector"]
        )
        detail_text = _clean_text(
            " ".join(content.get_text(" ", strip=True) for content in contents)
        )
        evidence_match = re.search(r"现任[^。]*。", detail_text)
        if evidence_match is None:
            raise RuntimeError(f"人物详情简历缺少可验证的现任职务依据：{name}")
        evidence = re.sub(
            r"[\s\u2000-\u200b\u3000\xa0]+",
            "",
            evidence_match.group(0),
        ).removeprefix("现任").rstrip("。")
        detail_url = "" if response.url.rstrip("/") == entry_url.rstrip("/") else response.url
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
