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
    "rule_id": "1138",
    "domain": "jhj.sc.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "sichuan_economic_cooperation_leader_links",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_sichuan_jhj_leader_links_v2",
    "leader_link_selector": "a[href*='zfxxgkldxxlist']",
    "name_duty_pattern": r"^(.+)\s+((?:党组|副局长).+|一级巡视员|二级巡视员)$",
    "detail_strategy": {
        "required": False,
        "mode": "list_item_link",
    },
    "risk_flag": "页面其他区域含大量政府信息链接；仅解析href含zfxxgkldxxlist的领导链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def normalize_space(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(value or "")).strip()


def clean_name(value: str) -> str:
    """移除姓名内部排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(value or "")).strip()


def clean_status_markers(value: str) -> str:
    """仅删除无期限独立状态标记，保留职级及带期限挂职信息。"""
    marker = r"(?:（(?:兼|挂职|主持日常工作|主持工作)）|\((?:兼|挂职|主持日常工作|主持工作)\)|[<＜](?:兼|挂职)[>＞])"
    return re.sub(marker, "", normalize_space(value)).strip("，,、 ")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导链接DOM顺序提取姓名、原始职务和独立人物页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    source_url = final_url or str(page_rule["url"])
    pattern = re.compile(str(page_rule["name_duty_pattern"]))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(str(page_rule["leader_link_selector"])):
        text = normalize_space(link.get_text(" ", strip=True))
        match = pattern.match(text)
        if not match:
            continue

        name = clean_name(match.group(1))
        duty = clean_status_markers(match.group(2))
        if not duty or name in seen or not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name):
            continue

        href = str(link.get("href") or "").strip()
        detail_url = urljoin(source_url, href) if href else ""
        if detail_url in {source_url, str(page_rule["url"])}:
            detail_url = ""

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "parser": str(page_rule["parser"]),
                "selector_summary": "href含zfxxgkldxxlist的领导链接文本及href",
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
