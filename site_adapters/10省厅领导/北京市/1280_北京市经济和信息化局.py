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
    "rule_id": "1280",
    "domain": "jxj.beijing.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "beijing_eit_ldfg_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_beijing_eit_ldfg_cards_v1",
    "risk_flag": "卡片职务后紧邻性别出生年月等简历段，必须只读取view中的首个非空段落",
    "confidence": "high",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性压缩排版空白，并去除中文之间的装饰性空格。"""
    text = re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)


def clean_name(value: str) -> str:
    """删除姓名中的排版空白。"""
    return re.sub(r"\s+", "", clean_text(value))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导卡片的DOM原始顺序读取姓名和首个非空职务段落。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in soup.select("li.ldfg_right"):
        if item.has_attr("hidden") or str(item.get("aria-hidden", "")).lower() == "true":
            continue
        name_node = item.select_one("h2")
        name = clean_name(name_node.get_text(" ", strip=True) if name_node is not None else "")
        duty = next(
            (
                text
                for paragraph in item.select(".view p")
                if (text := clean_text(paragraph.get_text(" ", strip=True)))
            ),
            "",
        )
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty or name in seen:
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
                "selector_summary": "li.ldfg_right内h2姓名与.view首个非空职务段落",
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
