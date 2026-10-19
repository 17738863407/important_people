from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0816',
 'page_type': '人物目录详情页',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'force_browser': True,
 'extract_mode': 'list_direct',
 'parser': 'page_parse_page',
 'leader_region_selector': '.xxgk-list li a[href]',
 'name_selector': '.xxgk-list li a[href]',
 'duty_selector': '.leader-main .wrap_right dl中标题为职务的第二个dd',
 'detail_link_selector': '.xxgk-list li a[href]',
 'detail_strategy': {'required': True, 'mode': 'person_name_link'},
 'risk_flag': 'HTTP直连返回403，需浏览器渲染；目录当前5人，必须逐详情核对标题和职务字段',
 'confidence': 'high',
 'filter_policy': 'strong_no_wordlist',
 'risk_note': '仅遍历领导目录链接，详情页标题必须与列表姓名一致，职务只取明确标注的职务dl。'}


def clean_text(value: str) -> str:
    """压缩网页文本空白。"""
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析长沙市国资委领导信息列表。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".xxgk-list li a[href]"):
        name = "".join(clean_text(link.get_text(" ", strip=True)).split())
        if not name or name in seen:
            continue
        seen.add(name)
        detail_url = urljoin(final_url, str(link.get("href", "")))
        detail_result = fetch_html_with_strategy(
            detail_url,
            "online",
            force_browser=True,
        )
        detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        detail_name_node = detail_soup.select_one(".leader-details .leader-tit")
        detail_name = "".join(clean_text(detail_name_node.get_text(" ", strip=True) if detail_name_node else "").split())
        if detail_name != name:
            raise ValueError(f"领导详情标题与目录姓名不一致：{name} -> {detail_name}")

        duty = ""
        for group in detail_soup.select(".leader-main .wrap_right dl"):
            heading = group.select_one("h2")
            heading_text = "".join(clean_text(heading.get_text(" ", strip=True) if heading else "").split())
            if heading_text != "职务":
                continue
            duty_nodes = group.select("dd")
            duty = clean_text(duty_nodes[-1].get_text(" ", strip=True)) if duty_nodes else ""
            break
        if not duty:
            raise ValueError(f"领导详情页缺少明确职务字段：{name}")
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_result.final_url,
                "evidence": duty,
                "confidence": "high",
                "parser": "page_parse_page",
                "selector_summary": "目录=.xxgk-list li a[href]；详情姓名=.leader-tit；职务=标题为职务的dl第二个dd",
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
