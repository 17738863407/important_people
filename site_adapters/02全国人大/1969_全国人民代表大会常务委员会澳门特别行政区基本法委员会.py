from __future__ import annotations

import html as html_lib
import re
import sys
from urllib.request import Request, urlopen
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1969',
 'domain': 'www.npc.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'npc_macao_basic_law_committee_iframe_v1',
 'leader_region_selector': '委员会组成人员官方iframe',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': None,
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '新闻人物或正文干扰；页面包含iframe；第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '委员会组成人员官方iframe',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {'source': 'legacy_page_rule', 'verified_status': 'pending_root', 'behavior_changed': False}}}


def _clean_text(text: str) -> str:
    text = html_lib.unescape(text).replace("\u3000", " ").replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _html_to_text(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "\n", text)
    return _clean_text(text)


def _fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        raw = response.read()
    return raw.decode("utf-8", errors="ignore")


def _source_html(html: str, base_url: str) -> tuple[str, str]:
    if "委员会组成人员" in html and "工作委员会" in html:
        return html, base_url
    iframe_match = re.search(r'<iframe[^>]+src=["\'](?P<src>[^"\']*amjbfwyh020/?[^"\']*)["\']', html, flags=re.I)
    iframe_url = urljoin(base_url, iframe_match.group("src")) if iframe_match else urljoin(base_url, "amjbfwyh020/")
    return _fetch_text(iframe_url), iframe_url


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析全国人大澳门基本法委员会官方 iframe 中的组成人员。"""
    from crawler_core.models import PersonRecord

    source_html, source_url = _source_html(html, page_rule["url"])
    text = _html_to_text(source_html)
    pattern = re.compile(
        r"委员会组成人员\s+主任\s+(?P<director>.*?)\s+副主任\s+(?P<deputies>.*?)\s+委员\s+（按姓名笔划为序）\s+.*?\s+工作委员会"
    )
    match = pattern.search(text)
    if not match:
        return []

    def names_from_text(value: str) -> list[str]:
        tokens = [token for token in re.split(r"\s+", value.strip()) if token]
        names = []
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if len(token) == 1 and index + 1 < len(tokens) and len(tokens[index + 1]) == 1:
                token += tokens[index + 1]
                index += 1
            if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", token):
                names.append(token)
            index += 1
        return names

    people: list[tuple[str, str]] = [(name, "主任") for name in names_from_text(match.group("director"))]
    people.extend((name, "副主任") for name in names_from_text(match.group("deputies")))

    records = []
    seen: set[tuple[str, str]] = set()
    for name, duty in people:
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url="",
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary="official iframe committee member text",
            )
        )
    return records


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
