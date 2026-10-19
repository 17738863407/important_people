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
    "rule_id": "1975",
    "page_type": "职务分组名单页",
    "structure_group": "npc_overseas_committee_iframe",
    "load_mode": "iframe嵌入",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "requests",
    "parser": "page_npc_overseas_committee_iframe_v1",
    "leader_region_selector": 'iframe[src*="hqwyh2023012"]',
    "name_selector": ".list1 li.font12, .text2",
    "duty_selector": ".list1 li.text0, .text1",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "仅读取组成人员iframe，排除图片报道、页眉页脚和其他委员会导航",
    "confidence": "high",
}


def _extract_names(text: str) -> list[str]:
    """从角色字段后的文本中提取中文姓名，排除性别、职务等辅助信息。"""
    text = text.replace("\u3000", " ").replace("\u00a0", " ")
    text = re.sub(r"（[^）]*）|\([^)]*\)", " ", text)
    tokens = []
    for token in re.split(r"\s+", text.strip()):
        tokens.extend(re.findall(r"[\u4e00-\u9fff]+", token))

    names = []
    seen = set()
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if len(token) == 1 and index + 1 < len(tokens) and len(tokens[index + 1]) == 1:
            name = token + tokens[index + 1]
            index += 2
        else:
            name = token
            index += 1

        if name in {"主任委员", "副主任", "委员会", "华侨", "全国人大", "按姓名笔划为序排列"}:
            continue
        if 2 <= len(name) <= 4 and name not in seen:
            names.append(name)
            seen.add(name)
    return names


def _normalize_role(text: str) -> str:
    text = re.sub(r"[\s\u3000\xa0]+", "", text)
    if text == "主任委员":
        return "主任委员"
    if text == "副主任委员":
        return "副主任委员"
    if text == "委员" or text.startswith("委员（"):
        return "委员"
    return ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """在线读取组成人员iframe，仅输出主任委员和副主任委员分组。"""
    import requests
    from bs4 import BeautifulSoup

    outer_soup = BeautifulSoup(html, "html.parser")
    iframe = outer_soup.select_one('iframe[src*="hqwyh2023012"]')
    if iframe is None:
        return []
    iframe_url = urljoin(final_url, str(iframe.get("src") or ""))
    response = requests.get(
        iframe_url,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0", "Referer": final_url},
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    iframe_soup = BeautifulSoup(response.text, "html.parser")

    groups: list[tuple[str, list[str]]] = []
    director = iframe_soup.select_one(".right_xinxi .list1")
    if director is not None:
        duty_node = director.select_one("li.text0")
        name_node = director.select_one("li.font12")
        duty = _normalize_role(duty_node.get_text(" ", strip=True) if duty_node else "")
        names = _extract_names(name_node.get_text(" ", strip=True) if name_node else "")
        if duty in {"主任委员", "副主任委员"} and names:
            groups.append((duty, names))

    for duty_node in iframe_soup.select(".right_xinxi > .text1"):
        duty = _normalize_role(duty_node.get_text(" ", strip=True))
        names_node = duty_node.find_next_sibling("div", class_="text2")
        names = _extract_names(names_node.get_text(" ", strip=True) if names_node else "")
        if duty == "副主任委员" and names:
            groups.append((duty, names))

    rows: list[dict[str, str]] = []
    for duty, names in groups:
        for name in names:
            rows.append(
                {
                    "organization": str(page_rule.get("organization", "")),
                    "url": str(page_rule.get("url", "")),
                    "name": name,
                    "duty": duty,
                    "detail_url": "",
                    "evidence": duty,
                    "confidence": "high",
                    "parser": "page_npc_overseas_committee_iframe_v1",
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
