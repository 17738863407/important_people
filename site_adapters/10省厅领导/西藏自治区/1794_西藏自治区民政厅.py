from __future__ import annotations

import sys
import re
import subprocess
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from crawler_core.paths import find_powershell_executable


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1794',
 'domain': 'mzt.xizang.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_to_detail',
 'collector': 'static_http',
 'parser': 'xizang_mzt_leader_detail_v1',
 'leader_region_selector': '.gl-list li a.e[href]',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'html > body > div.w-container:nth-of-type(2)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'pending',
                           'behavior_changed': False}}}


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ")).strip()


def _clean_duty(text: str) -> str:
    text = _clean_text(text)
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    text = re.sub(r"\s*([、，,；;：:（）()])\s*", r"\1", text)
    return text


def _fetch_detail_html(url: str) -> str:
    candidates = [
        url.replace("http://mzt.xizang.gov.cn/", "https://mzt.xizang.gov.cn/", 1),
        url,
        url.replace("https://mzt.xizang.gov.cn/", "http://mzt.xizang.gov.cn/", 1),
    ]
    last_error: Exception | None = None
    for fetch_url in dict.fromkeys(candidates):
        request = Request(fetch_url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urlopen(request, timeout=20) as response:
                body = response.read()
                encoding = response.headers.get_content_charset() or "utf-8"
            return body.decode(encoding, errors="replace")
        except Exception as exc:
            last_error = exc

    command = (
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
        "(Invoke-WebRequest -Uri $args[0] -UseBasicParsing -TimeoutSec 20).Content"
    )
    for fetch_url in dict.fromkeys(candidates):
        try:
            result = subprocess.run(
                [str(find_powershell_executable()), "-NoProfile", "-Command", command, fetch_url],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
            )
            return result.stdout
        except Exception as exc:
            last_error = exc
    if last_error:
        raise last_error
    raise RuntimeError(f"无法读取详情页：{url}")


def _extract_detail(detail_html: str) -> tuple[str, str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    scope = soup.select_one(".TRS_UEDITOR, .view") or soup
    paragraphs = [_clean_text(p.get_text(" ", strip=True)) for p in scope.select("p")]
    text = _clean_text(" ".join(p for p in paragraphs if p))

    name = ""
    for paragraph in paragraphs:
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", paragraph):
            name = paragraph
            break

    if name:
        match = re.search(rf"{re.escape(name)}，.*?现任(?P<duty>.+?)[。；;]", text)
        if match:
            return name, _clean_duty(match.group("duty"))

    match = re.search(r"(?P<name>[\u4e00-\u9fff]{2,4})，[^。；;]*?现任(?P<duty>.+?)[。；;]", text)
    if match:
        return match.group("name"), _clean_duty(match.group("duty"))
    return "", ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析西藏自治区民政厅领导信息列表，并从详情页抽取姓名。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    records = []
    seen_names: set[str] = set()
    for link in soup.select(".gl-list li a.e[href]"):
        href = link.get("href", "")
        detail_url = urljoin(final_url, href)
        try:
            name, duty = _extract_detail(_fetch_detail_html(detail_url))
        except Exception:
            name, duty = "", ""
        if not name or not duty or name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url=detail_url,
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary="list=.gl-list a.e; detail=text regex name + 现任 duty",
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
