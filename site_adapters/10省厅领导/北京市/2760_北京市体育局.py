from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2760",
    "domain": "tyj.beijing.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "beijing_sports_leader_profile_links_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_beijing_sports_leader_profile_links_v1",
    "risk_flag": "每人同时有图片与文本链接；仅解析带姓名职务文本的链接并按姓名去重",
    "confidence": "high",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩网页排版空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u200b", "").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按体育局领导列表的DOM原始顺序解析文本链接。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    pattern = re.compile(r"^(?P<name>[\u4e00-\u9fff·]{2,8})\s+(?P<duty>.+)$")
    for link in soup.select("ul.ldjj_list_pre1 li a[href]"):
        evidence = clean_text(link.get_text(" ", strip=True))
        match = pattern.fullmatch(evidence)
        if match is None:
            continue
        name = match.group("name")
        duty = clean_text(match.group("duty"))
        duty = re.sub(r"[（(]挂职[）)]", "", duty).rstrip("，、；; ")
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(final_url, link.get("href", "")),
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "ldjj_list_pre1内非空人物文本链接",
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
