from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0558",
    "domain": "fgw.sc.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "sichuan_fgw_leader_list_detail",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_detail",
    "collector": "static_http",
    "parser": "list_detail_sichuan_fgw_leader_intro_v2",
    "leader_container_selector": "div.content.clear dl",
    "leader_start_title": "领导简介",
    "leader_end_title": "委机关内设机构",
    "detail_name_selector": ".ldxx-intro .name strong",
    "detail_duty_selector": ".ldxx-intro dl.jianjie dd",
    "detail_strategy": {
        "required": True,
        "mode": "detail_page",
        "max_detail_links": 50,
    },
    "risk_flag": "目录页仅有姓名；职务必须逐一从对应详情页简介字段取得；online会误跟随无障碍脚本跳转，需保留原始HTTP响应",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩全角空格和连续空白，不改变原始语义。"""
    return " ".join(str(value or "").replace("\u3000", " ").split())


def clean_name(value: str) -> str:
    """移除姓名中的排版空格。"""
    return clean_text(value).replace(" ", "")


def clean_duty_evidence(value: str) -> str:
    """删除独立兼任状态标记，保留全部具体兼任职务。"""
    return re.sub(r"(?:<\s*兼\s*>|[（(]\s*兼\s*[）)])", "", clean_text(value)).strip()


def fetch_detail_html(url: str) -> str:
    """在线获取当前人物详情页HTML。"""
    import requests

    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def parse_detail(html: str, list_name: str, page_rule: dict) -> tuple[str, str]:
    """读取详情页明确标注的姓名和职务字段。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    name_node = soup.select_one(str(page_rule["detail_name_selector"]))
    duty_node = soup.select_one(str(page_rule["detail_duty_selector"]))
    name = clean_name(name_node.get_text(" ", strip=True) if name_node else list_name)
    duty = clean_duty_evidence(duty_node.get_text(" ", strip=True) if duty_node else "")
    return name or list_name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导简介目录顺序逐页提取详情中的原始职务。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one(str(page_rule["leader_container_selector"]))
    source_url = final_url or str(page_rule["url"])
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    in_leader_section = False

    for child in container.children if container else []:
        if getattr(child, "name", None) == "dt":
            title = clean_text(child.get_text(" ", strip=True))
            if title == str(page_rule["leader_start_title"]):
                in_leader_section = True
                continue
            if in_leader_section or title == str(page_rule["leader_end_title"]):
                break
        if not in_leader_section or getattr(child, "name", None) != "dd":
            continue

        link = child.select_one("a[href]")
        if link is None:
            continue
        list_name = clean_name(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", list_name):
            continue

        detail_url = urljoin(source_url, str(link.get("href") or ""))
        try:
            name, duty = parse_detail(fetch_detail_html(detail_url), list_name, page_rule)
        except Exception:
            name, duty = list_name, ""

        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "parser": str(page_rule["parser"]),
                "selector_summary": "领导简介dt边界内dd姓名链接及详情页简介职务字段",
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
