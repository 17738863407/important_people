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
    "rule_id": "1768",
    "page_type": "人物列表完整页",
    "structure_group": "wuhan_civil_affairs_leader_list_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page",
    "parser": "wuhan_civil_affairs_leader_list_v2",
    "leader_region_selector": ".modify_leader ul.leader_list",
    "name_selector": ":scope > li > h4 > span:first-of-type",
    "duty_selector": ":scope > li > h4 > span:nth-of-type(2)",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 0},
    "risk_flag": "职责div与职务并列，必须仅取h4第二个span；HTTP头声明ISO-8859-1但正文为UTF-8",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性合并页面排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_entry_soup(html: str) -> BeautifulSoup:
    """必要时严格回转错误HTTP字符集造成的UTF-8乱码。"""
    soup = BeautifulSoup(html or "", "html.parser")
    fields = soup.select(".modify_leader ul.leader_list > li > h4 > span:first-of-type")
    names = [re.sub(r"\s+", "", clean_text(field.get_text(" ", strip=True))) for field in fields]
    if fields and not any(re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) for name in names):
        try:
            repaired_html = (html or "").encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError) as exc:
            raise RuntimeError(f"入口页UTF-8乱码严格回转失败：{exc}") from exc
        soup = BeautifulSoup(repaired_html, "html.parser")
    return soup


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按领导列表DOM顺序提取h4中的姓名与原始职务字段。"""
    from crawler_core.models import PersonRecord

    soup = parse_entry_soup(html)
    regions = soup.select(".modify_leader ul.leader_list")
    if len(regions) != 1:
        raise RuntimeError(f"领导区域数量异常：{len(regions)}")

    records: list[object] = []
    seen_names: set[str] = set()
    for item in regions[0].select(":scope > li"):
        fields = item.select(":scope > h4 > span")
        if len(fields) != 2:
            raise RuntimeError(f"领导姓名职务字段数量异常：{len(fields)}")
        name = re.sub(r"\s+", "", clean_text(fields[0].get_text(" ", strip=True)))
        evidence = clean_text(fields[1].get_text(" ", strip=True))
        if re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) is None or not evidence:
            raise RuntimeError(f"领导姓名或职务异常：{name} {evidence}")
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
        raise RuntimeError("领导列表没有可验证人物记录")
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
