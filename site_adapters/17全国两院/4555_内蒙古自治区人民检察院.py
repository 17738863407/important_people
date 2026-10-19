from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """合并页面排版空白，不改变正文语义。"""
    return re.sub(r"[\s\u2000-\u200f\u202a-\u202e\u2060\u3000\xa0]+", " ", value or "").strip()


def find_leader_groups(soup: BeautifulSoup) -> list[tuple[str, Tag]]:
    """按页面顺序定位院领导、专职委员，并以检委会委员为结束边界。"""
    groups: list[tuple[str, Tag]] = []
    for node in soup.select("#adminTbody > .duoji"):
        title_link = node.select_one(":scope > span > a")
        title = clean_text(title_link.get_text(" ", strip=True) if title_link else "")
        if title == "检委会委员":
            break
        if title not in {"院领导", "专职委员"}:
            continue
        for sibling in node.next_siblings:
            if not isinstance(sibling, Tag):
                continue
            classes = {str(item) for item in (sibling.get("class") or [])}
            if "duoji" in classes:
                break
            if "pclm" in classes:
                groups.append((title, sibling))
                break
    if [title for title, _ in groups] != ["院领导", "专职委员"]:
        raise RuntimeError(f"领导分组异常：{[title for title, _ in groups]}")
    return groups


def parse_page(
    html: str, final_url: str, page_rule: dict[str, object]
) -> list[dict[str, str]]:
    """按院领导、专职委员两个分组提取，遇检委会委员分组即停止。"""
    soup = BeautifulSoup(html or "", "html.parser")
    groups = find_leader_groups(soup)
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for group_title, leader_list in groups:
        for link in leader_list.select(":scope > li > a[href]"):
            source_text = clean_text(link.get_text(" ", strip=True))
            parts = re.split(r"[：:]", source_text, maxsplit=1)
            if len(parts) != 2:
                continue
            name = re.sub(r"\s+", "", parts[0])
            evidence = clean_text(parts[1]).strip("，,、；;。 ")
            if re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) is None or not evidence:
                continue
            if name in seen_names:
                raise RuntimeError(f"领导分组出现重复人物：{name}")
            detail_url = urljoin(final_url, str(link.get("href") or "").strip())
            parsed_detail = urlparse(detail_url)
            parsed_entry = urlparse(final_url)
            if parsed_detail.scheme not in {"http", "https"} or parsed_detail.netloc != parsed_entry.netloc:
                detail_url = ""
            seen_names.add(name)
            rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": detail_url, "source_text": source_text, "confidence": "high", "parser": str(page_rule.get("parser", "")), "selector_summary": f"#adminTbody中{group_title}分组的桌面.pclm完整列表"})
    if not rows:
        raise RuntimeError("领导分组未提取到有效人物记录")
    return rows


PAGE_RULE = {
    "rule_id": "4555",
    "domain": "www.nm.jcy.gov.cn",
    "page_type": "多分组领导列表页",
    "structure_group": "nm_procuratorate_grouped_leader_list_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态请求跳转异常时由统一链路降级到浏览器渲染",
    "extract_mode": "list_direct",
    "parser": "page_nm_procuratorate_grouped_leader_list_v1",
    "leader_region_selector": "#adminTbody中检委会委员分组之前的院领导、专职委员分组",
    "name_selector": "院领导与专职委员分组链接冒号前",
    "duty_selector": "院领导与专职委员分组链接冒号后",
    "detail_link_selector": "院领导与专职委员分组桌面.pclm li a[href]",
    "detail_strategy": {"required": True, "mode": "paired_row_link"},
    "locator_strategy": "custom_parse_page",
    "risk_flag": "同页含移动端重复列表；仅按桌面端院领导、专职委员两个分组原序提取，检委会委员标题作为结构结束边界且该分组不采集",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(
        PAGE_RULE,
        globals(),
        runtime_context=runtime_context,
        update_fetch_memory=False,
    )
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
