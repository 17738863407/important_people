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
    "rule_id": "1923",
    "page_type": "人物目录详情页",
    "structure_group": "ningbo_government_directory_profiles_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "ningbo_government_directory_profiles_v2",
    "leader_region_selector": ".leader",
    "name_selector": ".leader_top a.leader-zn-detail[href], .leader_bottom .szf_name a[href]",
    "duty_selector": ".leader_intro .leader-right",
    "detail_link_selector": ".leader_top a.leader-zn-detail[href], .leader_bottom .szf_name a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_current_sentence",
        "detail_content_selector": ".leader_intro",
        "max_detail_links": 20,
    },
    "risk_flag": "详情人物区同时含分工、简历和领导活动，现任句仅在leader_intro当前人物范围内提取",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    text = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", value).strip()
    return re.sub(r"\s+([，。；：])", r"\1", text)


def _clean_evidence(value: str) -> str:
    """删除现任句的固定前缀及纯句末句号。"""
    return re.sub(r"。$", "", re.sub(r"^现任\s*", "", _clean_text(value))).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按入口目录顺序抓取详情页当前人物的完整现任句。"""
    import requests
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    links = []
    mayor_link = region.select_one(".leader_top a.leader-zn-detail[href]")
    if mayor_link is not None:
        links.append(mayor_link)
    links.extend(region.select(".leader_bottom .szf_name a[href]"))

    entry_url = final_url or page_rule["url"]
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()
    for link in links:
        name = _clean_text(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or name in seen:
            continue
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
        profile = detail_soup.select_one(
            page_rule["detail_strategy"]["detail_content_selector"]
        )
        name_node = profile.select_one(".leader-left p.name") if profile else None
        profile_name = _clean_text(name_node.get_text(" ", strip=True)) if name_node else ""
        profile_text = _clean_text(profile.get_text(" ", strip=True)) if profile else ""
        evidence_match = re.search(r"现任[^。]*。", profile_text)
        if profile_name != expected_name or evidence_match is None:
            raise RuntimeError(
                f"目录与详情现任信息无法核对：{expected_name} -> {profile_name or '空'}"
            )
        evidence = _clean_evidence(evidence_match.group(0))
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
