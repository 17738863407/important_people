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
    "rule_id": "2927",
    "page_type": "人物列表完整页",
    "structure_group": "wulumuqi_education_leader_cards_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "wulumuqi_education_leader_cards_v2",
    "leader_region_selector": "#list-data ul.list",
    "name_selector": "li p span a[href]",
    "duty_selector": "li p b",
    "detail_link_selector": "li p span a[href]",
    "detail_strategy": {"required": True, "mode": "list_link"},
    "risk_flag": "人物姓名可能含中间点且长度超过四字，必须按强结构卡片字段校验",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """合并卡片字段排版空白，不改变职务语义。"""
    text = re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()
    return re.sub(r"\s*·\s*", "·", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按卡片DOM顺序解析姓名、职务节点和独立详情链接。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    lists = soup.select("#list-data ul.list")
    if len(lists) != 1:
        raise RuntimeError(f"领导卡片列表数量异常：{len(lists)}")
    base_url = final_url or page_rule["url"]

    records: list[object] = []
    seen_names: set[str] = set()
    for item in lists[0].select(":scope > li"):
        name_nodes = item.select("p span a[href]")
        duty_nodes = item.select("p b")
        if len(name_nodes) != 1 or len(duty_nodes) != 1:
            raise RuntimeError(f"领导卡片字段数量异常：姓名={len(name_nodes)}，职务={len(duty_nodes)}")
        name = clean_text(name_nodes[0].get_text(" ", strip=True)).replace(" ", "")
        evidence = clean_text(duty_nodes[0].get_text(" ", strip=True))
        detail_url = urljoin(base_url, str(name_nodes[0].get("href") or ""))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
            raise RuntimeError(f"卡片姓名结构异常：{name}")
        if not evidence or name in seen_names:
            raise RuntimeError(f"人物职务异常或姓名重复：{name}")
        if not detail_url or detail_url.rstrip("/") == base_url.rstrip("/"):
            raise RuntimeError(f"人物详情链接异常：{name}")
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url=detail_url,
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    if not records:
        raise RuntimeError("领导卡片列表没有可验证人物")
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
