from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3116",
    "domain": "ybj.fujian.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "fujian_medical_security_leader_titles_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "static_http",
    "parser": "page_inline_fujian_medical_security_leader_titles_v1",
    "leader_region_selector": ".leader_name_list a[title][href]",
    "name_duty_attribute": "title",
    "detail_link_selector": "self[href]",
    "detail_strategy": {
        "required": False,
        "mode": "current_title_links",
    },
    "risk_flag": "领导链接title为姓名和职务组合字段；不得给原始职务补写机构前缀",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性压缩HTML排版空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", " ", str(value or "")).strip()


def comparable_url(value: str) -> str:
    parts = urlsplit(value)
    path = parts.path.rstrip("/") + "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def split_name_duty(value: str) -> tuple[str, str]:
    text = clean_text(value)
    match = re.fullmatch(r"([\u4e00-\u9fff·]{2,10})\s+(.+)", text)
    if match is None:
        return "", ""
    return match.group(1), match.group(2)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导下拉目录原序解析title中的姓名和原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    entry_url = comparable_url(final_url)
    attribute = str(page_rule["name_duty_attribute"])
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(str(page_rule["leader_region_selector"])):
        name, evidence = split_name_duty(str(link.get(attribute) or ""))
        if not name or not evidence or name in seen:
            continue
        candidate = urljoin(final_url, str(link.get("href") or ""))
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "" if comparable_url(candidate) == entry_url else candidate,
            }
        )
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
