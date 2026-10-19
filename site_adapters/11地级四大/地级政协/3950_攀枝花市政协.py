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
    "rule_id": "3950",
    "domain": "www.pzhzx.gov.cn",
    "page_type": "领导图文名单",
    "structure_group": "panzhihua_cppcc_leader_blocks",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_panzhihua_cppcc_blocks_v1",
    "leader_region_selector": ".neirong4",
    "name_selector": ".ld-zhuxi2, .ld-fuzhuxi2, .ld-mishuzhang2",
    "duty_selector": ".ld-zhuxi2, .ld-fuzhuxi2, .ld-mishuzhang2",
    "content_scope": {"include_selectors": [".neirong4"], "exclude_selectors": [".ld-changwei", "script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同页标题包含常务委员名单，必须仅取主席、副主席和秘书长专属文本类",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".neirong4",
            "record_selector": ".ld-zhuxi2, .ld-fuzhuxi2, .ld-mishuzhang2",
        },
        "api": {"enabled": False, "reason": "静态HTML专属领导文本类已直接包含职务和姓名"},
    },
}


def normalize_text(value: str) -> str:
    """删除字段中的排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按主席、副主席、秘书长专属文本节点的DOM顺序提取。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".neirong4")
    if region is None:
        raise RuntimeError("未找到领导名单区域 .neirong4")
    rows: list[dict[str, str]] = []
    pattern = re.compile(r"^(主席|副主席|秘书长)[：:](.+)$")
    for node in region.select(".ld-zhuxi2, .ld-fuzhuxi2, .ld-mishuzhang2"):
        text = normalize_text(node.get_text(" ", strip=True))
        match = pattern.fullmatch(text)
        if not match:
            continue
        duty, name = match.groups()
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name):
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".neirong4内主席、副主席、秘书长专属文本节点",
            }
        )
    if not rows:
        raise RuntimeError("领导名单区域未解析出有效人物")
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
