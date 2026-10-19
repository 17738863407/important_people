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
    "rule_id": "2714",
    "domain": "tjj.beijing.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "beijing_statistics_leader_paragraphs_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_beijing_statistics_leader_paragraphs_v1",
    "risk_flag": "人物区域含空段落且姓名可能含单个全角空格；按连续双空白确定职务边界",
    "confidence": "high",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """删除零宽字符并压缩网页排版空白。"""
    normalized = str(value or "").replace("\u200b", "").replace("\u200d", "").replace("\xa0", " ")
    return re.sub(r"\s+", " ", normalized).strip()


def split_leader_text(value: str) -> tuple[str, str]:
    """以姓名后的连续双空白拆分姓名和原始职务。"""
    parts = re.split(r"\s{2,}", str(value or "").strip(), maxsplit=1)
    if len(parts) != 2:
        return "", ""
    name = re.sub(r"\s+", "", clean_text(parts[0]))
    duty = clean_text(parts[1])
    if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None:
        return "", ""
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按统计局领导段落的DOM原始顺序解析非空人物记录。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in soup.select(".ldjlR p"):
        raw_text = paragraph.get_text(" ", strip=True)
        name, duty = split_leader_text(raw_text)
        if not name or not duty or name in seen:
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
                "selector_summary": "ldjlR内非空p人物段落",
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
