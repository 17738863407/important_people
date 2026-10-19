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

PAGE_RULE = {'rule_id': '0978',
 'domain': 'www.hlj.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'parser': 'page_inline_hlj_gov_office_leaders_v2',
 'leader_region_selector': '“省政府办公厅领导”标题所在内容块',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': '政府信息公开聚合页内容较多，必须限定“省政府办公厅领导”标题后的同级段落',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '“省政府办公厅领导”标题所在内容块',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'}}}


def clean_text(value: str) -> str:
    """压缩页面中的全角空格、窄空格与普通空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析黑龙江省人民政府办公厅正文中的领导名单段落。"""
    soup = BeautifulSoup(html, "html.parser")
    organization = str(page_rule.get("organization", ""))
    page_url = str(page_rule.get("url", "")) or final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = "strategy=custom_parse_page；anchor=省政府办公厅领导；scope=标题后的同级p"
    leader_heading = next(
        (
            paragraph
            for paragraph in soup.select("p")
            if clean_text(paragraph.get_text(" ", strip=True)) == "省政府办公厅领导"
        ),
        None,
    )
    if leader_heading is None:
        raise RuntimeError("未找到省政府办公厅领导标题")

    for paragraph in leader_heading.find_next_siblings("p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        if not text:
            continue
        if text.startswith(("办公地址", "办公时间", "联系电话")):
            break
        match = re.fullmatch(
            r"(?P<name>(?:[\u4e00-\u9fa5]\s*){2,4}?)(?P<duty>省政府.+)",
            text,
        )
        if not match:
            continue
        name = re.sub(r"\s+", "", match.group("name"))
        duty = clean_text(match.group("duty")).strip("，。；;、 ")
        if name in seen or not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "organization": organization,
                "url": page_url,
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
