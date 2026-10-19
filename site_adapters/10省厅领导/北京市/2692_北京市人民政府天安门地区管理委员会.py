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
    "rule_id": "2692",
    "domain": "tamgw.beijing.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "beijing_tiananmen_leader_titles_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_beijing_tiananmen_leader_titles_v1",
    "risk_flag": "姓名可能含连续排版空格；必须限定唯一leader_list并从同段剩余文本取职务",
    "confidence": "high",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """删除零宽字符并压缩网页排版空白。"""
    normalized = str(value or "").replace("\u200b", "").replace("\u200d", "").replace("\xa0", " ")
    return re.sub(r"\s+", " ", normalized).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按天安门地区管委会领导段落的DOM原始顺序解析。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in soup.select(".container.leader_list p.tit"):
        name_node = item.find("strong")
        if name_node is None:
            continue
        raw_name = name_node.get_text(" ", strip=True)
        raw_full = item.get_text(" ", strip=True)
        name = re.sub(r"\s+", "", clean_text(raw_name))
        duty = clean_text(raw_full.replace(raw_name, "", 1))
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "唯一leader_list内tit段落strong姓名与同段职务",
            }
        )
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
