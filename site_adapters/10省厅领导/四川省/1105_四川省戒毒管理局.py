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
    "rule_id": "1105",
    "domain": "jdglj.sc.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "sichuan_drug_rehab_ldxx_links",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_sichuan_drug_rehab_ldxx_links_v2",
    "leader_link_selector": "#cmsArticleContent a[href*='/ldxx/']",
    "name_duty_pattern": r"([\u4e00-\u9fff\s]{2,8})\s+(四川省.+)",
    "detail_suffix_pattern": r"\s*详情\s*>*>?\s*$",
    "detail_strategy": {
        "required": False,
        "mode": "list_item_link",
    },
    "risk_flag": "正文同时含主要职责、机构设置和直属单位；只解析领导简介区域内含/ldxx/的链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性清理全角空格、排版空格和连续空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\u2003", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导简介链接顺序提取姓名、完整原始职务和人物页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    source_url = final_url or str(page_rule["url"])
    name_duty_pattern = re.compile(str(page_rule["name_duty_pattern"]))
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for link in soup.select(str(page_rule["leader_link_selector"])):
        text = clean_text(link.get_text(" ", strip=True))
        text = re.sub(str(page_rule["detail_suffix_pattern"]), "", text)
        match = name_duty_pattern.fullmatch(text)
        if not match:
            continue

        name = clean_text(match.group(1)).replace(" ", "")
        duty = clean_text(match.group(2)).strip(" ：:，,。")
        if not duty or not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
            continue

        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        href = str(link.get("href") or "").strip()
        detail_url = urljoin(source_url, href) if href else ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "parser": str(page_rule["parser"]),
                "selector_summary": "#cmsArticleContent内含/ldxx/的领导链接文本及href",
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
