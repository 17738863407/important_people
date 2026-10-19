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
    "rule_id": "1211",
    "domain": "jssxfj.jiangsu.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "jiangsu_petition_static_compound_paragraphs_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_jiangsu_petition_static_compound_paragraphs_v2",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "旧画像误标接口数据加载；姓名内部可能单空格，姓名与职务边界为连续排版空格",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def preserve_space_runs(value: str) -> str:
    """统一空白字符为普通空格，但保留连续数量以识别字段边界。"""
    return re.sub(
        r"[\t\r\n\f\v\u3000\xa0\u2000-\u200b]",
        " ",
        str(value or ""),
    ).strip()


def clean_text(value: str) -> str:
    """压缩字段内部排版空白。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导之窗正文段落顺序拆分姓名与原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    selector = ".main-content-right.fdzdgknr-content > div:first-of-type > ul > p"

    for paragraph in soup.select(selector):
        text = preserve_space_runs(paragraph.get_text("", strip=False))
        match = re.fullmatch(r"([\u3400-\u9fff](?: ?[\u3400-\u9fff]){1,4}) {2,}(.+)", text)
        if match is None:
            continue
        name = re.sub(r"\s+", "", match.group(1))
        duty = clean_text(match.group(2)).strip("，,；;。 ")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")) or final_url,
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；"
                    "row=.main-content-right.fdzdgknr-content first-content-ul direct-p；"
                    "field=name-single-space-vs-duty-multiple-space-boundary"
                ),
            }
        )

    return records


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
