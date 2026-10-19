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
    "rule_id": "3666", "page_type": "段落职务名单页",
    "structure_group": "scu_current_leader_paragraphs_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "scu_current_leader_paragraphs_v1",
    "leader_region_selector": ".ld-t1", "name_selector": "li p a",
    "duty_selector": "li p直属文本", "detail_link_selector": "li p a[href]",
    "content_scope": {"include_selectors": [".ld-t1"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "list_link_optional", "max_detail_links": 50},
    "risk_flag": "职务为人物链接前直属文本；姓名职务含字距；党委常委一人链接为#",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    """删除排版空白，并移除字段末尾冒号。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip(" ：:")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按段落DOM顺序解析职务及其人物链接，并聚合重复人物。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".ld-t1")
    if region is None:
        return []
    people: dict[str, dict[str, object]] = {}
    for group in region.select("li > p"):
        direct_text = "".join(str(node) for node in group.find_all(string=True, recursive=False))
        duty = _clean_text(direct_text)
        if not duty:
            continue
        for anchor in group.select(":scope > a"):
            name = _clean_text(anchor.get_text(" ", strip=True) or anchor.get("title", ""))
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name):
                continue
            href = str(anchor.get("href", "")).strip()
            detail_url = urljoin(final_url, href) if href and not href.startswith("#") else ""
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
            selector_summary=".ld-t1 li > p的直属职务文本与直属人物a",
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
