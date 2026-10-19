from __future__ import annotations

import sys
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2323',
 'domain': 'sft.gansu.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'browser_dom',
 'parser': 'custom_gansu_sft_visible_leader_groups_v1',
 'leader_region_selector': 'a.sz[href], a.sz1[href]',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'max_detail_links': 50},
 'risk_flag': '第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'a.sz[href], a.sz1[href]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线页面采集领导链接并逐页解析现任职务'}}}


def clean_text(text: str) -> str:
    return " ".join((text or "").replace("\u3000", " ").replace("\xa0", " ").split())


def clean_name(text: str) -> str:
    return "".join(clean_text(text).split())


def fetch_detail_html(detail_url: str, referer: str) -> str:
    """在线读取人物详情页；HTTP 防护页时降级到现有 Chrome CDP。"""
    try:
        response = requests.get(
            detail_url,
            headers={"User-Agent": "Mozilla/5.0", "Referer": referer},
            timeout=20,
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        return response.text
    except requests.RequestException:
        from crawler_core.fetcher import fetch_by_chrome_debug

        return fetch_by_chrome_debug(detail_url, timeout=45).html


def extract_current_duty(detail_html: str) -> tuple[str, str]:
    """提取详情页 .ldcon 中“职务”标签对应的真实字段。"""
    detail_soup = BeautifulSoup(detail_html, "html.parser")
    region = detail_soup.select_one(".ldcon")
    if region is None:
        return "", ""
    label = next(
        (
            node
            for node in region.find_all("strong")
            if re.sub(r"[\s：:]", "", clean_text(node.get_text(" ", strip=True))) == "职务"
        ),
        None,
    )
    if label is None:
        return "", ""
    label_paragraph = label.find_parent("p")
    if label_paragraph is None:
        return "", ""
    for duty_node in label_paragraph.find_all_next("p"):
        if region not in duty_node.parents:
            break
        duty = clean_text(duty_node.get_text(" ", strip=True)).rstrip("。；; ")
        duty = re.sub(r"\s*[（(]\s*兼\s*[）)]", "", duty)
        if not duty:
            continue
        if re.sub(r"[\s：:]", "", duty) in {"个人基本信息", "工作分工"}:
            return "", ""
        return duty, duty
    return "", ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    candidates: list[tuple[int, str, str]] = []
    seen: set[str] = set()

    for link in soup.select("a.sz[href], a.sz1[href]"):
        name = clean_name(link.get_text(" ", strip=True)) or clean_name((link.find("img") or {}).get("alt", ""))
        if not name or name in seen:
            continue
        if not (2 <= len(name) <= 4):
            continue
        detail_url = urljoin(final_url, link.get("href") or "")
        candidates.append((len(candidates), name, detail_url))
        seen.add(name)

    if not candidates:
        raise RuntimeError("领导介绍页中未发现可验证的人物详情链接")

    duties: dict[int, tuple[str, str]] = {}
    with ThreadPoolExecutor(max_workers=4, thread_name_prefix="gansu_sft_detail") as executor:
        future_map = {
            executor.submit(fetch_detail_html, detail_url, final_url): (order, name, detail_url)
            for order, name, detail_url in candidates
        }
        for future in as_completed(future_map):
            order, name, detail_url = future_map[future]
            try:
                duty, evidence = extract_current_duty(future.result())
            except Exception as error:
                raise RuntimeError(f"详情页读取失败：{name}：{error}") from error
            if not duty or not evidence:
                raise RuntimeError(f"详情页缺少可验证职务字段：{name}")
            duties[order] = (duty, evidence)

    rows: list[dict] = []
    for order, name, detail_url in candidates:
        duty, evidence = duties[order]
        output_detail_url = detail_url
        if output_detail_url.rstrip("/") == final_url.rstrip("/"):
            output_detail_url = ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": output_detail_url,
                "evidence": evidence,
                "selector_summary": "领导介绍可见姓名链接+分组职务",
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
