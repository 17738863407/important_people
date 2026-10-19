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

PAGE_RULE = {'rule_id': '0630',
 'domain': 'gat.hubei.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'parser': 'hubei_police_view_paragraph_v1',
 'leader_region_selector': '.article-box .view p',
 'name_selector': '.article-box .view p（冒号前）',
 'duty_selector': '.article-box .view p（冒号后）',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': '第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.article-box .view p',
                     'name_selector': '.article-box .view p（冒号前）',
                     'duty_selector': '.article-box .view p（冒号后）',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': ['.article-box .view'],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线页面包含领导信息静态段落，无需接口或详情页'}}}


def clean_text(value: str) -> str:
    text = (value or "").replace("\u00a0", " ").replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"(?<=[\u4e00-\u9fa5])\s+(?=[\u4e00-\u9fa5])", "", text)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；leader=.article-box .view p；"
        "name=冒号前；duty=冒号后；detail=none；api_enabled=False"
    )
    for paragraph in soup.select(".article-box .view p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        match = re.match(r"^(?P<name>[\u4e00-\u9fa5·]{2,4})[:：]\s*(?P<duty>.+)$", text)
        if not match:
            continue
        name = clean_text(match.group("name"))
        duty = clean_text(match.group("duty")).strip(" ：:，,。")
        duty = re.sub(
            r"([（(])([^（）()]*?)[，,]\s*协助[^（）()]*?负责[^（）()]*?工作([）)])",
            r"\1\2\3",
            duty,
        )
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")),
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": selector_summary,
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
