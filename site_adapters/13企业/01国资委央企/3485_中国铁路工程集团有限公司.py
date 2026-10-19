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
    "rule_id": "3485",
    "page_type": "多栏目管理团队",
    "structure_group": "crecg_four_management_sections",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "leader_region_selector": "ul.gsld1",
    "name_selector": "ul.gsld1 > li.clearfix",
    "duty_selector": "ul.gsld1 > li.clearfix p, ul.gsld1 > li.clearfix .dshcon em",
    "detail_link_selector": "ul.gsld1 > li.clearfix a[href]",
    "risk_flag": "须按导航动态采集集团公司党委常委、公司党委委员、董事会、经理层及高管四个栏目，同名人物职务去重合并",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_evidence(value: str) -> str:
    """清理单个管理栏目中的确定性格式噪声。"""
    evidence = re.sub(r"\s+", "", str(value or ""))
    evidence = re.sub(r"^现任", "", evidence)
    evidence = re.sub(r"[（(]\s*兼\s*[）)]", "", evidence)
    return evidence.strip("；;，,。 ")


def _role_signature(value: str) -> frozenset[str]:
    """生成同一“公司”指代下、忽略并列次序的职务签名。"""
    comparable = re.sub(r"^公司", "", value)
    return frozenset(part for part in re.split(r"[、，,]", comparable) if part)


def _is_redundant_evidence(candidate: str, existing: list[str]) -> bool:
    """过滤完全重复、并列次序颠倒或已被完整职务包含的短片段。"""
    candidate_comparable = re.sub(r"^公司", "", candidate)
    candidate_signature = _role_signature(candidate)
    for value in existing:
        value_comparable = re.sub(r"^公司", "", value)
        if candidate == value or candidate_signature == _role_signature(value):
            return True
        if candidate_comparable and candidate_comparable in value_comparable:
            return True
    return False


def _append_evidence(existing: list[str], candidate: str) -> None:
    """保留信息更完整的职务片段，同时维持网页栏目首次出现顺序。"""
    if _is_redundant_evidence(candidate, existing):
        return
    candidate_comparable = re.sub(r"^公司", "", candidate)
    existing[:] = [
        value
        for value in existing
        if re.sub(r"^公司", "", value) not in candidate_comparable
    ]
    existing.append(candidate)


def _parse_section(html: str, section_url: str) -> list[dict[str, str]]:
    """解析一个管理团队栏目，兼容职务句和“职务：姓名”卡片。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for item in soup.select("ul.gsld1 > li.clearfix"):
        role_node = item.select_one(".dshcon em")
        detail_node = item.select_one("a[href]")
        if role_node is not None:
            role_text = re.sub(r"\s+", "", role_node.get_text(" ", strip=True))
            role_match = re.fullmatch(r"(?P<evidence>[^：:]+)[：:](?P<name>[一-鿿·]{2,4})", role_text)
        else:
            text_node = item.select_one(":scope > p")
            item_text = re.sub(r"\s+", "", text_node.get_text(" ", strip=True) if text_node else "")
            role_match = re.fullmatch(r"(?P<name>[一-鿿·]{2,4})[，,](?P<evidence>[^。]+。)", item_text)
        if role_match is None:
            continue
        name = role_match.group("name")
        evidence = _clean_evidence(role_match.group("evidence"))
        if not evidence:
            continue
        href = str(detail_node.get("href") or "").strip() if detail_node else ""
        detail_url = ""
        if href and not href.lower().startswith(("javascript:", "mailto:")) and href != "#":
            detail_url = urljoin(section_url, href)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_url,
            }
        )
    return rows


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """动态采集四个管理团队栏目，并按首次出现顺序合并同名人物职务。"""
    from crawler_core.fetcher import fetch_by_requests

    section_titles = ("集团公司党委常委", "公司党委委员", "董事会", "经理层及高管")
    main_soup = BeautifulSoup(html, "html.parser")
    section_urls: dict[str, str] = {}
    for anchor in main_soup.select("a[href]"):
        title = re.sub(r"\s+", "", anchor.get_text(" ", strip=True))
        if title in section_titles and title not in section_urls:
            section_urls[title] = urljoin(final_url, str(anchor.get("href") or ""))
    missing_titles = [title for title in section_titles if title not in section_urls]
    if missing_titles:
        raise ValueError(f"未从管理团队导航发现栏目：{','.join(missing_titles)}")

    merged: dict[str, dict[str, object]] = {}
    for section_title in section_titles:
        section_url = section_urls[section_title]
        if section_url.rstrip("/") == final_url.rstrip("/"):
            section_html = html
            resolved_url = final_url
        else:
            fetch_result = fetch_by_requests(section_url)
            section_html = fetch_result.html
            resolved_url = fetch_result.final_url
        section_rows = _parse_section(section_html, resolved_url)
        if not section_rows:
            raise ValueError(f"栏目解析结果为空：{section_title}")
        for section_row in section_rows:
            name = section_row["name"]
            if name not in merged:
                merged[name] = {
                    "evidence": [],
                    "detail_url": "",
                }
            person = merged[name]
            evidences = person["evidence"]
            if isinstance(evidences, list):
                _append_evidence(evidences, section_row["evidence"])
            if not person["detail_url"] and section_row["detail_url"]:
                person["detail_url"] = section_row["detail_url"]

    rows: list[dict[str, str]] = []
    for name, person in merged.items():
        evidences = person["evidence"]
        evidence = "；".join(str(value) for value in evidences) if isinstance(evidences, list) else ""
        rows.append(
            {
                "order": str(len(rows) + 1),
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": str(person["detail_url"]),
                "confidence": str(page_rule.get("confidence") or "high"),
                "parser": "inline_crecg_four_management_sections_v1",
            }
        )
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
