from __future__ import annotations

import sys
from pathlib import Path
import re
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0514',
 'domain': 'edu.xizang.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': 'iframe静态HTML',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'image_asset',
 'parser': 'S_EDU_XIZANG_GOV_CN_IFRAME_LEADER_V1',
 'leader_region_selector': '.boss',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'image_asset',
                     'detail_link_selector': None,
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '领导信息存储在图片中；页面包含iframe；第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.boss',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {'source': 'legacy_page_rule', 'verified_status': 'pending_root', 'behavior_changed': False}}}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析西藏自治区教育厅 iframe 领导页。"""
    from crawler_core.models import PersonRecord

    base_url = final_url
    iframe_url = urljoin(base_url, "16/index.html")
    soup = BeautifulSoup(_fetch_html(iframe_url), "html.parser")
    organization = str(page_rule.get("organization") or "")
    rows: list[PersonRecord] = []
    for item in soup.select("div.boss li"):
        name_node = item.select_one("dd.name")
        duty_node = item.select_one("dd.post")
        name = _clean_text(name_node.get_text(" ", strip=True) if name_node else "")
        duty = _clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,6}", name) or not duty:
            continue
        rows.append(
            PersonRecord(
                organization=organization,
                url=str(page_rule.get("url") or base_url),
                name=name,
                duty=duty,
                detail_url="",
                evidence=duty,
                confidence="high",
                parser="S_EDU_XIZANG_GOV_CN_IFRAME_LEADER_V1",
                selector_summary="iframe 8/16/index.html div.boss li dd.name/dd.post",
            )
        )
    return rows


def _fetch_html(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=25) as response:
        data = response.read()
        content_type = response.headers.get("content-type", "")
    charset_match = re.search(r"charset=([\w-]+)", content_type, re.I)
    encodings = [charset_match.group(1)] if charset_match else []
    encodings.extend(["utf-8", "gb18030"])
    for encoding in encodings:
        try:
            return data.decode(encoding)
        except Exception:
            continue
    return data.decode("utf-8", errors="ignore")


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", "", value.replace("\u3000", " ")).strip(" ：:\t\r\n")


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
