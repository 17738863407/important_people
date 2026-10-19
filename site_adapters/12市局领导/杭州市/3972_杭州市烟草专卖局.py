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
    "rule_id": "3972", "domain": "www.hangzhou.gov.cn", "page_type": "机构领导信息表格",
    "structure_group": "hangzhou_department_profile_leaders", "reuse_scope": "hangzhou_government_profile_platform",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct", "collector": "static_http",
    "parser": "page_hangzhou_profile_leaders_v1", "leader_region_selector": "#con_one_2",
    "name_selector": "table.jgzn strong[style*='font-size: 22px']", "duty_selector": "table.jgzn strong[style*='font-size: 22px']",
    "content_scope": {"include_selectors": ["#con_one_2"], "exclude_selectors": [".asd", "script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同页另列处室和区县单位，须限定领导选项卡及姓名锚点",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "#con_one_2", "record_selector": "table.jgzn", "name_anchor": "strong[style*='font-size: 22px']"}},
}


def normalize_text(value: str) -> str:
    """删除姓名和职务中的排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """以领导表22px姓名锚点定位姓名职务单元格。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#con_one_2")
    if region is None:
        raise RuntimeError("未找到机构领导选项卡 #con_one_2")
    rows: list[dict[str, str]] = []
    for table in region.select("table.jgzn"):
        strong = table.select_one("strong[style*='font-size: 22px']")
        cell = strong.find_parent("td") if strong else None
        name = normalize_text(strong.get_text(" ", strip=True) if strong else "")
        parts = [normalize_text(value) for value in cell.stripped_strings] if cell else []
        duty = "；".join(dict.fromkeys(value for value in parts if value and value != name))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name) or not duty:
            continue
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "", "parser": str(page_rule.get("parser", "")), "selector_summary": "#con_one_2中jgzn表22px姓名锚点所在单元格"})
    if not rows:
        raise RuntimeError("机构领导选项卡未解析出有效人物")
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
