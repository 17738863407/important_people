from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3880",
    "page_type": "人物卡片列表页",
    "structure_group": "shantou_government_leader_blocks_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_shantou_government_blocks_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".leader_right1 .leader_padd > dl",
    "name_selector": "dd .font1 .font1_span",
    "duty_selector": "dd .font1 > b",
    "detail_link_selector": "dt > a[href]",
    "risk_flag": "页面另含切换标签、分工和活动信息，仅解析正文人物块的明确姓名职务行",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: object) -> str:
    """压缩页面排版空白，不改变职务字段语义。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """仅删除姓名字符之间的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def same_page(reference_url: str, candidate_url: str) -> bool:
    """忽略查询和片段比较入口与候选详情路径。"""
    reference = urlsplit(reference_url)
    candidate = urlsplit(candidate_url)
    return (
        reference.scheme.lower(),
        reference.netloc.lower(),
        reference.path.rstrip("/"),
    ) == (
        candidate.scheme.lower(),
        candidate.netloc.lower(),
        candidate.path.rstrip("/"),
    )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按正文人物块顺序提取姓名、职务和详情链接。"""
    soup = BeautifulSoup(html, "lxml")
    blocks = soup.select(page_rule["leader_region_selector"])
    if not blocks:
        raise RuntimeError("未找到市政府领导正文人物块")

    base_url = final_url or page_rule["url"]
    rows: list[dict] = []
    seen_names: set[str] = set()
    for block in blocks:
        name_node = block.select_one(page_rule["name_selector"])
        duty_node = block.select_one(page_rule["duty_selector"])
        detail_link = block.select_one(page_rule["detail_link_selector"])
        name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        href = clean_text(detail_link.get("href")) if detail_link else ""
        detail_url = urljoin(base_url, href) if href else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) or not duty:
            continue
        if name in seen_names:
            continue
        if not detail_url or same_page(page_rule["url"], detail_url):
            detail_url = ""

        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "confidence": "high",
                "parser": page_rule["parser"],
                "selector_summary": (
                    ".leader_right1 .leader_padd > dl内.font1_span姓名、b职务及dt头像链接"
                ),
            }
        )

    if not rows:
        raise RuntimeError("市政府领导正文人物块未提取到有效人物")
    return rows


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

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
