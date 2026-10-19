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
    "rule_id": "1993",
    "page_type": "职务分组名单页",
    "structure_group": "主要领导分号分组字段",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "NraDepartmentSemicolonLeaderGroupsParser_v2",
    "leader_region_selector": ".nsjg_wrap .list_main",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同一区域另含部门职责、内设处室和信访指南，必须仅解析主要领导卡片并保持分组顺序",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ").replace("\u3000", " ")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按主要领导卡片中的分号分组顺序抽取职务与姓名。"""
    soup = BeautifulSoup(html, "html.parser")
    leader_card = None
    for card in soup.select(".nsjg_wrap .list_main"):
        title = card.select_one(".mobile_list_titles2")
        if title and _clean_text(title.get_text(" ", strip=True)) == "主要领导":
            leader_card = card
            break
    if leader_card is None:
        raise RuntimeError("未找到标题为主要领导的机构卡片")

    text_node = leader_card.select_one(".mobile_list_text1")
    raw_text = _clean_text(text_node.get_text(" ", strip=True)) if text_node else ""
    groups = [_clean_text(part) for part in re.split(r"[；;]", raw_text) if _clean_text(part)]
    records: list[dict] = []
    for group in groups:
        match = re.fullmatch(r"(?P<duty>[^：:]+)\s*[：:]\s*(?P<name>[\u4e00-\u9fff·\s]{2,8})", group)
        if not match:
            raise RuntimeError(f"主要领导分组无法解析：{group}")
        name = re.sub(r"\s+", "", match.group("name"))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
            raise RuntimeError(f"主要领导姓名格式异常：{name}")
        records.append(
            {
                "name": name,
                "duty": _clean_text(match.group("duty")),
                "evidence": _clean_text(match.group("duty")),
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": ".nsjg_wrap .list_main；主要领导标题；分号分组",
            }
        )
    if not records:
        raise RuntimeError("主要领导卡片未解析到人物记录")
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
