from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1282",
    "page_type": "人物详情页",
    "structure_group": "jiangxi_finance_right_leader_iframe_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "parse_page",
    "leader_region_selector": "iframe[src*='/col/col38667/']",
    "name_selector": ".ld_list a[href]",
    "duty_selector": ".leader_fg02中包含现任句的简介节点",
    "detail_link_selector": ".ld_list a[href]经栏目页解析出的独立人物详情页",
    "detail_strategy": {
        "required": True,
        "mode": "iframe_list_to_detail",
        "detail_collector_type": "requests",
        "detail_link_selector": ".ld_list a[href]经栏目页在线文章数组解析",
        "detail_name_selector": ".leader_introduce",
        "detail_duty_selector": ".leader_fg02中的现任句",
        "detail_content_selector": ".leader_fg02",
        "max_detail_links": 4,
    },
    "risk_flag": "入口为首位人物详情页，完整4人名单位于右侧iframe；须保持右栏顺序并逐栏目取得详情页",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
}


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def _clean_text(value: str) -> str:
    """确定性清理网页排版空白。"""
    text = re.sub(r"\s+", " ", value.replace("\u3000", " ").replace("\xa0", " ")).strip()
    return re.sub(r"(?<=[\u4e00-\u9fff、，])\s+(?=[\u4e00-\u9fff、，。])", "", text)


def _clean_name(value: str) -> str:
    """清理并校验中文姓名。"""
    name = re.sub(r"\s+", "", value)
    return name if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) else ""


def _fetch_page(url: str) -> tuple[str, str]:
    """通过项目运行环境读取当前官方站点的可用 HTTP 页面。"""
    parts = urlsplit(url)
    if parts.netloc.lower() == "jxjr.jiangxi.gov.cn" and parts.scheme == "https":
        url = urlunsplit(("http", parts.netloc, parts.path, parts.query, parts.fragment))
    session = requests.Session()
    response = session.get(url, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text, response.url


def _find_detail_url(index_html: str, index_url: str) -> str:
    """从领导栏目页的在线文章数组中提取当前人物独立详情页。"""
    match = re.search(
        r"/jxsdfjrjdglj/col/col\d+/content/content_\d+\.html",
        index_html,
    )
    if match is None:
        raise RuntimeError(f"领导栏目页未找到独立详情链接：{index_url}")
    return urljoin(index_url, match.group(0))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按右侧领导iframe顺序逐栏目解析4名领导的详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    frame = soup.select_one(page_rule["leader_region_selector"])
    frame_src = frame.get("src", "") if frame else ""
    if not frame_src:
        raise RuntimeError("入口详情页未找到右侧领导iframe")

    frame_url = urljoin(final_url, frame_src)
    frame_html, frame_final_url = _fetch_page(frame_url)
    frame_soup = BeautifulSoup(frame_html, "html.parser")
    leader_links = frame_soup.select(".ld_list a[href]")
    if not leader_links:
        raise RuntimeError("右侧领导iframe未找到人物栏目链接")

    rows: list[dict[str, str]] = []
    for leader_link in leader_links:
        index_url = urljoin(frame_final_url, leader_link.get("href", ""))
        index_html, index_final_url = _fetch_page(index_url)
        detail_url = _find_detail_url(index_html, index_final_url)
        detail_html, detail_final_url = _fetch_page(detail_url)
        detail_soup = BeautifulSoup(detail_html, "html.parser")

        name_node = detail_soup.select_one(".leader_introduce")
        name = _clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        evidence = ""
        for node in detail_soup.select(".leader_fg02"):
            text = _clean_text(node.get_text(" ", strip=True))
            match = re.search(r"现任[^。]*。", text)
            if match:
                evidence = re.sub(r"^现任\s*", "", match.group(0)).removesuffix("。").strip()
                break
        if not name or not evidence:
            raise RuntimeError(f"人物详情页未解析出姓名或完整现任职务句：{detail_final_url}")
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": detail_final_url,
                "evidence": evidence,
                "parser": page_rule["parser"],
                "selector_summary": (
                    "strategy=iframe_list_to_detail；frame=.ld_list a[href]；"
                    "detail=.leader_introduce+.leader_fg02当前人物简介内现任句；"
                    "exclude=.leader_brief分管工作"
                ),
            }
        )
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
