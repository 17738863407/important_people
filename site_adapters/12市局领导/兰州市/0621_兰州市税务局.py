from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0621",
    "page_type": "多人物详情合并页",
    "structure_group": "gansu_tax_current_profile_and_leader_sidebar_v1",
    "reuse_scope": "single_page",
    "load_mode": "浏览器渲染",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_gansu_tax_current_profile_and_leader_sidebar_v1",
    "leader_region_selector": ".ldxx",
    "name_selector": ".ldxx-m个人简介首句姓名；.ldlist li第三个a",
    "duty_selector": ".ldxx-m个人简介完整现任句；.ldlist li第一个a",
    "detail_link_selector": ".ldlist li a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "dynamic_list_links",
        "detail_link_selector": ".ldlist li a[href]",
        "max_detail_links": 20,
    },
    "risk_flag": "current_profile_is_outside_sidebar_and_iframes_are_only_auxiliary_widgets",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "current_profile_selector": ".ldxx-m .ld-list p",
            "sidebar_row_selector": ".ldxx-r .ldlist li",
            "sidebar_link_selector": "a",
        },
        "api": {
            "enabled": False,
            "reason": "当前浏览器渲染DOM直接包含当前人物简介和领导专栏列表；页面iframe仅为访问统计与日期控件",
        },
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白。"""
    return re.sub(
        r"\s+",
        " ",
        str(text or "").replace("\u3000", " ").replace("\xa0", " "),
    ).strip()


def append_row(
    rows: list[dict[str, str]],
    seen_names: set[str],
    name: str,
    duty: str,
    evidence: str,
    detail_url: str,
    page_rule: dict,
    selector_summary: str,
) -> None:
    """校验人物强结构字段并追加记录。"""
    clean_name = re.sub(r"\s+", "", normalize_space(name))
    clean_duty = normalize_space(duty)
    clean_duty = re.sub(r"^现任\s*", "", clean_duty).removesuffix("。").strip()
    clean_evidence = normalize_space(evidence)
    if clean_evidence in {f"{clean_duty}：{clean_name}", f"{clean_duty}:{clean_name}"}:
        clean_evidence = clean_duty
    clean_evidence = re.sub(r"^现任\s*", "", clean_evidence).removesuffix("。").strip()
    if (
        not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", clean_name)
        or not clean_duty
        or clean_name in seen_names
    ):
        return
    seen_names.add(clean_name)
    rows.append(
        {
            "name": clean_name,
            "duty": clean_duty,
            "evidence": clean_evidence,
            "detail_url": detail_url,
            "parser": str(page_rule.get("parser", "")),
            "selector_summary": selector_summary,
        }
    )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """先取当前主职人物，再按侧栏顺序提取其余领导。"""
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(".ldxx")
    if root is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for paragraph in root.select(".ldxx-m .ld-list p"):
        text = normalize_space(paragraph.get_text(" ", strip=True))
        name_match = re.match(r"([\u4e00-\u9fff·]{2,8})[，,]", text)
        evidence_match = re.search(r"现任[^。]*。", text)
        if name_match is None or evidence_match is None:
            continue
        evidence = evidence_match.group(0)
        append_row(
            rows,
            seen_names,
            name_match.group(1),
            evidence,
            evidence,
            "",
            page_rule,
            "当前人物简介首句姓名及同一简介块完整现任句；入口页本身不重复写入详情链接",
        )
        break

    for item in root.select(".ldxx-r .ldlist li"):
        links = item.select("a")
        if len(links) < 3:
            continue
        duty = normalize_space(links[0].get_text(" ", strip=True))
        name = normalize_space(links[2].get_text(" ", strip=True))
        href = str(links[2].get("href", "")).strip()
        append_row(
            rows,
            seen_names,
            name,
            duty,
            f"{duty}：{name}",
            urljoin(final_url, href),
            page_rule,
            "领导专栏侧栏li第一个a原始职务、第三个a姓名及其动态人物详情链接",
        )
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
