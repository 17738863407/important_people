from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1439",
    "page_type": "人物列表完整页",
    "structure_group": "lanzhou_grain_xml_name_duty_list_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_lanzhou_grain_xml_name_duty_list_v2",
    "leader_region_selector": "div[id='112118']中的领导之窗数据",
    "name_selector": "领导记录p开头至首个职务关键词前（清理姓名内部排版空格）",
    "duty_selector": "领导记录p中姓名后的职务",
    "detail_link_selector": "领导记录a[href*='art_4895_']",
    "detail_strategy": {
        "required": False,
        "mode": "dynamic_list_links",
        "detail_link_selector": "a[href*='art_4895_']",
        "max_detail_links": 20,
    },
    "risk_flag": "领导记录位于text/xml脚本中，姓名字符可能被排版空格拆开，须以职务关键词确定边界",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白。"""
    return re.sub(
        r"[\s\u3000\xa0]+",
        " ",
        str(text or ""),
    ).strip()


def extract_entries(html: str, final_url: str) -> list[tuple[str, str]]:
    """兼容渲染DOM与原始text/xml数据，保持领导记录顺序。"""
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[str, str]] = []
    for link in soup.select("div[id='112118'] li.clearfix a[href*='art_4895_']"):
        text_node = link.select_one("p")
        text = normalize_space(text_node.get_text(" ", strip=True) if text_node else "")
        candidates.append((text, urljoin(final_url, str(link.get("href", "")).strip())))

    if not candidates:
        pattern = re.compile(
            r"<a\s+href=[\"']([^\"']*art_4895_[^\"']+)[\"'][^>]*>\s*"
            r"<p>(.*?)</p>",
            re.IGNORECASE | re.DOTALL,
        )
        for match in pattern.finditer(html):
            text = normalize_space(BeautifulSoup(match.group(2), "html.parser").get_text(" ", strip=True))
            candidates.append((text, urljoin(final_url, match.group(1).strip())))

    entries: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for text, detail_url in candidates:
        if detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        entries.append((text, detail_url))
    return entries


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """从领导记录中按首个职务关键词拆分姓名和原始职务。"""
    entries = extract_entries(html, final_url)
    rows: list[dict[str, str]] = []
    for text, detail_url in entries:
        match = re.fullmatch(
            r"(?P<name>(?:[\u4e00-\u9fff·]\s*){2,8}?)(?P<duty>(?:党组|书记|副?局长|主任|调研员|巡视员).*)",
            text,
        )
        if not match:
            continue
        name = re.sub(r"\s+", "", match.group("name"))
        duty = normalize_space(match.group("duty"))
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "div[id='112118']领导记录顺序；p文本以首个职务关键词确定姓名职务边界",
            }
        )
    if not rows:
        raise RuntimeError("当前在线领导之窗未发现可验证的姓名职务记录")
    if len(rows) != len(entries):
        raise RuntimeError("当前在线领导之窗存在无法可靠拆分的记录")
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
