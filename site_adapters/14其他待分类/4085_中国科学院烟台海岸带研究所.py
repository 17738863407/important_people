from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4085",
    "page_type": "领导卡片页",
    "structure_group": "yic_leader_position_link_card",
    "reuse_scope": "page_structure",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_yic_leader_position_link_card",
    "leader_region_selector": ".leader-container",
    "risk_flag": "内嵌样式不参与人物提取，仅解析领导卡片链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析姓名在前、职务在后的卡片链接并保留对应人物详情页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for link in soup.select(".leader-container a.position-link[href]"):
        text = re.sub(r"\s+", "", link.get_text(" ", strip=True))
        split = next(
            (
                (text[:name_length], text[name_length:])
                for name_length in (2, 3, 4)
                if re.match(r"(?:党委|纪委|副|所长|院长|主任|书记)", text[name_length:])
            ),
            None,
        )
        if split is None:
            continue
        rows.append({"name": split[0], "duty": split[1], "evidence": split[1],
                     "detail_url": urljoin(final_url, link["href"])})
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
