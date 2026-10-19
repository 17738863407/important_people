from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2933",
    "page_type": "人物列表完整页",
    "structure_group": "wulumuqi_foreign_affairs_name_duty_pairs_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "wulumuqi_foreign_affairs_name_duty_pairs_v2",
    "leader_region_selector": "#NewsContent .gjnr",
    "name_selector": "过滤空段后的奇数位姓名段",
    "duty_selector": "姓名后相邻非空段的现任职务字段",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "姓名与现任职务段之间存在多个空段，姓名可能含中间点和排版空格",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """合并段落排版空白并规范中间点两侧空格。"""
    text = re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()
    return re.sub(r"\s*·\s*", "·", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """过滤直属空段后按顺序严格解析姓名与现任职务对。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select("#NewsContent .gjnr")
    if len(regions) != 1:
        raise RuntimeError(f"领导正文区域数量异常：{len(regions)}")
    items = [
        clean_text(node.get_text(" ", strip=True))
        for node in regions[0].select(":scope > p")
        if clean_text(node.get_text(" ", strip=True))
    ]
    if len(items) % 2 != 0:
        raise RuntimeError(f"姓名与职务非空段数量不是偶数：{len(items)}")

    records: list[object] = []
    seen_names: set[str] = set()
    for index in range(0, len(items), 2):
        name = items[index].replace(" ", "")
        evidence = items[index + 1]
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
            raise RuntimeError(f"人物姓名段结构异常：{name}")
        if not evidence.startswith("现任职务：") or not evidence.removeprefix("现任职务：").strip():
            raise RuntimeError(f"人物职务段结构异常：{name}={evidence}")
        if name in seen_names:
            raise RuntimeError(f"人物姓名重复：{name}")
        duty = evidence.removeprefix("现任职务：").strip()
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url="",
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    if not records:
        raise RuntimeError("领导正文没有可验证姓名与职务对")
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
