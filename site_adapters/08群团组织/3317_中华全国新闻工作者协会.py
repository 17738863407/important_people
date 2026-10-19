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
    "rule_id": "3317",
    "page_type": "职务分组名单页",
    "structure_group": "zgjx_visible_leader_role_groups",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "leader_region_selector": ".centerbox",
    "name_selector": "h2 + ul:not(.list005) li h3 a[href], h2常务理事后的.rm > ul > li",
    "detail_link_selector": "li h3 a[href]",
    "risk_flag": "排除副主席隐藏list005重复；纳入下方常务理事，并按姓名合并跨职务重复",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return " ".join((value or "").replace("\xa0", " ").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析可见领导与常务理事分组，排除移动端重复并合并跨组同名人物。"""
    soup = BeautifulSoup(html, "html.parser")
    center = soup.select_one(".centerbox")
    if center is None:
        return []
    target_duties = {"主席", "党组书记", "副主席", "书记处书记"}
    rows: list[dict[str, str]] = []
    row_index_by_name: dict[str, int] = {}
    for heading in center.select("h2"):
        duty = _clean_text(heading.get_text(" ", strip=True))
        if duty not in target_duties:
            continue
        sibling = heading.find_next_sibling()
        while sibling is not None and sibling.name != "h2":
            classes = {str(item) for item in sibling.get("class") or []}
            if sibling.name == "ul" and "list005" not in classes:
                for link in sibling.select(":scope > li h3 a[href]"):
                    name = re.sub(r"\s+", "", link.get_text(" ", strip=True))
                    if not re.fullmatch(r"[一-鿿·]{2,4}", name):
                        continue
                    evidence = duty
                    detail_url = urljoin(final_url, str(link.get("href") or ""))
                    if name in row_index_by_name:
                        existing = rows[row_index_by_name[name]]
                        if existing["detail_url"] != detail_url:
                            raise RuntimeError(f"同一人物跨分组详情链接不一致：{name}")
                        existing["duty"] = f"{existing['duty']}；{duty}"
                        existing["evidence"] = f"{existing['evidence']}；{evidence}"
                        continue
                    row_index_by_name[name] = len(rows)
                    rows.append(
                        {
                            "order": str(len(rows) + 1),
                            "name": name,
                            "duty": duty,
                            "evidence": evidence,
                            "detail_url": detail_url,
                            "confidence": str(page_rule.get("confidence") or "high"),
                            "parser": "inline_zgjx_visible_leader_role_groups_v1",
                        }
                    )
            sibling = sibling.find_next_sibling()

    director_heading = next(
        (
            heading
            for heading in center.select("h2")
            if _clean_text(heading.get_text(" ", strip=True)) == "常务理事"
        ),
        None,
    )
    if director_heading is None:
        raise RuntimeError("未找到常务理事分组标题")
    director_title = director_heading.find_next_sibling("div", class_="rmbt")
    director_region = director_heading.find_next_sibling("div", class_="rm")
    if director_title is None or director_region is None:
        raise RuntimeError("常务理事分组缺少标题说明或姓名列表")
    director_evidence = _clean_text(director_title.get_text(" ", strip=True))
    if "常务理事" not in director_evidence:
        raise RuntimeError("常务理事分组说明与目标职务不一致")
    director_evidence = "常务理事"

    for item in director_region.select(":scope > ul > li"):
        name = re.sub(r"\s+", "", item.get_text(" ", strip=True))
        if not re.fullmatch(r"[一-鿿·]{2,4}", name):
            raise RuntimeError(f"常务理事姓名格式异常：{name!r}")
        if name in row_index_by_name:
            existing = rows[row_index_by_name[name]]
            existing_duties = existing["duty"].split("；")
            existing_evidence = existing["evidence"].split("；")
            if "常务理事" not in existing_duties:
                existing["duty"] += "；常务理事"
            if director_evidence not in existing_evidence:
                existing["evidence"] += f"；{director_evidence}"
            continue
        row_index_by_name[name] = len(rows)
        rows.append(
            {
                "order": str(len(rows) + 1),
                "name": name,
                "duty": "常务理事",
                "evidence": director_evidence,
                "detail_url": "",
                "confidence": str(page_rule.get("confidence") or "high"),
                "parser": "inline_zgjx_visible_leader_role_groups_v1",
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
