from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2965',
 'page_type': '人物目录详情页',
 'structure_group': 'gansu_foreign_affairs_chrome_profiles',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'browser_render_wait_ms': 8000,
 'fetch_mode': 'chrome',
 'extract_mode': 'list_then_detail',
 'collector': 'chrome_cdp',
 'parser': 'page_inline_gansu_foreign_affairs_profiles_v2',
 'leader_region_selector': '#newsList > li',
 'name_selector': '.articleCon h2.title',
 'duty_selector': '.articleCon #fontzoom',
 'detail_link_selector': '.post-t > a[href]',
 'detail_strategy': {'required': True,
                     'mode': 'list_then_detail',
                     'detail_link_selector': '.post-t > a[href]'},
 'risk_flag': 'requests为412且Playwright正文过短，仅Chrome CDP可稳定取得列表及详情',
 'confidence': 'high'}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按Chrome渲染后的目录顺序逐页提取姓名和完整“现任……”句。"""
    import re
    from urllib.parse import urljoin

    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_by_chrome_debug

    soup = BeautifulSoup(html, "html.parser")
    candidates = soup.select("#newsList > li .post-t > a[href]")
    if not candidates:
        raise RuntimeError("Chrome渲染列表未发现#newsList领导详情链接")
    rows: list[dict[str, str]] = []
    for link in candidates:
        listed_name = re.sub(r"\s+", "", link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", listed_name):
            raise RuntimeError(f"领导目录姓名字段无效：{listed_name}")
        detail_result = fetch_by_chrome_debug(urljoin(final_url, str(link["href"])))
        detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        name_node = detail_soup.select_one(".articleCon h2.title")
        scope = detail_soup.select_one(".articleCon #fontzoom")
        if name_node is None or scope is None:
            raise RuntimeError(f"详情页缺少人物结构：{detail_result.final_url}")
        detail_name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        if detail_name != listed_name:
            raise RuntimeError(f"目录与详情姓名不一致：{listed_name} != {detail_name}")
        profile_text = re.sub(r"[\s\u00a0\u3000]+", "", scope.get_text("", strip=True))
        duty_match = re.search(r"现任[^。]*。", profile_text)
        if duty_match is None:
            raise RuntimeError(f"详情页缺少完整现任职务句：{detail_result.final_url}")
        duty = re.sub(r"^现任", "", duty_match.group(0)).rstrip("。")
        rows.append(
            {
                "name": detail_name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_result.final_url,
                "confidence": "high",
                "parser": "page_inline_gansu_foreign_affairs_profiles_v2",
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
