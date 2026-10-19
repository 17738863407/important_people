from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, NavigableString


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3441",
    "page_type": "职务分组名单页",
    "structure_group": "左侧职务分组姓名列表",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "NanjingCppccGroupedLeaderListParser_v2",
    "leader_region_selector": ".ldzc_left_bottom ul > li",
    "risk_flag": "姓名含性别民族括注；主席链接等于入口，副秘书长无链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """仅归一页面排版空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def _clean_name(value: str) -> str:
    """移除姓名后的性别、民族括注及排版空白。"""
    text = re.sub(r"（[^）]*）", "", _clean_text(value))
    return "".join(text.split())


def _direct_label(list_item: object) -> str:
    """读取姓名容器之后的直接文本职务标签。"""
    direct_text = " ".join(
        str(child)
        for child in getattr(list_item, "children", [])
        if isinstance(child, NavigableString)
    )
    return "".join(_clean_text(direct_text).split()).rstrip("：:")


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按左侧4个职务分组的DOM顺序解析姓名及可验证链接。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[str] = set()
    for list_item in soup.select(rule["leader_region_selector"]):
        evidence = _direct_label(list_item)
        name_container = list_item.find("span", recursive=False)
        if not evidence or name_container is None:
            continue
        anchors = name_container.select("a")
        name_nodes = anchors if anchors else name_container.find_all("span", recursive=False)
        for name_node in name_nodes:
            name = _clean_name(name_node.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
                continue
            href = (name_node.get("href") or "").strip() if name_node.name == "a" else ""
            detail_url = urljoin(base_url, href) if href else ""
            if detail_url.rstrip("/") == base_url.rstrip("/"):
                detail_url = ""
            seen.add(name)
            records.append(
                {
                    "name": name,
                    "duty": evidence,
                    "evidence": evidence,
                    "detail_url": detail_url,
                    "parser": rule["parser"],
                    "selector_summary": ".ldzc_left_bottom直接li：span姓名容器+直接文本职务标签",
                }
            )
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
