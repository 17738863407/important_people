from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1974",
    "page_type": "职务分组名单页",
    "structure_group": "npc_budget_members_iframe_v1",
    "reuse_scope": "single_page",
    "load_mode": "iframe嵌入",
    "fetch_mode": "requests",
    "extract_mode": "grouped_name_list",
    "collector": "static_http",
    "parser": "parse_page",
    "leader_region_selector": "td#main_c_ysgz",
    "name_selector": "iframe[src]中的.text_a；主页面.text_b .TRS_Editor",
    "duty_selector": "iframe[src]中的.tit_a；主页面.tit_b",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "委员会组成人员",
        "end_anchor": "工作委员会",
        "include_selectors": ["td#main_c_ysgz"],
        "exclude_selectors": ["td#main_b", ".iframe_css"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "requests",
        "detail_link_selector": None,
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "主任位于同域iframe，副主任位于主页面；相邻工作动态含大量人物新闻",
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
    return re.sub(r"\s+", "", value.replace("\u3000", " ").replace("\xa0", " ")).strip()


def _valid_name(value: str) -> str:
    """只接受清理后仍符合中文姓名字符边界的文本。"""
    name = _clean_text(value)
    return name if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) else ""


def _split_group_names(raw_text: str) -> list[str]:
    """以网页双空白或标点为成员边界，保留姓名内部单个排版空格。"""
    names: list[str] = []
    for part in re.split(r"[\s\u3000]{2,}|[、,，；;]", raw_text):
        name = _valid_name(part)
        if name:
            names.append(name)
    return names


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按入口版面顺序解析主任iframe和主页面副主任名单。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("td#main_c_ysgz")
    heading = region.find("h1", recursive=False) if region else None
    if region is None or heading is None or _clean_text(heading.get_text(" ", strip=True)) != "委员会组成人员":
        raise RuntimeError("入口页未找到委员会组成人员精确区域")

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    iframe = region.find("iframe", src=True, recursive=False)
    if iframe is not None:
        iframe_url = urljoin(final_url, str(iframe["src"]))
        if urlparse(iframe_url).netloc != urlparse(final_url).netloc:
            raise RuntimeError("主任iframe不是入口页同域资源")
        response = requests.get(
            iframe_url,
            timeout=60,
            headers={"Referer": final_url, "User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        frame_soup = BeautifulSoup(response.text, "html.parser")
        duty_node = frame_soup.select_one(".right > .tit_a")
        name_node = frame_soup.select_one(".right > .text_a")
        duty = _clean_text(duty_node.get_text(" ", strip=True) if duty_node else "").rstrip("：:")
        name = _valid_name(name_node.get_text(" ", strip=True) if name_node else "")
        if duty and name:
            seen_names.add(name)
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "detail_url": "",
                    "evidence": duty,
                    "parser": page_rule["parser"],
                    "selector_summary": (
                        "strategy=iframe+css；leader=td#main_c_ysgz；"
                        "director=同域iframe .right > .tit_a/.text_a"
                    ),
                }
            )

    deputy_block = region.find("div", class_="right", recursive=False)
    if deputy_block is not None:
        duty_node = deputy_block.select_one(":scope > .tit_b")
        names_node = deputy_block.select_one(":scope > .text_b .TRS_Editor")
        duty = _clean_text(duty_node.get_text(" ", strip=True) if duty_node else "").rstrip("：:")
        raw_names = names_node.get_text("", strip=False) if names_node else ""
        for name in _split_group_names(raw_names):
            if not duty or name in seen_names:
                continue
            seen_names.add(name)
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "detail_url": "",
                    "evidence": duty,
                    "parser": page_rule["parser"],
                    "selector_summary": (
                        "strategy=iframe+css；leader=td#main_c_ysgz；"
                        "deputies=:scope > div.right > .tit_b/.text_b .TRS_Editor；"
                        "detail=页面无人物独立链接"
                    ),
                }
            )
    if not rows:
        raise RuntimeError("委员会组成人员区域未解析出有效姓名")
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
