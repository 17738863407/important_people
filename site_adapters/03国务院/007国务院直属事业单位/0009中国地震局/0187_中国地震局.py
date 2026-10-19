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
    "rule_id": "0187",
    "page_type": "多人物详情合并页",
    "structure_group": "cea_leader_navigation_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "custom",
    "collector": "browser_dom",
    "parser": "builtin_parse_page",
    "leader_region_selector": "a[id='5513304'] + div.sy2_ul li",
    "name_selector": "li a[href]开头姓名字段",
    "duty_selector": "姓名字段后的原始文本",
    "detail_link_selector": "a[id='5513304'] + div.sy2_ul li a[href]",
    "detail_strategy": {"required": False, "mode": "list_card_link"},
    "risk_flag": "普通HTTP可能受访问防护，需公共在线浏览器链路取得领导导航",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def _split_name_duty(value: str) -> tuple[str, str]:
    matched = re.match(r"^\s*([\u4e00-\u9fff·\u3000]{2,9})[ \t\r\n]+(.+)$", value)
    if matched is None:
        return "", ""
    name = re.sub(r"[\s\u3000]+", "", matched.group(1))
    return name, _clean_text(matched.group(2))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析“领导之窗”导航中的当前人物、原始职务和独立详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    leader_anchor = soup.find("a", id="5513304")
    nav_box = leader_anchor.find_next_sibling("div", class_="sy2_ul") if leader_anchor else None
    if nav_box is None:
        raise RuntimeError("中国地震局领导之窗导航未找到")

    records: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for link in nav_box.select("li a[href]"):
        name, evidence = _split_name_duty(link.get_text("", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence:
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        resolved_url = urljoin(final_url, link.get("href", ""))
        detail_url = "" if resolved_url.rstrip("/") == final_url.rstrip("/") else resolved_url
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_url,
                "parser": page_rule["parser"],
                "selector_summary": "领导之窗a[id='5513304']后续div.sy2_ul；锚点开头姓名、剩余文本职务；href详情",
            }
        )
    if not records:
        raise RuntimeError("中国地震局领导之窗导航未解析到人物记录")
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
