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
    "rule_id": "2099",
    "page_type": "人物目录详情页",
    "structure_group": "zhengzhou_government_directory_profiles_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "zhengzhou_government_directory_profiles_v2",
    "leader_region_selector": ".common-box",
    "name_selector": ".leader-list dd a[href] > span",
    "duty_selector": ".box-leader-info .box-view > span",
    "detail_link_selector": ".leader-list dd a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_profile_fields",
        "detail_content_selector": ".box-leader-info .box-view",
        "max_detail_links": 20,
    },
    "risk_flag": "入口页只列姓名，完整现任职务位于独立人物页box-view字段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_name(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", value).strip()


def _clean_duty(value: str) -> str:
    text = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value).strip()
    return re.sub(r"\s+([，。；：])", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按市政府领导卡片顺序抓取详情页姓名和职务字段。"""
    import requests
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = next(
        (
            box
            for box in soup.select(page_rule["leader_region_selector"])
            if "市政府领导" in box.get_text(" ", strip=True)
        ),
        None,
    )
    if region is None:
        return []

    entry_url = final_url or page_rule["url"]
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()
    for link in region.select(".leader-list dd a[href]"):
        name_node = link.select_one(":scope > span")
        name = _clean_name(name_node.get_text(" ", strip=True)) if name_node else ""
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
        field = detail_soup.select_one(
            page_rule["detail_strategy"]["detail_content_selector"]
        )
        name_node = field.select_one(":scope > em") if field else None
        duty_node = field.select_one(":scope > span") if field else None
        profile_name = _clean_name(name_node.get_text(" ", strip=True)) if name_node else ""
        evidence = _clean_duty(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if profile_name != expected_name or not evidence:
            raise RuntimeError(
                f"目录与详情字段无法核对：{expected_name} -> {profile_name or '空'}"
            )
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
