from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, NavigableString, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3673", "page_type": "跨单元格职务人物混排页",
    "structure_group": "xidian_profile_leader_table_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "xidian_profile_leader_table_v1",
    "leader_region_selector": ".Profile_left_div", "name_selector": ".Profile_left_content a[href]",
    "duty_selector": ".Profile_left_content td", "detail_link_selector": ".Profile_left_content a[href]",
    "content_scope": {"include_selectors": [".Profile_left_div"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "list_link_only", "max_detail_links": 50},
    "risk_flag": "党委常委末两人无链接，职务标签与姓名跨段落延续且含多种字距空白",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def _compact(value: str) -> str:
    return re.sub(r"[\s\u2002\u2003\u3000\xa0]+", "", value)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """定位标题为现任领导的区块，沿单元格文本流继承当前职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = next((node for node in soup.select(".Profile_left_div")
                   if _compact((node.select_one(".Profile_left_title") or node).get_text(" ", strip=True)) == "现任领导"), None)
    if region is None:
        return []
    table = region.select_one(".Profile_left_content table")
    if table is None:
        return []
    allowed_duties = {"党委书记", "党委副书记", "纪委书记", "校长", "副校长", "党委常委"}
    people: dict[str, dict[str, object]] = {}

    def add_person(name: str, duty: str, href: str = "") -> None:
        cleaned = _compact(name)
        if duty not in allowed_duties or not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", cleaned):
            return
        detail_url = urljoin(final_url, href) if href else ""
        person = people.setdefault(cleaned, {"duties": [], "detail_url": detail_url})
        if duty not in person["duties"]:
            person["duties"].append(duty)
        if not person["detail_url"] and detail_url:
            person["detail_url"] = detail_url

    for cell in table.select("td"):
        if cell.find_parent("td") is not None:
            continue
        current_duty = ""
        for node in cell.descendants:
            if isinstance(node, Tag) and node.name == "a":
                add_person(node.get_text(" ", strip=True), current_duty, str(node.get("href", "")).strip())
            elif isinstance(node, NavigableString) and node.parent and node.parent.name != "a":
                raw = str(node)
                compact = _compact(raw)
                if not compact:
                    continue
                if "：" in compact or ":" in compact:
                    label = re.split(r"[：:]", compact, maxsplit=1)[0]
                    if label in allowed_duties:
                        current_duty = label
                    continue
                if current_duty:
                    normalized = re.sub(r"[\u2002\u2003\u3000\xa0\s]+", " ", raw)
                    for candidate in re.findall(r"[\u3400-\u9fff·]{2,15}", normalized):
                        add_person(candidate, current_duty)

    return [PersonRecord(
        organization=page_rule["organization"], url=page_rule["url"], name=name,
        duty="；".join(data["duties"]), detail_url=data["detail_url"], evidence="；".join(data["duties"]),
        confidence="high", parser=page_rule["parser"], selector_summary="现任领导.Profile_left_div内表格按文本流继承职务",
    ) for name, data in people.items()]


def main(update_fetch_memory: bool) -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=update_fetch_memory)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    update_fetch_memory = False
    main(update_fetch_memory)
