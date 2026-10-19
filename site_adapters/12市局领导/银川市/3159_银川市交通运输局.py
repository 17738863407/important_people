from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3159",
    "page_type": "人物列表完整页",
    "structure_group": "yinchuan_transport_role_name_colon_paragraphs_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "custom_parse_page",
    "parser": "yinchuan_transport_role_name_colon_paragraphs_v1",
    "leader_region_selector": "div.view.TRS_UEDITOR.trs_word.trs_web",
    "name_selector": ":scope p",
    "duty_selector": ":scope p",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "人物标题冒号后是职责，须只解析冒号前“职务+姓名”并排除后续分管联系段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _compact_text(value: str) -> str:
    """移除人物标题中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", value).strip()


def _split_role_and_name(title: str) -> tuple[str, str]:
    """按可核验职务边界拆分标题末尾姓名，并保留姓名后的挂职标记。"""
    compact = _compact_text(title).strip("：:")
    suffix_match = re.search(r"(（[^）]+）)$", compact)
    suffix = suffix_match.group(1) if suffix_match else ""
    core = compact[: suffix_match.start()] if suffix_match else compact
    match = re.fullmatch(
        r"(?P<duty>.*?(?:书记|主任|委员|调研员|局长))"
        r"(?P<name>[\u3400-\u9fff·]{2,4})",
        core,
    )
    if not match:
        return "", ""
    suffix = "" if suffix in {"（挂职）", "(挂职)"} else suffix
    return match.group("name"), f"{match.group('duty')}{suffix}"


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按正文顺序只解析冒号前人物职务标题，不纳入职责与分工段。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    regions = soup.select(page_rule["leader_region_selector"])
    if len(regions) != 1:
        raise RuntimeError(f"领导正文区域命中数量异常：{len(regions)}")

    records: list[object] = []
    seen_names: set[str] = set()
    for paragraph in regions[0].select("p"):
        text = paragraph.get_text(" ", strip=True)
        if "：" not in text and ":" not in text:
            continue
        title = re.split(r"[：:]", text, maxsplit=1)[0]
        name, evidence = _split_role_and_name(title)
        if not name or not evidence:
            continue
        if name in seen_names:
            raise RuntimeError(f"领导姓名重复：{name}")
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url="",
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
        )

    if not records:
        raise RuntimeError("领导正文中未找到可核验的职务姓名标题")
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
