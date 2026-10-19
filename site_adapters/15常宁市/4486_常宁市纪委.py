from __future__ import annotations

import re
import sys
from collections import OrderedDict
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
    """合并页面排版空白。"""
    text = re.sub(r"[\s\u2000-\u200f\u202a-\u202e\u2060\u3000\xa0]+", " ", value or "").strip()
    return re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", text)


def clean_name(value: str) -> str:
    """清除页面附在姓名后的性别标记。"""
    text = clean_text(value).replace(" ", "")
    return re.sub(r"[（(]女[）)]$", "", text)


def normalize_role(value: str) -> str:
    """移除仅说明排序方式的括注，保留实际职务。"""
    text = clean_text(value).rstrip("：: ")
    return re.sub(r"[（(]按姓氏笔画为序[）)]$", "", text).strip()


def parse_page(
    html: str, final_url: str, page_rule: dict[str, object]
) -> list[dict[str, str]]:
    """按首个届次委员会分组顺序抽取，排除按笔画排序的委员版块。"""
    soup = BeautifulSoup(html or "", "html.parser")
    section = soup.select_one(".right_cont p.ldt")
    if section is None:
        raise RuntimeError("领导机构页面缺少届次委员会标题")
    section_title = clean_text(section.get_text(" ", strip=True))
    group_list = section.find_next_sibling("ul", class_="ld")
    if group_list is None or not section_title:
        raise RuntimeError("届次委员会标题后缺少领导分组列表")

    people: OrderedDict[str, dict[str, object]] = OrderedDict()
    for item in group_list.find_all("li", recursive=False):
        label = item.find("b")
        raw_role = clean_text(label.get_text(" ", strip=True) if label else "")
        if "按姓氏笔画为序" in raw_role:
            continue
        role = normalize_role(raw_role)
        if not role:
            continue
        duty = f"{section_title}{role}"
        for anchor in item.find_all("a"):
            name = clean_name(anchor.get_text(" ", strip=True))
            if re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) is None:
                continue
            href = clean_text(str(anchor.get("href") or ""))
            detail_url = urljoin(final_url, href) if href else ""
            record = people.setdefault(name, {"duties": [], "detail_url": ""})
            duties = record["duties"]
            if isinstance(duties, list) and duty not in duties:
                duties.append(duty)
            if detail_url and not record["detail_url"]:
                record["detail_url"] = detail_url

    rows: list[dict[str, str]] = []
    for name, record in people.items():
        duties = record["duties"]
        if not isinstance(duties, list) or not duties:
            continue
        duty = "；".join(str(item) for item in duties)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": str(record["detail_url"]),
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "首个届次委员会下书记、副书记和常委分组的姓名链接；排除按姓氏笔画排序的委员版块",
            }
        )
    if not rows:
        raise RuntimeError("届次委员会领导分组未提取到人物")
    return rows


PAGE_RULE = {
    "rule_id": "4486",
    "page_type": "届次委员会领导分组列表",
    "structure_group": "changning_discipline_committee_groups_v1",
    "reuse_scope": "same_site_same_structure",
    "load_mode": "浏览器渲染在线页面",
    "extract_mode": "grouped_list",
    "parser": "page_changning_discipline_committee_groups_v1",
    "leader_region_selector": ".right_cont 首个 p.ldt 及其相邻 ul.ld",
    "name_selector": "各职务分组中的姓名链接",
    "duty_selector": "当前届次委员会标题与职务分组标签",
    "detail_link_selector": "页面为人物提供链接时使用该独立详情页；未提供时留空",
    "detail_strategy": {"required": False, "mode": "optional_current_person_link"},
    "locator_strategy": "custom_parse_page",
    "risk_flag": "页面并列展示纪律检查委员会和监察委员会；仅取首个届次委员会，并排除按姓氏笔画排序的委员版块",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
