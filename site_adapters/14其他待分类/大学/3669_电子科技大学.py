from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3669", "page_type": "交互式职务名单页",
    "structure_group": "uestc_current_leader_list_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "uestc_current_leader_list_v1",
    "leader_region_selector": ".leader-list", "name_selector": ".leader-item ul.leaders > li[data-id]",
    "duty_selector": ".leader-item .position", "detail_link_selector": "",
    "content_scope": {"include_selectors": [".leader-list"], "exclude_selectors": [".leader-detail-content"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "详情区含历史履历及桌面移动重复；名单人物为交互节点而非独立链接",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    """删除姓名和职务中的纯排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """仅解析当前领导名单区，排除含历史履历的详情展示区。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".leader-list")
    if region is None:
        return []
    people: dict[str, list[str]] = {}
    for group in region.select(".leader-item > div"):
        duty_node = group.select_one(":scope > .position")
        duty = _clean_text(duty_node.get_text(" ", strip=True)) if duty_node is not None else ""
        for node in group.select(":scope > ul.leaders > li[data-id]"):
            name = _clean_text(node.get_text(" ", strip=True))
            if not duty or not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name):
                continue
            duties = people.setdefault(name, [])
            if duty not in duties:
                duties.append(duty)
    return [
        PersonRecord(
            organization=page_rule["organization"], url=page_rule["url"], name=name,
            duty="；".join(duties), detail_url="", evidence="；".join(duties),
            confidence="high", parser=page_rule["parser"],
            selector_summary=".leader-list .leader-item > div中的.position与ul.leaders > li[data-id]",
        ) for name, duties in people.items()
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
