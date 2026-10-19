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


def clean_text(value: str) -> str:
    """清理页面排版空白，不改变正文语义。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def discover_leader_article_url(html: str, final_url: str) -> str:
    """只从“法院领导”栏目动态发现当前领导简历文章。"""
    soup = BeautifulSoup(html or "", "html.parser")
    for section in soup.select(".content"):
        heading = section.select_one(".tit_br h2, #title h2")
        if clean_text(heading.get_text(" ", strip=True) if heading else "") != "法院领导":
            continue
        for link in section.select(".list_br a[href]"):
            title = clean_text(str(link.get("title") or link.get_text(" ", strip=True)))
            href = clean_text(str(link.get("href") or ""))
            if "领导简历" in title and href:
                return urljoin(final_url, href)
        raise RuntimeError("法院领导栏目未找到领导简历文章链接")
    raise RuntimeError("入口页未找到标题为“法院领导”的栏目")


def extract_leader_rows(detail_html: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按详情正文顺序将姓名字段与其后的现任职务字段配对。"""
    soup = BeautifulSoup(detail_html or "", "html.parser")
    region = soup.select_one(".detail > .text")
    if region is None:
        raise RuntimeError("领导简历文章未找到正文区域 .detail > .text")

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    current_name = ""
    for paragraph in region.select("p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        if text.startswith("姓名：") or text.startswith("姓名:"):
            if current_name:
                raise RuntimeError(f"人物 {current_name} 缺少现任职务字段")
            current_name = clean_text(re.split(r"[：:]", text, maxsplit=1)[1]).replace(" ", "")
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", current_name):
                raise RuntimeError(f"领导简历姓名字段异常：{text}")
            if current_name in seen_names:
                raise RuntimeError(f"领导简历姓名重复：{current_name}")
            continue
        if not (text.startswith("现任职务：") or text.startswith("现任职务:")):
            continue
        if not current_name:
            raise RuntimeError("现任职务字段前未找到对应姓名")
        evidence = clean_text(re.split(r"[：:]", text, maxsplit=1)[1]).rstrip("。；; ")
        rows.append(
            {
                "name": current_name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".detail > .text中按姓名与现任职务标签成组",
            }
        )
        seen_names.add(current_name)
        current_name = ""

    if current_name:
        raise RuntimeError(f"人物 {current_name} 缺少现任职务字段")
    if not rows:
        raise RuntimeError("领导简历文章未提取到姓名与现任职务记录")
    return rows


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """从入口页发现领导简历文章，再按正文原始顺序抽取人物。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    if BeautifulSoup(html or "", "html.parser").select_one(".detail > .text") is not None:
        return extract_leader_rows(html, page_rule)
    article_url = discover_leader_article_url(html, final_url)
    detail = fetch_html_with_strategy(
        article_url,
        strategy="requests",
        timeout=30,
        referer=final_url,
    )
    return extract_leader_rows(detail.html, page_rule)


PAGE_RULE = {
    "rule_id": "4431",
    "domain": "qhgy.qhwsfy.gov.cn",
    "page_type": "法院概况入口转领导简历文章",
    "structure_group": "qinghai_high_court_leader_article_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态入口页并动态请求领导简历文章",
    "extract_mode": "list_to_detail",
    "parser": "page_qinghai_high_court_leader_article_v1",
    "leader_region_selector": ".content中标题为法院领导的栏目",
    "name_selector": ".detail > .text p中的姓名标签值",
    "duty_selector": ".detail > .text p中的现任职务标签值",
    "detail_link_selector": ".content .list_br a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_shared_article",
        "detail_collector_type": "requests",
        "max_detail_links": 1,
    },
    "locator_strategy": "custom_parse_page",
    "risk_flag": "入口含法院简介、机构职能等相邻栏目；只进入法院领导栏目的领导简历文章，文章为多人共用依据页，不作为人物独立详情页；领导文章内的审判委员会委员、专职委员等均属于目标领导记录，完整保留网页现任职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
