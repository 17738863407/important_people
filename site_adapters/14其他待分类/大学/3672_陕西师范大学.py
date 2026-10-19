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
    "rule_id": "3672", "page_type": "分栏职务人物链接页",
    "structure_group": "snnu_leader_items_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "snnu_leader_items_v1",
    "leader_region_selector": ".m-leader", "name_selector": ".item dl a[href]",
    "duty_selector": ".item h3", "detail_link_selector": ".item dl a[href]",
    "content_scope": {"include_selectors": [".m-leader"], "exclude_selectors": []},
    "detail_strategy": {"required": True, "mode": "list_link_only", "max_detail_links": 50},
    "risk_flag": "同一人物跨党委、纪委和行政分组重复，姓名含全角排版空格",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def _compact(value: str) -> str:
    return re.sub(r"[\s\u2002\u2003\u3000\xa0]+", "", value).strip("：:")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """逐个职务 item 读取人物，并按首次展示顺序合并职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".m-leader")
    if region is None:
        return []
    people: dict[str, dict[str, object]] = {}
    for item in region.select(".item"):
        duty_node = item.select_one("h3")
        duty = _compact(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not duty:
            continue
        for anchor in item.select("dl a[href]"):
            name = _compact(anchor.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name):
                continue
            detail_url = urljoin(final_url, str(anchor.get("href", "")).strip())
            person = people.setdefault(name, {"duties": [], "detail_url": detail_url})
            if duty not in person["duties"]:
                person["duties"].append(duty)
            if not person["detail_url"]:
                person["detail_url"] = detail_url
    return [PersonRecord(
        organization=page_rule["organization"], url=page_rule["url"], name=name,
        duty="；".join(data["duties"]), detail_url=data["detail_url"], evidence="；".join(data["duties"]),
        confidence="high", parser=page_rule["parser"], selector_summary=".m-leader内.item的h3职务与dl人物链接",
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
