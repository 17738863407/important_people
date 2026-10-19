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
    "rule_id": "3690", "page_type": "领导姓名职务卡片页",
    "structure_group": "cstid_center_leader_cards_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "cstid_center_leader_cards_v1",
    "leader_region_selector": ".leader-list", "name_selector": ".leader-item-name",
    "duty_selector": ".leader-item-job", "detail_link_selector": "",
    "content_scope": {"include_selectors": [".leader-list"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 0},
    "risk_flag": "源码含一条注释掉的历史人物卡片，现有卡片链接均为javascript占位",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def _clean(value: str) -> str:
    return re.sub(r"[\s\u2002\u2003\u3000\xa0]+", "", value)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """仅解析当前DOM中的领导卡片，HTML注释不会成为候选节点。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".leader-list")
    if region is None:
        return []
    rows: list[object] = []
    for card in region.select(":scope > .leader-item"):
        name_node = card.select_one(".leader-item-name")
        duty_node = card.select_one(".leader-item-job")
        name = _clean(name_node.get_text(" ", strip=True)) if name_node else ""
        raw_duty = _clean(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name) or not raw_duty:
            continue
        duties = [_clean(item) for item in re.split(r"[、；;]", raw_duty) if _clean(item)]
        rows.append(PersonRecord(
            organization=page_rule["organization"], url=page_rule["url"], name=name,
            duty="；".join(duties), detail_url="", evidence="；".join(duties), confidence="high",
            parser=page_rule["parser"], selector_summary=".leader-list直属.leader-item姓名与职务字段",
        ))
    return rows


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
