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
    "rule_id": "1807",
    "page_type": "多人物详情合并页",
    "structure_group": "wuhan_ethnic_religious_merged_leader_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page",
    "parser": "wuhan_ethnic_religious_merged_leader_v2",
    "leader_region_selector": ".leader",
    "name_selector": ".leader > ul > li > h4",
    "duty_selector": ".leader > ul > li > p",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 0},
    "risk_flag": "简历与分管工作位于同一人物块，必须仅取h4后直属p职务字段；HTTP头声明ISO-8859-1但正文为UTF-8",
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
    fields = soup.select(".leader > ul > li > h4")
    names = [re.sub(r"\s+", "", clean_text(field.get_text(" ", strip=True))) for field in fields]
    if fields and not any(re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) for name in names):
        try:
            repaired_html = (html or "").encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError) as exc:
            raise RuntimeError(f"入口页UTF-8乱码严格回转失败：{exc}") from exc
        soup = BeautifulSoup(repaired_html, "html.parser")
    return soup


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按合并领导页DOM顺序提取直属姓名与职务字段。"""
    from crawler_core.models import PersonRecord

    soup = parse_entry_soup(html)
    regions = soup.select(".leader")
    if len(regions) != 1:
        raise RuntimeError(f"领导区域数量异常：{len(regions)}")

    records: list[object] = []
    seen_names: set[str] = set()
    for item in regions[0].select(":scope > ul > li"):
        name_node = item.select_one(":scope > h4")
        duty_node = item.select_one(":scope > p")
        name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True) if name_node else ""))
        evidence = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        evidence = re.sub(r"[（(]\s*兼\s*[)）]", "", evidence).strip(" 、，")
        if re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) is None or not evidence:
            raise RuntimeError(f"领导姓名或职务字段异常：{name} {evidence}")
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
        raise RuntimeError("合并领导页没有可验证人物记录")
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
