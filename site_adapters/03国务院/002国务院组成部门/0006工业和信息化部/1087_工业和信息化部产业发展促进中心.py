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
    "rule_id": "1087",
    "page_type": "人物列表完整页",
    "structure_group": "正文段落姓名职务连续文本",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "IdpcArticleLeaderParagraphParser_v2",
    "leader_region_selector": ".pageArticle .article",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "姓名内部含排版空格，页面无独立人物详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按正文段落DOM顺序抽取姓名和原始职务文本。"""
    soup = BeautifulSoup(html, "html.parser")
    paragraphs = soup.select(".pageArticle .article p")
    if not paragraphs:
        raise RuntimeError("未找到中心领导正文 .pageArticle .article p")

    rows: list[dict] = []
    seen: set[str] = set()
    for paragraph in paragraphs:
        evidence = _clean_text(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(
            r"(?P<name>[\u4e00-\u9fff ]{2,8}?)\s+(?P<duty>(?:中心|党委|纪委).+)",
            evidence,
        )
        if not match:
            continue
        name = re.sub(r"\s+", "", match.group("name"))
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or name in seen:
            continue
        duty = re.sub(r"\s*([、，；：])\s*", r"\1", match.group("duty")).strip()
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": ".pageArticle .article p",
            }
        )

    if not rows:
        raise RuntimeError("中心领导正文未解析到姓名职务记录")
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
