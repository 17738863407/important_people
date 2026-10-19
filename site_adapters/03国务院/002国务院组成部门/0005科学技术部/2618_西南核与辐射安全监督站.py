from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2618',
 'page_type': '人物列表完整页',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'force_browser': True,
 'extract_mode': 'list_direct',
 'parser': 'page_parse_page',
 'leader_region_selector': '.main_left, .main_right .list_txt',
 'name_selector': '.main_left a[href]对应栏目页 .main_right .list_txt li a[href]',
 'duty_selector': '.main_left a[href]栏目标题',
 'detail_link_selector': '各职务栏目页 .main_right .list_txt li a[href]',
 'detail_strategy': {'required': True, 'mode': 'person_name_link'},
 'risk_flag': 'requests存在TLS失败，online强制浏览器；必须验证详情标题姓名与列表一致',
 'confidence': 'high',
 'filter_policy': 'weak_allow_wordlist',
 'locator_strategy': 'custom_parse_page',
 'risk_note': '按左侧站领导栏目顺序遍历全部职务页，以栏目标题作为强结构职务依据；详情页仅用于验证姓名和真实人物链接。'}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按左侧站领导职务栏目顺序解析全部人物。"""
    import re
    from urllib.parse import urljoin

    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_group_urls: set[str] = set()
    seen_names: set[str] = set()
    for group_link in soup.select(".main_left a[href]"):
        duty = re.sub(r"\s+", "", group_link.get_text(" ", strip=True))
        group_url = urljoin(final_url, str(group_link.get("href", "")))
        if not duty or not group_url or group_url in seen_group_urls:
            continue
        seen_group_urls.add(group_url)
        if group_url.rstrip("/") == final_url.rstrip("/"):
            group_html = html
            group_final_url = final_url
        else:
            group_result = fetch_html_with_strategy(group_url, "online", force_browser=True)
            group_html = group_result.html
            group_final_url = group_result.final_url
        group_soup = BeautifulSoup(group_html, "html.parser")
        for link in group_soup.select(".main_right .list_txt li a[href]"):
            name = re.sub(r"\s+", "", link.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen_names:
                continue
            detail_result = fetch_html_with_strategy(
                urljoin(group_final_url, str(link.get("href", ""))),
                "online",
                force_browser=True,
            )
            detail_soup = BeautifulSoup(detail_result.html, "html.parser")
            detail_title = detail_soup.title.get_text(" ", strip=True) if detail_soup.title else ""
            if name not in detail_title:
                raise ValueError(f"领导详情标题与列表姓名不一致：{name}")
            seen_names.add(name)
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "detail_url": detail_result.final_url,
                    "evidence": duty,
                    "parser": "page_parse_page",
                    "selector_summary": "职务=.main_left a；姓名=各栏目.list_txt li a；详情标题校验",
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
