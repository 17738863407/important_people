from __future__ import annotations

import sys
import re
from urllib.parse import urljoin
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2621',
 'domain': 'swt.gansu.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'top_leader_nav_gansu_commerce_v1',
 'leader_region_selector': '厅领导顶部导航',
 'name_selector': '领导导航姓名',
 'duty_selector': '领导导航职务',
 'detail_link_selector': '领导导航href',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'browser_dom',
                     'max_detail_links': 50},
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'html > body > div.main_box:nth-of-type(4) > '
                                               'div.lingdao_main.d:nth-of-type(1)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线浏览器 DOM 解析厅领导导航'}}}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return " ".join((value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def split_leader_text(link) -> tuple[str, str]:
    """从领导导航链接的实时文本中拆分姓名与原始职务。"""
    parts = [clean_text(part) for part in link.stripped_strings if clean_text(part)]
    if parts and re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", parts[0]):
        return parts[0], clean_text(" ".join(parts[1:]))
    image = link.find("img")
    image_alt = clean_text(image.get("alt", "")) if image else ""
    if re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", image_alt):
        return image_alt, clean_text(" ".join(parts))
    text = clean_text(link.get_text(" ", strip=True))
    match = re.match(
        r"^(?P<name>[\u4e00-\u9fff·]{2,4}?)(?P<duty>(?:厅|党组|省纪委|驻厅|副厅|一级|二级).*)$",
        text.replace(" ", ""),
    )
    if not match:
        return "", ""
    return match.group("name"), clean_text(match.group("duty"))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析甘肃省商务厅厅领导顶部导航名单。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("div.lingdao_main.d") or soup.select_one("div.lingdao_main") or soup
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in region.select('a[href*="ldzc_con.shtml"]'):
        name, duty = split_leader_text(link)
        if not name or name in seen:
            continue
        seen.add(name)
        detail_url = urljoin(final_url, link.get("href") or "")
        if detail_url.rstrip("/") == final_url.rstrip("/"):
            detail_url = ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule["parser"]),
                "selector_summary": "厅领导导航链接文本：姓名+职务",
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
