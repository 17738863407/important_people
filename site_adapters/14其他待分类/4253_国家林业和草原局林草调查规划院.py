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
    "rule_id": "4253",
    "page_type": "领导班子链接列表",
    "structure_group": "林草调查规划院领导班子详情链接列表",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_forestry_ghy_leaders_v1",
    "leader_region_selector": "a[href*='/c/ghy/ldbz/']",
    "name_selector": "a[href*='/c/ghy/ldbz/']",
    "duty_selector": "链接文本中姓名后的职务",
    "detail_link_selector": "a[href*='/c/ghy/ldbz/']",
    "detail_strategy": {"required": False, "mode": "list_link"},
    "risk_flag": "同页还包含组织机构、挂靠单位等链接，必须限定领导班子详情 URL 模式。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """通过领导班子详情页 URL 模式解析姓名、职务与真实详情链接。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    base_url = final_url or str(page_rule["url"])
    for link in soup.select("a[href*='/c/ghy/ldbz/']"):
        text = re.sub(r"\s+", "", link.get_text(" ", strip=True))
        role_start = re.search(r"党委|纪委|党组|副院长|院长|副主任|主任|书记", text)
        if not role_start:
            continue
        name, duty = text[: role_start.start()], text[role_start.start() :]
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen or not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(base_url, link["href"]),
                "parser": page_rule["parser"],
                "selector_summary": "领导班子详情链接 URL 模式 /c/ghy/ldbz/",
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
