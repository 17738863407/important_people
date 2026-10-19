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
    "rule_id": "1460",
    "domain": "lwj.sc.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "sichuan_grain_leader_ajax_cards",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "raw_http",
    "extract_mode": "leader_card_direct",
    "collector": "static_http",
    "parser": "page_sichuan_grain_leader_cards_v2",
    "leader_data_url": "https://lwj.sc.gov.cn/sclwj/leaderinfo/leaderList.shtml",
    "leader_region_selector": ".gknr_list",
    "card_link_selector": "a[href]",
    "card_text_selector": "p",
    "name_duty_pattern": r"(?P<duty>.+?)\s+(?P<name>[\u4e00-\u9fff\s·]{2,6})$",
    "detail_strategy": {
        "required": False,
        "mode": "list_item_link",
    },
    "risk_flag": "入口页通过zwxx.js异步加载领导信息；使用脚本公开的稳定领导列表端点",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def normalize_space(value: str) -> str:
    """压缩连续空白和全角空格。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\u00a0", " ")).strip()


def clean_name(value: str) -> str:
    """移除姓名内部排版空白。"""
    return re.sub(r"\s+", "", normalize_space(value))


def fetch_leader_html(url: str) -> str:
    """在线读取入口页脚本公开的领导信息HTML端点。"""
    import requests

    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导卡片顺序提取职务、姓名和独立人物页。"""
    from bs4 import BeautifulSoup

    del html
    leader_url = str(page_rule["leader_data_url"])
    soup = BeautifulSoup(fetch_leader_html(leader_url), "html.parser")
    region = soup.select_one(str(page_rule["leader_region_selector"]))
    if region is None:
        return []

    pattern = re.compile(str(page_rule["name_duty_pattern"]))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in region.select(str(page_rule["card_link_selector"])):
        text_node = link.select_one(str(page_rule["card_text_selector"]))
        text = normalize_space(text_node.get_text(" ", strip=True) if text_node else "")
        match = pattern.search(text)
        if not match:
            continue

        name = clean_name(match.group("name"))
        duty = normalize_space(match.group("duty")).strip(" ：:，,。.")
        if name in seen or not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name):
            continue
        if not re.search(r"书记|局长|巡视员", duty):
            continue

        seen.add(name)
        href = str(link.get("href") or "").strip()
        detail_url = urljoin(leader_url, href) if href else ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "parser": str(page_rule["parser"]),
                "selector_summary": "公开领导列表端点.gknr_list内卡片p文本及a[href]",
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
