from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3896",
    "page_type": "多机构标签页内嵌人物详情",
    "structure_group": "wuzhong_government_tab_nav_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "online",
    "extract_mode": "scoped_name_duty_pairs",
    "collector": "requests",
    "parser": "page_inline_wuzhong_government_tab_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".Ld-option3-nav",
    "name_selector": ".ld-name",
    "duty_selector": ".ld-position",
    "detail_link_selector": "",
    "risk_flag": "同页静态包含市委、人大、政府、政协四套名单与详情；须严格限定第三套政府导航，不得将标签页锚点冒充详情链接",
    "confidence": "high",
    "filter_policy": "strict_structure",
}


def clean_text(value: object) -> str:
    """压缩职务文本中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """仅删除姓名字符之间的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按政府标签页左侧导航原始顺序提取姓名与明确职务。"""
    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        raise RuntimeError("未找到政府领导第三标签页导航")

    title = region.select_one(".ldzc-con-left-title")
    if clean_text(title.get_text(" ", strip=True) if title else "") != "政府领导":
        raise RuntimeError("第三标签页导航标题不是政府领导")

    rows: list[dict] = []
    seen_names: set[str] = set()
    for item in region.select("li"):
        name_node = item.select_one(".ld-name")
        duty_node = item.select_one(".ld-position")
        name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) or not duty:
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "confidence": "high",
                "parser": page_rule["parser"],
                "selector_summary": ".Ld-option3-nav政府标签页.ld-name与.ld-position",
            }
        )

    if not rows:
        raise RuntimeError("政府领导第三标签页导航未提取到有效人物")
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
