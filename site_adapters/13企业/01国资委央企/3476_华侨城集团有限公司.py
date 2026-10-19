from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def clean_text(value: str) -> str:
    """压缩人物简介中的排版空白。"""
    text = " ".join((value or "").replace("\u3000", " ").replace("\xa0", " ").split())
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    text = re.sub(r"\s+([，。；：、（）])", r"\1", text)
    return re.sub(r"([，。；：、（）])\s+", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析董事会人物块中的姓名和完整现任句。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []

    for card in soup.select("ul.page_newlist.gltd > li"):
        name_node = card.select_one(".gltd_right h2")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
            continue
        evidence = ""
        for paragraph in card.select(".gltd_right p"):
            text = clean_text(paragraph.get_text(" ", strip=True))
            match = re.search(r"现任[^。]*。", text)
            if match:
                evidence = re.sub(
                    r"^现任(?:职务)?\s*[：:]?\s*",
                    "",
                    clean_text(match.group(0)),
                )
        if not evidence:
            continue
        records.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": "",
                "evidence": evidence,
                "confidence": "high",
                "parser": "page_inline_oct_board_current_sentence_v1",
            }
        )
    return records


PAGE_RULE = {
    "rule_id": "3476",
    "page_type": "人物列表完整页",
    "structure_group": "oct_board_profile_cards",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "browser_dom",
    "parser": "page_inline_oct_board_current_sentence_v1",
    "locator_strategy": "custom_parse_page",
    "risk_flag": "规则表 HTTP 入口的错误重定向使 requests/Playwright 失败，在线链路由 Chrome CDP 取得页面；只提取同块完整现任句",
    "confidence": "high",
}


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

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
