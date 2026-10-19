from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3924",
    "page_type": "人物卡片双字段",
    "structure_group": "anqing_cppcc_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "raw_http",
    "_fetch_mode_override": True,
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "page_inline_anqing_cppcc_cards_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".leader-pic",
    "name_selector": ".leaderPic-list li a p span:nth-of-type(1)",
    "duty_selector": ".leaderPic-list li a p span:nth-of-type(2)",
    "detail_link_selector": "none_javascript_modal",
    "risk_flag": "人物入口为javascript弹层函数，不能作为真实详情URL",
    "confidence": "high",
}


def clean_text(value: object) -> str:
    """压缩网页排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """删除姓名中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按三个卡片列表及li顺序读取姓名、职务强字段。"""
    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one(".leader-pic")
    if region is None or "政协领导" not in clean_text(region.get_text(" ", strip=True)):
        raise RuntimeError("未定位到政协领导卡片区域")

    rows: list[dict] = []
    seen_names: set[str] = set()
    for card in region.select("ul.leaderPic-list > li"):
        fields = card.select("a p > span")
        if len(fields) < 2:
            continue
        name = clean_name(fields[0].get_text(" ", strip=True))
        evidence = clean_text(fields[1].get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) or not evidence:
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "confidence": "high",
                "parser": page_rule["parser"],
                "selector_summary": ".leader-pic内leaderPic-list卡片双span字段",
            }
        )

    if not rows:
        raise RuntimeError("政协领导卡片区域未提取到有效人物")
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
