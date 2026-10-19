from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2733",
    "page_type": "人物目录详情页",
    "structure_group": "lanzhou_statistics_leader_group_to_open_ended_resume_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_lanzhou_statistics_leader_group_to_open_ended_resume_v1",
    "leader_region_selector": ".zfxxgk_subtit文本为领导之窗的相邻.zfxxgk_subcon",
    "name_selector": ".zfxxgk_subcon a[href*='art_6371_'][title]",
    "duty_selector": "人物详情页#zoom p中无结束年月且以兰州市统计局开头的现任履历行",
    "detail_link_selector": ".zfxxgk_subcon a[href*='art_6371_'][title][href]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_list_to_detail",
        "detail_link_selector": ".zfxxgk_subcon a[href*='art_6371_'][title][href]",
        "detail_content_selector": "#zoom",
        "max_detail_links": 20,
    },
    "risk_flag": "combined_institution_page_contains_leader_and_nonleader_groups_and_resume_dates_have_split_inline_digits",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_heading_selector": ".zfxxgk_subtit",
            "leader_container_selector": ".zfxxgk_subtit + .zfxxgk_subcon",
            "leader_link_selector": "a[href*='art_6371_'][title][href]",
            "detail_content_selector": "#zoom",
        },
        "api": {
            "enabled": False,
            "reason": "当前静态领导分组提供4个动态人物链接，详情页正文直出姓名和现任履历行",
        },
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白、数字拆分和标点两侧空格。"""
    cleaned = re.sub(
        r"\s+",
        " ",
        str(text or "").replace("\u3000", " ").replace("\xa0", " "),
    ).strip()
    cleaned = re.sub(r"(?<=\d)\s+(?=\d)", "", cleaned)
    cleaned = re.sub(r"\s*([.、，。；：()（）])\s*", r"\1", cleaned)
    return re.sub(r"\s*([-—－]{1,2})\s*", r"\1", cleaned)


def fetch_detail_html(session: requests.Session, detail_url: str) -> str:
    """在线读取当前人物详情页。"""
    response = session.get(detail_url, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding or "utf-8"
    return response.text


def extract_detail_record(detail_html: str, expected_name: str) -> tuple[str, str]:
    """校验详情页姓名，并提取无结束年月的当前履历原文和职务。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    title = normalize_space(soup.title.get_text(" ", strip=True)) if soup.title else ""
    container = soup.select_one("#zoom")
    if expected_name not in re.sub(r"\s+", "", title) or container is None:
        return "", ""

    matches: list[tuple[str, str]] = []
    for paragraph in container.find_all("p"):
        text = normalize_space(paragraph.get_text(" ", strip=True))
        for match in re.finditer(
            r"(?P<start>\d{4}\.\d{2})(?P<dash>[-—－]{1,2})(?P<duty>兰州市统计局[^）)]*)",
            text,
        ):
            duty = normalize_space(match.group("duty"))
            evidence = normalize_space(match.group(0))
            if re.search(r"党组|书记|局长|副局长|调研员", duty):
                matches.append((evidence, duty))
    return matches[-1] if matches else ("", "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """限定领导之窗分组，并按列表顺序逐页提取当前履历。"""
    soup = BeautifulSoup(html, "html.parser")
    leader_heading = next(
        (
            node
            for node in soup.select(".zfxxgk_subtit")
            if normalize_space(node.get_text(" ", strip=True)) == "领导之窗"
        ),
        None,
    )
    leader_container = (
        leader_heading.find_next_sibling("div", class_="zfxxgk_subcon")
        if leader_heading
        else None
    )
    if leader_container is None:
        return []

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
    )
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    links = leader_container.select("a[href*='art_6371_'][title][href]")
    for link in links:
        name = re.sub(r"\s+", "", normalize_space(str(link.get("title", ""))))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen_names:
            continue
        detail_url = urljoin(final_url, str(link.get("href", "")).strip())
        evidence, duty = extract_detail_record(
            fetch_detail_html(session, detail_url),
            name,
        )
        if not evidence or not duty:
            raise RuntimeError(f"人物详情页未提取到当前履历：{name} {detail_url}")
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": evidence,
                "detail_url": detail_url,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "领导之窗标题锚点；仅取art_6371人物链接；详情页#zoom无结束年月现任履历行",
            }
        )
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
