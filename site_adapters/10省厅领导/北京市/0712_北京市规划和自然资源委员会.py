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
    "rule_id": "0712",
    "domain": "ghzrzyw.beijing.gov.cn",
    "page_type": "多人物详情合并页",
    "structure_group": "beijing_ghzrzyw_leader_blocks_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_beijing_ghzrzyw_leader_blocks_v1",
    "risk_flag": "页面顶部内嵌JSON与正文同时包含领导信息，必须限定在可见领导块内提取现任职务",
    "confidence": "high",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩网页文本中的换行、全角空格和连续空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ")).strip()


def clean_name(value: str) -> str:
    """删除姓名中的排版空白。"""
    return re.sub(r"\s+", "", str(value or "").replace("\u3000", ""))


def extract_present_sentence(block_text: str) -> tuple[str, str]:
    """仅在当前人物块内提取完整“现任……”句及原始职务。"""
    match = re.search(r"现任[^。]*。", block_text)
    if match is None:
        return "", ""
    evidence = clean_text(match.group(0))
    duty = evidence.removeprefix("现任").removesuffix("。")
    duty = re.sub(r"[（(]\s*兼\s*[）)]", "", duty).strip()
    return duty, duty


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按网页中可见领导块的原始顺序提取姓名、现任职务和详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for block in soup.select(".ldjj-list"):
        if block.has_attr("hidden") or str(block.get("aria-hidden", "")).lower() == "true":
            continue
        name_link = block.select_one(".name a[href]")
        intro = block.select_one(".indroduce")
        if name_link is None or intro is None:
            continue

        name = clean_name(name_link.get_text(" ", strip=True) or str(name_link.get("title") or ""))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue

        duty, evidence = extract_present_sentence(clean_text(intro.get_text(" ", strip=True)))
        if not duty:
            continue

        href = clean_text(str(name_link.get("href") or ""))
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(final_url, href) if href else "",
                "evidence": evidence,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".ldjj-list内.name姓名、.indroduce现任句及同块详情链接",
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
