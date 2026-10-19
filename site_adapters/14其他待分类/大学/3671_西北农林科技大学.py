from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3671", "page_type": "职务分组领导链接页",
    "structure_group": "nwsuaf_leader_group_boxes_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "nwsuaf_leader_group_boxes_v1",
    "leader_region_selector": ".sub_013", "name_selector": ".box .right a",
    "duty_selector": ".box .left", "detail_link_selector": ".box .right a[href]",
    "content_scope": {"include_selectors": [".sub_013"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "list_link_only", "max_detail_links": 50},
    "risk_flag": "党委常委组链接缺少href，页面还含一个无人员的空职务组",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def _compact(value: str) -> str:
    """清理姓名字距、全角空格和纯排版空白。"""
    return re.sub(r"[\s\u2002\u2003\u3000\xa0]+", "", value).strip("：:")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """逐个职务分组读取人员，并按首次出现次序合并重复人物职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".sub_013")
    if region is None:
        return []
    people: dict[str, dict[str, object]] = {}
    for box in region.select(".box"):
        duty_node = box.select_one(".left")
        right = box.select_one(".right")
        duty = _compact(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not duty or right is None:
            continue
        for anchor in right.select("a"):
            name = _compact(anchor.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name):
                continue
            href = str(anchor.get("href", "")).strip()
            detail_url = urljoin(final_url, href) if href and not href.startswith(("#", "javascript:", "mailto:")) else ""
            person = people.setdefault(name, {"duties": [], "detail_url": detail_url})
            if duty not in person["duties"]:
                person["duties"].append(duty)
            if not person["detail_url"] and detail_url:
                person["detail_url"] = detail_url

    return [
        PersonRecord(
            organization=page_rule["organization"], url=page_rule["url"], name=name,
            duty="；".join(person["duties"]), detail_url=person["detail_url"],
            evidence="；".join(person["duties"]), confidence="high", parser=page_rule["parser"],
            selector_summary=".sub_013内逐个.box的.left职务与.right人物链接",
        ) for name, person in people.items()
    ]


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
