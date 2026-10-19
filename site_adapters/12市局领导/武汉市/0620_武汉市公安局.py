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
    "rule_id": "0620",
    "page_type": "多人物详情合并页",
    "structure_group": "wuhan_police_article_current_sentence_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page",
    "parser": "wuhan_police_article_current_sentence_v2",
    "leader_region_selector": "#tabContent .article",
    "name_selector": "h2.tc",
    "duty_selector": ".article-box内完整现任句",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "原始响应直接包含完整人物块；online后续通道会改变页面结构，固定使用raw_http",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性清理人物块排版空白。"""
    text = re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()
    text = re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", text)
    return re.sub(r"\s*([，。；：、（）])\s*", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按人物块DOM顺序提取标题姓名和当前人物简介内完整现任句。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    articles = soup.select("#tabContent .article")

    records: list[object] = []
    seen_names: set[str] = set()
    for article in articles:
        name_node = article.select_one("h2.tc")
        content_node = article.select_one(".article-box")
        name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True) if name_node else ""))
        content = clean_text(content_node.get_text(" ", strip=True) if content_node else "")
        duty_match = re.search(r"(?P<evidence>现任[^。]*。)", content)
        if re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) is None or duty_match is None:
            raise RuntimeError(f"人物块姓名或现任句异常：{name} {content}")
        evidence = re.sub(r"^现任\s*", "", duty_match.group("evidence"))
        evidence = re.sub(r"[（(]\s*兼\s*[）)]", "", evidence).removesuffix("。").strip()
        if name in seen_names:
            raise RuntimeError(f"人物姓名重复：{name}")
        if article.select_one("a[href]") is not None:
            raise RuntimeError(f"人物块出现未审计链接：{name}")
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
        raise RuntimeError("领导信息区域没有可验证人物块")
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
