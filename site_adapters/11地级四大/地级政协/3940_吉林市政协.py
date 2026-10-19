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
    "rule_id": "3940",
    "domain": "www.jlszx.gov.cn",
    "page_type": "分组头像名单",
    "structure_group": "jilin_city_cppcc_leader_groups_2026",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_jilin_city_cppcc_leader_groups_v1",
    "leader_region_selector": ".zxjj .ldzp",
    "name_selector": ".ldzp_right li a span",
    "duty_selector": ".ldzp_left .ldzp_name",
    "detail_link_selector": "",
    "content_scope": {"include_selectors": [".zxjj"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "主席和旧秘书长姓名只存在HTML注释，当前有效DOM主席组为空，人物锚点无href",
    "confidence": "medium",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "group_selector": ".zxjj .ldzp",
            "duty_selector": ".ldzp_left .ldzp_name",
            "name_selector": ".ldzp_right li a span",
        },
        "api": {"enabled": False, "reason": "当前静态HTML有效DOM已含职务分组和姓名"},
    },
}


def normalize_text(value: str) -> str:
    """清理分组字段中的排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """仅从有效DOM的领导分组提取姓名，不读取HTML注释。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for group in soup.select(".zxjj .ldzp"):
        heading = group.select_one(".ldzp_left .ldzp_name")
        duty = normalize_text(heading.get_text(" ", strip=True) if heading else "")
        if duty not in {"主席", "副主席", "秘书长"}:
            continue
        for node in group.select(".ldzp_right li a span"):
            name = normalize_text(node.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or name in seen:
                continue
            seen.add(name)
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": "",
                    "parser": str(page_rule.get("parser", "")),
                    "selector_summary": ".zxjj .ldzp有效DOM；ldzp_name职务 + li a span姓名",
                }
            )
    if not rows:
        raise RuntimeError("政协领导有效DOM未解析出姓名")
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
