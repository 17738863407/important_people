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
    "rule_id": "2794",
    "page_type": "人物列表完整页",
    "structure_group": "yunnan_sports_article_duty_name_lines",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_yunnan_sports_article_duty_name_lines_v2",
    "leader_region_selector": "body内来源与打印锚点之间的文章正文",
    "name_selector": "正文行冒号后文本",
    "duty_selector": "正文行冒号前文本",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "来源：本站",
        "end_anchor": "打印页面",
        "include_selectors": ["正文锚点之间的非空文本行"],
        "exclude_selectors": ["页眉", "导航", "打印控件", "友情链接", "页脚"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "权威业务页面当前返回404；仅保留来源与打印锚点间结构明确的职务：姓名行，不使用历史名单兜底",
    "confidence": "medium",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "body内来源与打印锚点之间的文章正文",
            "name_selector": "正文行冒号后文本",
            "duty_selector": "正文行冒号前文本",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "来源：本站",
                "end_anchor": "打印页面",
                "include_selectors": ["正文锚点之间的非空文本行"],
                "exclude_selectors": ["页眉", "导航", "打印控件", "友情链接", "页脚"],
            },
        },
        "api": {"enabled": False, "reason": "原页面静态正文直接提供职务和姓名行；当前入口已返回404"},
    },
}


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    start = text.find("来源：本站")
    end = text.find("打印页面", start + 1) if start >= 0 else -1
    if start < 0 or end <= start:
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw_line in text[start:end].splitlines():
        line = _clean_text(raw_line)
        parts = re.split(r"[：:]", line, maxsplit=1)
        if len(parts) != 2:
            continue
        duty = _clean_text(parts[0]).strip(" ：:，,。.；;")
        name = re.sub(r"\s+", "", _clean_text(parts[1])).strip(" ：:，,。.；;")
        if not duty or not re.fullmatch(r"[\u4e00-\u9fff·.]{2,20}", name) or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": "custom_yunnan_sports_article_duty_name_lines_v2",
                "selector_summary": "来源：本站至打印页面正文；冒号前职务；冒号后姓名",
            }
        )
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
