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
    "rule_id": "3981", "domain": "www.chinabdh.com", "page_type": "JavaScript纵向领导选项卡",
    "structure_group": "chinabdh_management_tabs", "reuse_scope": "single_page",
    "load_mode": "JavaScript渲染", "fetch_mode": "online", "force_browser": True,
    "extract_mode": "list_direct", "collector": "playwright",
    "parser": "page_chinabdh_management_tabs_v1", "leader_region_selector": ".site_tabs",
    "name_selector": ".site_tabs_nav .tab_picture_text", "duty_selector": ".tab_pane_item .fk-editor",
    "content_scope": {"include_selectors": [".site_tabs"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "普通HTTP被WAF拦截，须浏览器渲染；人物选项卡正文含分工简历，职务只取标题卡",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"name_selector": ".site_tabs_nav .tab_picture_text", "pane_selector": ".site_tabs_pane .tab_pane_item"}},
}


def normalize_text(value: str) -> str:
    """清理渲染文本中的纯排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "").strip("。；; ")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按导航与内容面板索引配对，从人物标题卡提取姓名和现职。"""
    soup = BeautifulSoup(html, "html.parser")
    names = [normalize_text(node.get_text(" ", strip=True)) for node in soup.select(".site_tabs_nav .tab_picture_text")]
    panes = soup.select(".site_tabs_pane .tab_pane_item")
    rows: list[dict[str, str]] = []
    for name, pane in zip(names, panes):
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name):
            continue
        duty = ""
        for editor in pane.select(".fk-editor"):
            text = normalize_text(editor.get_text(" ", strip=True))
            if text.startswith(name) and not text.startswith(name + "【"):
                candidate = text[len(name):]
                if candidate and "【" not in candidate:
                    duty = candidate
                    break
        if not duty:
            raise RuntimeError(f"人物面板未取得标题卡职务：{name}")
        rows.append({
            "name": name, "duty": duty, "evidence": duty, "detail_url": "",
            "parser": str(page_rule.get("parser", "")), "selector_summary": "选项卡导航姓名→同序内容面板标题卡",
        })
    if not rows or len(rows) != len(names):
        raise RuntimeError(f"领导选项卡解析不完整：导航{len(names)}人，结果{len(rows)}人")
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
