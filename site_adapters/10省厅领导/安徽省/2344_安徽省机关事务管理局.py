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

PAGE_RULE = {'rule_id': '2344',
 'page_type': '人物目录详情页',
 'structure_group': 'anhui_public_leader_list_and_profile',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_then_detail',
 'collector': 'static_http',
 'parser': 'page_inline_anhui_leader_profiles_v2',
 'leader_region_selector': '#zdgkList',
 'name_selector': '#zoom',
 'duty_selector': '#zoom',
 'detail_link_selector': 'a.title[href]',
 'detail_strategy': {'required': True,
                     'mode': 'list_then_detail',
                     'detail_link_selector': 'a.title[href]'},
 'risk_flag': 'online会误跟随导航脚本丢失catId；详情当前职务可能与列表标题不同',
 'confidence': 'high'}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导目录顺序抓取详情，只取当前人物简介中的完整“现任……”句。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select("#zdgkList a.title[href]"):
        detail_result = fetch_by_raw_requests(urljoin(final_url, str(link["href"])))
        detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        scope = detail_soup.select_one("#zoom")
        if scope is None:
            continue
        text = re.sub(r"[\s\u00a0\u3000]+", "", scope.get_text("", strip=True))
        name_match = re.match(r"^([\u4e00-\u9fff·]{2,8})[，,]", text)
        duty_match = re.search(r"现任[^。]*。", text)
        if name_match is None or duty_match is None:
            continue
        name = name_match.group(1)
        duty = duty_match.group(0).removeprefix("现任").removesuffix("。")
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_result.final_url,
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_anhui_leader_profiles_v2",
            }
        )
    if not rows:
        raise RuntimeError("领导目录详情页未解析出姓名及完整现任职务句")
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
