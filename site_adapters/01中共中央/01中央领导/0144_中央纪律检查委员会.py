from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean_text(value: str) -> str:
    """压缩 HTML 文本中的换行、全角空格和连续空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def clean_name(value: str) -> str:
    """删除姓名后的性别、民族等括号备注。"""
    import re

    text = clean_text(value).replace(" ", "")
    text = re.sub(r"（[^）]+）", "", text)
    return text


def normalize_duty(value: str) -> str:
    """保留核心职务，去掉排序和会议说明。"""
    duty = clean_text(value).replace(" ", "")
    duty = duty.split("（", 1)[0]
    return duty


def extract_current_duty(detail_url: str, name: str) -> tuple[str, str]:
    """进入个人页的完整简历二级页面，提取以“现任”起始的现职原文。"""
    import re
    import time

    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_by_raw_requests

    time.sleep(0.4)
    result = fetch_by_raw_requests(detail_url, timeout=30)
    soup = BeautifulSoup(result.html, "lxml")
    profile = soup.select_one(".grjj")
    if profile is None:
        from crawler_core.fetcher import fetch_by_playwright

        result = fetch_by_playwright(detail_url, timeout=30)
        soup = BeautifulSoup(result.html, "lxml")
        profile = soup.select_one(".grjj")
    if profile is None:
        raise RuntimeError(f"{name}详情页未找到个人简历块")
    resume_link = profile.select_one(".more3 a[href], :scope > a[href]")
    if resume_link is not None:
        resume_url = urljoin(result.final_url, str(resume_link.get("href", "")))
        time.sleep(0.4)
        result = fetch_by_raw_requests(resume_url, timeout=30)
        soup = BeautifulSoup(result.html, "lxml")
        profile = soup.select_one(".content")
        if profile is None:
            from crawler_core.fetcher import fetch_by_playwright

            result = fetch_by_playwright(resume_url, timeout=30)
            soup = BeautifulSoup(result.html, "lxml")
            profile = soup.select_one(".content")
        if profile is None:
            raise RuntimeError(f"{name}完整简历页未找到正文区域")
    text = clean_text(profile.get_text(" ", strip=True))
    match = re.search(r"现任\s*([^。！？!?]+)", text)
    if match is None:
        raise RuntimeError(f"{name}完整简历正文未找到“现任”职务")
    return clean_text(match.group(1)).replace(" ", ""), result.final_url


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析中央纪律检查委员会领导机构分组。"""
    import re

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    source_url = final_url or str(page_rule.get("url", ""))

    heading = None
    for node in soup.select(".ldjg h2.tit2"):
        if "中国共产党第二十届中央纪律检查委员会" in clean_text(node.get_text(" ", strip=True)):
            heading = node
            break
    if heading is None:
        from crawler_core.fetcher import fetch_by_playwright

        browser_result = fetch_by_playwright(source_url, timeout=30)
        source_url = browser_result.final_url
        soup = BeautifulSoup(browser_result.html, "html.parser")
        for node in soup.select(".ldjg h2.tit2"):
            if "中国共产党第二十届中央纪律检查委员会" in clean_text(node.get_text(" ", strip=True)):
                heading = node
                break
    if heading is None:
        raise RuntimeError("HTTP与无头浏览器均未找到第二十届中央纪律检查委员会分组")

    for block in heading.find_next_siblings():
        if getattr(block, "name", None) == "h2":
            break
        if "content2" not in (block.get("class") or []):
            continue
        raw_duty = clean_text("".join(span.get_text(" ", strip=True) for span in block.select("span.spa1")))
        group_duty = normalize_duty(raw_duty)
        if group_duty not in {"书记", "副书记", "常务委员会委员"}:
            continue
        for name_node in block.select("span.spa4, span.spa2"):
            link = name_node.select_one("a")
            raw_name = link.get_text(" ", strip=True) if link is not None else name_node.get_text(" ", strip=True)
            name = clean_name(raw_name)
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
                continue
            key = (name, group_duty)
            if key in seen:
                continue
            seen.add(key)
            href = str(link.get("href") or "") if link is not None else ""
            detail_url = urljoin(source_url, href) if href and not href.startswith(("#", "javascript:")) else ""
            if detail_url.rstrip("/") == source_url.rstrip("/"):
                detail_url = ""
            if not detail_url:
                rows.append(
                    {
                        "name": name,
                        "duty": group_duty,
                        "detail_url": "",
                        "evidence": group_duty,
                        "confidence": "high",
                        "parser": "page_inline_ccdi_commission_v1",
                    }
                )
                continue
            try:
                duty, detail_url = extract_current_duty(detail_url, name)
            except RuntimeError as exc:
                failure = f"抽取失败：{exc}"
                rows.append(
                    {
                        "name": name,
                        "duty": failure,
                        "detail_url": "",
                        "evidence": failure,
                        "confidence": "low",
                        "parser": "page_inline_ccdi_commission_v1",
                    }
                )
                continue
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "detail_url": detail_url,
                    "evidence": duty,
                    "confidence": "high",
                    "parser": "page_inline_ccdi_commission_v1",
                }
            )
    if not rows:
        raise RuntimeError("目标分组未解析到任何人物记录")
    return rows


PAGE_RULE = {'rule_id': '0144',
 'domain': 'www.ccdi.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_ccdi_commission_v1',
 'leader_region_selector': '.ldjg h2.tit2, .ldjg .content2',
 'name_selector': 'span.spa4, span.spa2',
 'duty_selector': 'span.spa1',
 'detail_link_selector': '.ldjg .content2 a[href]',
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
 'risk_flag': '按分组标题精确排除末尾独立“委员”分组，保留书记、副书记和常务委员会委员领导分组',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.ldjg h2.tit2, .ldjg .content2',
                     'name_selector': 'span.spa4, span.spa2',
                     'duty_selector': 'span.spa1',
                     'detail_link_selector': '.ldjg .content2 a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {'source': 'legacy_page_rule', 'verified_status': 'pending_root', 'behavior_changed': False}}}


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
