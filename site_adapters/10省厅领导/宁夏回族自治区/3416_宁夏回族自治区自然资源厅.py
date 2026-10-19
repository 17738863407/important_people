from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3416',
 'domain': 'zrzyt.nx.gov.cn',
 'page_type': '图片名单型',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '图片承载',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'image_asset',
 'parser': 'ningxia_natural_resources_image_profiles_v1',
 'leader_region_selector': 'html > body > section.head.clearfix:nth-of-type(1)',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'raw': '{"required":false,"mode":"none","detail_collector_type":"image_asset","detail_link_selector":null,"detail_name_selector":"","detail_duty_selector":"","detail_content_selector":"","max_detail_links":50,"candidate_links":[]}'},
 'risk_flag': '领导信息存储在图片中',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'html > body > section.head.clearfix:nth-of-type(1)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线领导列表与详情正文用于补齐职务'},
             'migration': {'source': 'last_batch_online_template',
                           'verified_status': 'fixed_verified',
                           'behavior_changed': True}}}


def _clean_text(value: str) -> str:
    """清理页面排版空白，同时保留原始标点。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", value or "").strip()


def _strip_current_prefix(value: str) -> str:
    """仅删除任职证据句首的“现任”固定标签。"""
    return re.sub(r"^现任(?:职务)?\s*[：:]?\s*", "", value)


def _fetch_online_html(url: str) -> str:
    """以官网可接受的简洁请求头在线读取页面。"""
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read()
        encoding = response.headers.get_content_charset() or "utf-8"
    return raw.decode(encoding, errors="ignore")


def _extract_detail_evidence(detail_url: str, name: str) -> str:
    """从详情页人物简介中抽取完整原始任职句。"""
    soup = BeautifulSoup(_fetch_online_html(detail_url), "html.parser")
    paragraphs = [_clean_text(node.get_text("", strip=True)) for node in soup.select(".TRS_UEDITOR p")]
    for text in paragraphs:
        current_match = re.search(r"现任[^。]*。", text)
        if current_match:
            return _strip_current_prefix(current_match.group(0))
        if text.startswith(("自治区自然资源厅", "宁夏回族自治区自然资源厅")) and text.endswith("。"):
            return text
    joined = "".join(paragraphs)
    fallback_match = re.search(
        r"[；;](?P<duty>(?:现任)?(?:宁夏回族自治区|自治区)自然资源厅[^。]*。)",
        joined,
    )
    if fallback_match:
        return _strip_current_prefix(fallback_match.group("duty"))
    return ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导名单网页顺序进入详情页，在线抽取原始任职句。"""
    soup = BeautifulSoup(html, "html.parser")
    if not soup.select("ul.u-commonList_leader li a[href] h3"):
        soup = BeautifulSoup(_fetch_online_html(str(page_rule["url"])), "html.parser")
    rows: list[dict[str, str]] = []
    for heading in soup.select("ul.u-commonList_leader li a[href] h3"):
        link = heading.find_parent("a", href=True)
        if link is None:
            continue
        name = re.sub(r"厅长$", "", _clean_text(heading.get_text("", strip=True)))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name):
            continue
        detail_url = urljoin(str(page_rule["url"]), str(link.get("href") or ""))
        if not re.search(r"/t\d+_\d+\.html$", detail_url):
            continue
        try:
            evidence = _extract_detail_evidence(detail_url, name)
        except Exception:
            continue
        if not evidence:
            continue
        rows.append(
            {
                "organization": str(page_rule["organization"]),
                "url": str(page_rule["url"]),
                "name": name,
                "duty": evidence,
                "detail_url": detail_url,
                "evidence": evidence,
                "parser": str(page_rule["parser"]),
                "selector_summary": "ul.u-commonList_leader名单+详情页.TRS_UEDITOR任职句",
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
