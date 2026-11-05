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
    "inline_parser_handles_fetch": True, "inline_fetch_collector": "raw_http",
    "rule_id": "3975", "domain": "www.fuzhou.gov.cn", "page_type": "机构职责页领导简介",
    "structure_group": "fuzhou_department_profile_numbered_leaders", "reuse_scope": "fuzhou_government_profile_platform",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct", "collector": "static_http",
    "parser": "page_fuzhou_profile_numbered_leaders_v1", "leader_region_selector": "#detailCont .Custom_UnionStyle",
    "name_selector": "p", "duty_selector": "p",
    "content_scope": {"include_selectors": ["#detailCont .Custom_UnionStyle"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "职责、简历、分工和机构设置混排，须限定领导简介并匹配序号姓名括号职务段",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "#detailCont .Custom_UnionStyle", "record_selector": "p"}, "text_pattern": "序号.姓名（职务）"},
}


def normalize_text(value: str) -> str:
    """删除富文本字段中的排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """限定领导简介，以编号姓名为人物边界，仅取对应简介中的明确现任句。"""
    if not html:
        from crawler_core.fetcher import fetch_html_with_strategy
        # 正文含“债务信息系统维护”，不能把这个正常职责词误判为整站维护页。
        html = fetch_html_with_strategy(str(page_rule["url"]), strategy="raw_http").html
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#detailCont .TRS_Editor, #detailCont .Custom_UnionStyle")
    if region is None:
        raise RuntimeError("未找到机构职责页面的正文区域")
    for node in region.select('script, style, [hidden], [aria-hidden="true"], [style*="display:none"], [style*="display: none"]'):
        node.decompose()
    blocks: list[tuple[str, str, list[str]]] = []
    in_leaders = False
    for paragraph in region.select("p"):
        text = normalize_text(paragraph.get_text(" ", strip=True))
        if text == "三、领导简介":
            in_leaders = True
            continue
        if not in_leaders:
            continue
        if re.match(r"^[四五六七八九十]+、", text):
            break
        match = re.fullmatch(r"\d+[.．、]([\u3400-\u9fff·]{2,8})(?:[（(](.+)[）)])?", text)
        if match:
            name, heading_duty = match.groups()
            blocks.append((name, heading_duty or "", []))
        elif blocks and text:
            blocks[-1][2].append(text)
    rows: list[dict[str, str]] = []
    for name, heading_duty, paragraphs in blocks:
        evidence = heading_duty
        for text in paragraphs:
            if text.startswith("个人简历"):
                current = re.search(r"现任([^。]+)(?:。|$)", text)
                if current:
                    evidence = current.group(1)
            if text.startswith("工作分工"):
                concurrent = re.search(r"[，,；;](兼(?!顾)[^。；;，,]+)[。]?$", text)
                if concurrent and concurrent.group(1) not in evidence:
                    evidence = "；".join(x for x in (evidence, concurrent.group(1)) if x)
        # 姓名明确但未公开职务的记录保留空证据，交由人工复核，不从职责推断。
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": "", "parser": str(page_rule.get("parser", "")), "selector_summary": "领导简介内编号姓名边界；同人物简介现任句与明确兼任句"})
    if not rows:
        raise RuntimeError("领导简介未解析出明确人物")
    return rows


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
