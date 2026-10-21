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


PAGE_RULE = {
    "rule_id": "4061",
    "domain": "igg.cas.cn",
    "page_type": "图片人物块与简介",
    "structure_group": "igg_current_leader_biographies_2026",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_igg_current_leader_biographies_v1",
    "leader_region_selector": "#zoom .trs_editor_view table",
    "name_selector": "tr td:nth-of-type(3)",
    "duty_selector": "当前任职句",
    "detail_link_selector": "tr td:nth-of-type(3) a[href]",
    "detail_strategy": {"required": False, "mode": "dynamic_link"},
    "risk_flag": "简介含大量历史任职与职责分工，必须限定当前任职句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def normalize_space(value: str) -> str:
    """整理简介排版空白。"""
    return re.sub(r"\s+", "", (value or "").replace("\u3000", " ").replace("\xa0", " "))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按头像行顺序从各人物简介的当前任职句提取领导记录。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#zoom .trs_editor_view")
    if region is None:
        raise RuntimeError("未找到现任领导简介区域 #zoom .trs_editor_view")

    rows: list[dict[str, str]] = []
    for row in region.select("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 3 or cells[0].select_one("img") is None:
            continue
        text = normalize_space(cells[2].get_text(" ", strip=True))
        name_match = re.match(r"(?P<name>[\u4e00-\u9fff·]{2,6})[：:]", text)
        duty_matches = list(
            re.finditer(
                r"(?:自)?\d{4}年(?:\d{1,2}月)?(?:起)?任(?P<duty>(?:中国科学院)?地质与地球物理研究所[^，。；]+)",
                text,
            )
        )
        if name_match is None or not duty_matches:
            continue
        name = name_match.group("name")
        duty = duty_matches[-1].group("duty")
        link = cells[2].select_one("a[href]")
        detail_url = urljoin(final_url, str(link.get("href", ""))) if link else ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "parser": str(page_rule["parser"]),
                "selector_summary": "#zoom简介表格头像行；姓名冒号边界 + 最后一个当前任职句",
            }
        )
    if not rows:
        raise RuntimeError("现任领导简介未解析出可验证的当前任职记录")
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
