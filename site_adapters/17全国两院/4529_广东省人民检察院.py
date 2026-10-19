from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value or "").strip()


def clean_committee_duty(value: str) -> str:
    """保留领导列表展示的全部职务，包括各类委员职务。"""
    return "、".join(clean_text(part) for part in re.split(r"[、，；;]", value) if clean_text(part))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导列表链接的实时 DOM 顺序抽取姓名、职务和个人页。"""
    soup = BeautifulSoup(html or "", "html.parser")
    candidates = []
    for region in soup.select("td.b16"):
        links = [link for link in region.select("a[href]") if "：" in clean_text(link.get_text(" ", strip=True))]
        if links:
            candidates = links
            break

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for link in candidates:
        text = clean_text(link.get_text(" ", strip=True))
        name, raw_duty = (clean_text(part) for part in text.split("：", 1))
        name = name.replace(" ", "")
        if re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) is None or name in seen_names:
            continue
        duty = clean_committee_duty(raw_duty)
        if not duty:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(final_url, str(link.get("href") or "")),
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "含姓名全角冒号的省院领导独立链接",
            }
        )
    if not rows:
        raise RuntimeError("省院领导列表未提取到姓名与职务记录")
    return rows


PAGE_RULE = {
    "rule_id": "4529",
    "page_type": "检察院领导姓名职务链接列表",
    "structure_group": "guangdong_procuratorate_leader_links_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_guangdong_procuratorate_leader_links_v1",
    "leader_region_selector": "td.b16中含姓名全角冒号的领导链接列表",
    "name_selector": "a[href]文本全角冒号前",
    "duty_selector": "a[href]文本全角冒号后",
    "detail_link_selector": "同一领导a[href]",
    "detail_strategy": {"required": False, "mode": "dynamic_link"},
    "locator_strategy": "custom_parse_page",
    "risk_flag": "排除无姓名冒号的领导简介栏目链接；领导列表内检察委员会委员、专职委员及仅任委员者全部保留",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)}")


if __name__ == "__main__":
    main()
