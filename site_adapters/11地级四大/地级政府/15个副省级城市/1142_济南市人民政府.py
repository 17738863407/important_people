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
    "rule_id": "1142",
    "page_type": "职务分组名单页",
    "structure_group": "jinan_government_grouped_leader_links_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "jinan_government_grouped_leader_links_v2",
    "leader_region_selector": ".lingdao",
    "name_selector": ".szfld li > a[href], .fszmsz ul li > a[href], .fszmsz > a[href]",
    "duty_selector": ".szfld li > span, .fszmsz > span, .fszmsz > p.msz",
    "detail_link_selector": ".szfld li > a[href], .fszmsz ul li > a[href], .fszmsz > a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "dynamic_group_links",
        "max_detail_links": 20,
    },
    "risk_flag": "市长卡片另含简历和分工锚点，领导区域下另有政府报告和会议链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按市长、副市长、秘书长分组的网页顺序解析人物链接。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    groups: list[tuple[str, list[object]]] = []
    mayor_link = region.select_one(".szfld li > a[href]")
    if mayor_link is not None:
        groups.append(("市长", [mayor_link]))
    groups.append(("副市长", list(region.select(".fszmsz ul li > a[href]"))))
    secretary_link = region.select_one(".fszmsz > a[href]")
    if secretary_link is not None:
        groups.append(("秘书长", [secretary_link]))

    entry_url = final_url or page_rule["url"]
    records: list[object] = []
    seen: set[str] = set()
    for duty, links in groups:
        for link in links:
            name = _clean_text(link.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or name in seen:
                continue
            seen.add(name)
            records.append(
                PersonRecord(
                    organization=page_rule["organization"],
                    url=page_rule["url"],
                    name=name,
                    duty=duty,
                    detail_url=urljoin(entry_url, link["href"]),
                    evidence=duty,
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
