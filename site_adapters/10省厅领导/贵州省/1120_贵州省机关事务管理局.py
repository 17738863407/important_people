from __future__ import annotations

import sys
import re
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1120',
 'page_type': '多人物详情合并页',
 'structure_group': 'guizhou_script_list_online_profiles',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_then_detail',
 'collector': 'static_http',
 'parser': 'page_inline_guizhou_online_leader_profiles_v2',
 'leader_region_selector': '#ldlist',
 'name_selector': '.ldjbxx > p:first-of-type',
 'duty_selector': '.ldjbxx',
 'detail_link_selector': '#ldlist a[href]',
 'detail_strategy': {'required': True,
                     'mode': 'list_then_detail',
                     'detail_link_selector': '#ldlist a[href]'},
 'risk_flag': '目录由内嵌脚本拼接；存在两名不同人物同名，禁止按姓名去重',
 'confidence': 'high',
 'configuration_status': '在线核验通过'}


def normalize_text(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按脚本拼接顺序在线读取每个详情，保留不同URL的同名人物。"""
    from urllib.parse import urljoin

    from crawler_core.fetcher import fetch_by_raw_requests

    rows: list[dict[str, str]] = []
    detail_urls = re.findall(r'var src = "([^"]+)"', html)
    if not detail_urls:
        raise RuntimeError("页面脚本未发现领导详情URL")
    seen_urls: set[str] = set()
    for raw_url in detail_urls:
        detail_result = fetch_by_raw_requests(urljoin(final_url, raw_url))
        if detail_result.final_url in seen_urls:
            continue
        seen_urls.add(detail_result.final_url)
        detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        scope = detail_soup.select_one(".ldzc_right .ldjj_box .ldjbxx")
        name_node = scope.select_one(":scope > p:first-of-type") if scope else None
        if scope is None or name_node is None:
            raise RuntimeError(f"详情页缺少领导基本信息结构：{detail_result.final_url}")
        name = normalize_text(name_node.get_text(" ", strip=True))
        text = normalize_text(scope.get_text(" ", strip=True))
        duty_match = re.search(r"现任[^。]*。", text)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or duty_match is None:
            raise RuntimeError(f"详情页姓名或现任职务无效：{detail_result.final_url}")
        duty = duty_match.group(0).removeprefix("现任").removesuffix("。")
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_result.final_url,
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_guizhou_online_leader_profiles_v2",
            }
        )
    if not rows:
        raise RuntimeError("领导详情页未解析出有效人物")
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
