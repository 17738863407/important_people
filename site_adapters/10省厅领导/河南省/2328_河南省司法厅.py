from __future__ import annotations

import re
import sys
from html import unescape
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlsplit


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2328',
 'domain': 'sft.henan.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'parser': 'custom_henan_sft_expanded_profiles_v1',
 'leader_region_selector': '.colInfoBox .leaderCon',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.colInfoBox .leaderCon',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '页面已展开全部领导简介，左侧列表提供详情链接'}}}


def _make_record(page_rule: dict, name: str, duty: str, detail_url: str) -> object:
    from crawler_core.models import PersonRecord

    return PersonRecord(
        organization=page_rule["organization"],
        url=page_rule["url"],
        name=name,
        duty=duty,
        detail_url=detail_url,
        evidence=duty,
        confidence="high",
        parser=page_rule["parser"],
    )


def _clean_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = unescape(text).replace("\u3000", "")
    return re.sub(r"\s+", "", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析河南省司法厅已展开的领导简介。"""
    page_url = final_url or str(page_rule.get("url", ""))
    link_map: dict[str, str] = {}
    for link_match in re.finditer(r'<a href="(?P<href>[^"]+)" title="(?P<title>[^"]+)">', html):
        name = _clean_text(link_match.group("title"))
        if name:
            detail_url = urldefrag(urljoin(page_url, link_match.group("href"))).url
            parsed = urlsplit(detail_url)
            if parsed.scheme in {"http", "https"} and parsed.netloc and detail_url.rstrip("/") != page_url.rstrip("/"):
                link_map[name] = detail_url

    rows: list[object] = []
    seen: set[str] = set()
    for para_match in re.finditer(r"<p[^>]*>(?P<text>[^<]*?现任[^<]*?)</p>", html, re.S):
        text = _clean_text(para_match.group("text"))
        item_match = re.match(r"(?P<name>[\u4e00-\u9fa5]{2,4})，.*?现任(?P<duty>[^。]+)", text)
        if not item_match:
            continue
        name = item_match.group("name")
        duty = item_match.group("duty")
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(_make_record(page_rule, name, duty, link_map.get(name, "")))
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
