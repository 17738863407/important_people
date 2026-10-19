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
    "rule_id": "1409",
    "page_type": "职务分组详情页",
    "structure_group": "lasa_government_ordered_lists_profiles_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "lasa_government_ordered_lists_profiles_v2",
    "leader_region_selector": ".zfxxgk-right .zfxxgk-nr",
    "name_selector": "领导信息标题后的前三个ul.jgjj-list li a[href]",
    "duty_selector": "详情页p.zwxm span",
    "detail_link_selector": "领导信息标题后的前三个ul.jgjj-list li a[href]",
    "content_scope": {
        "start_anchor": "领导信息",
        "end_anchor": "机构职能",
    },
    "detail_strategy": {
        "required": False,
        "mode": "dynamic_profile_field_with_group_fallback",
        "detail_content_selector": "p.zwxm",
        "max_detail_links": 30,
    },
    "risk_flag": "领导分组标题仅保留在页面模板注释中，且部分当前人物链接返回404；失效链接必须留空",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", value).strip()


def _is_section_title(node: object, title: str) -> bool:
    return bool(
        getattr(node, "name", None) == "div"
        and "zfxxgk-nr-tlt" in (node.get("class") or [])
        and _clean_text(node.get_text(" ", strip=True)) == title
    )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按领导信息前三组顺序解析，并验证可用详情页的现任职务字段。"""
    import requests
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    leader_title = next(
        (
            node
            for node in region.select(".zfxxgk-nr-tlt")
            if _clean_text(node.get_text(" ", strip=True)) == "领导信息"
        ),
        None,
    )
    if leader_title is None:
        return []

    group_lists = []
    for sibling in leader_title.find_next_siblings():
        if _is_section_title(sibling, "机构职能"):
            break
        if (
            getattr(sibling, "name", None) == "ul"
            and "jgjj-list" in (sibling.get("class") or [])
        ):
            group_lists.append(sibling)
    if len(group_lists) < 3:
        return []

    entry_url = final_url or page_rule["url"]
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": entry_url})
    records: list[object] = []
    seen: set[str] = set()
    for group_duty, group in zip(("市长", "副市长", "秘书长"), group_lists[:3]):
        for link in group.select("li a[href]"):
            name = _clean_text(link.get("title") or link.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or name in seen:
                continue
            seen.add(name)
            candidate_url = urljoin(entry_url, link["href"])
            verified_detail_url = ""
            evidence = group_duty
            try:
                response = session.get(candidate_url, timeout=30)
                if response.ok:
                    response.encoding = response.apparent_encoding or response.encoding
                    detail_soup = BeautifulSoup(response.text, "html.parser")
                    field = detail_soup.select_one(
                        page_rule["detail_strategy"]["detail_content_selector"]
                    )
                    spans = field.find_all("span", recursive=False) if field else []
                    profile_name = _clean_text(spans[0].get_text(" ", strip=True)) if spans else ""
                    profile_duty = _clean_text(spans[1].get_text(" ", strip=True)) if len(spans) > 1 else ""
                    if profile_name == name and profile_duty:
                        evidence = profile_duty
                        verified_detail_url = response.url
            except requests.RequestException:
                pass

            records.append(
                PersonRecord(
                    organization=page_rule["organization"],
                    url=page_rule["url"],
                    name=name,
                    duty=evidence,
                    detail_url=verified_detail_url,
                    evidence=evidence,
                    confidence="high" if verified_detail_url else "medium",
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
