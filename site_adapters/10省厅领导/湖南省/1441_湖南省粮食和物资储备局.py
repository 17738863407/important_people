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
    "rule_id": "1441",
    "domain": "lshwzcbj.hunan.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "hunan_grain_inline_leader_group_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "playwright",
    "extract_mode": "inline_leader_list",
    "collector": "playwright",
    "parser": "page_inline_hunan_grain_leader_group_v2",
    "detail_strategy": {"required": False, "mode": "inline_with_verified_links"},
    "risk_flag": "HTTPS在requests链路触发BAD_ECPOINT；机构页含内设和直属机构同构列表",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def clean_name(value: str) -> str:
    """移除姓名中的排版空白。"""
    return re.sub(r"\s+", "", clean_text(value))


def clean_duty(value: str) -> str:
    """只清理职务节点中的排版空白，不改变职务语义。"""
    duty = clean_text(value).strip(" ：:，,。.")
    return re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", duty)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """仅解析标题为“机构领导”的分组，并继承其人物顺序。"""
    soup = BeautifulSoup(html, "html.parser")
    leader_region = None
    for region in soup.select(".gkmus2"):
        title_node = region.select_one(".lists-t2")
        if clean_text(title_node.get_text(" ", strip=True) if title_node else "") == "机构领导":
            leader_region = region
            break
    if leader_region is None:
        return []

    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in leader_region.select(".gkmus2-1 li"):
        name_node = item.select_one("a[href]")
        duty_node = item.select_one("span")
        name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        duty = clean_duty(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        detail_url = urljoin(final_url, clean_text(str(name_node.get("href", ""))))
        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")) or final_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；"
                    "group=.gkmus2 title=机构领导；"
                    "row=.gkmus2-1 li；fields=a[href]+span"
                ),
            }
        )

    return records


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
