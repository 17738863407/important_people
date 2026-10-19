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
    "rule_id": "2888",
    "domain": "wjw.beijing.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "beijing_health_leader_lines_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_beijing_health_leader_lines_v1",
    "risk_flag": "个别姓名含排版空格且职务可能分为多个p段落；须按同卡片段落顺序连接",
    "confidence": "high",
    "locator_strategy": "custom_parse_page",
}


def compact_text(value: str) -> str:
    """移除字段内部的排版空白和零宽字符。"""
    return re.sub(r"\s+", "", str(value or "").replace("\u200b", ""))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导卡片DOM原始顺序解析姓名和多段原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    selector = ".con_con_lingdao .con_con_lingdao_line:has(.con_con_lingdao_line_text_tit):has(.con_con_lingdao_line_text_text)"
    for item in soup.select(selector):
        name_node = item.select_one(".con_con_lingdao_line_text_tit")
        duty_node = item.select_one(".con_con_lingdao_line_text_text")
        name = compact_text(name_node.get_text("", strip=True) if name_node else "")
        paragraphs = [compact_text(p.get_text("", strip=True)) for p in duty_node.select("p")] if duty_node else []
        paragraphs = [text for text in paragraphs if text]
        duty = "；".join(paragraphs) if paragraphs else compact_text(duty_node.get_text("", strip=True) if duty_node else "")
        duty = re.sub(r"[（(]兼[）)]", "", duty).strip("，、； ")
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "con_con_lingdao_line同卡片标题姓名与职务段落",
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
