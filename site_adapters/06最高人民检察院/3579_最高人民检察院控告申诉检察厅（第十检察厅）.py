from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def normalize_space(text: str) -> str:
    """清理网页排版空白，不改变职务语义。"""
    value = re.sub(r"\s+", " ", str(text or "").replace("\xa0", " ")).strip()
    return re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", value)


def clean_name(text: str) -> str:
    """删除强结构姓名字段中的全部排版空白。"""
    return re.sub(r"\s+", "", str(text or "").replace("\xa0", " ")).strip()


def clean_duty(text: str) -> str:
    """删除末尾分隔符和仅说明展示顺序的附注。"""
    duty = normalize_space(text).strip(" ：:，,。.")
    duty = re.sub(r"[（(]按(?:姓名|姓氏)笔画(?:为序|排序|排列)[）)]", "", duty)
    return normalize_space(duty).strip(" ：:，,。.")


def is_name(text: str) -> bool:
    """校验强结构姓名字段中的常见中文姓名形式。"""
    return bool(re.fullmatch(r"[\u3400-\u9fff·]{2,4}", text))


def split_names(text: str) -> list[str]:
    """按页面使用的全角空格或普通空白拆分多人姓名。"""
    normalized = str(text or "").replace("\xa0", " ").strip()
    return [clean_name(part) for part in re.split(r"[\s\u3000]+", normalized) if clean_name(part)]


def append_row(
    rows: list[dict[str, str]],
    seen_names: set[str],
    name: str,
    duty: str,
    parser: str,
    selector_summary: str,
) -> None:
    """追加一条经过强结构校验的人物记录。"""
    if duty == "检察官":
        return
    if not is_name(name) or not duty or name in seen_names:
        return
    seen_names.add(name)
    rows.append(
        {
            "name": name,
            "duty": duty,
            "evidence": duty,
            "detail_url": "",
            "parser": parser,
            "selector_summary": selector_summary,
        }
    )


def build_page_rule(rule_id: str) -> dict[str, object]:
    """构造当前页面经过在线核验的技术规则。"""
    return {
        "rule_id": rule_id,
        "domain": "www.spp.gov.cn",
        "page_type": "图片后职务姓名强结构",
        "structure_group": "spp_internal_department_duty_name_blocks_2026",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "duty_name_pairs_and_multiline_group",
        "collector": "static_http",
        "parser": "page_spp_internal_department_multiline_duty_name_blocks_v1",
        "leader_region_selector": "#fontzoom",
        "name_selector": ".spanright, 居中职务名单段落及连续纯姓名段落",
        "duty_selector": ".spanleft, 居中名单首段冒号前职务标题",
        "detail_link_selector": "",
        "content_scope": {
            "include_selectors": ["#fontzoom"],
            "exclude_selectors": ["style", "script"],
        },
        "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
        "risk_flag": "verified_static_article_with_portrait_span_pairs_and_two_paragraph_name_group",
        "confidence": "high",
        "filter_policy": "strong_no_wordlist",
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": "#fontzoom",
                "portrait_selector": ":scope > p > img",
                "pair_duty_selector": ":scope > .spanleft",
                "pair_name_selector": ":scope > .spanright",
                "group_selector": "p[style*='text-align: center']",
            },
            "api": {"enabled": False, "reason": "静态HTML正文已直接包含职务和姓名强结构"},
        },
    }


def is_centered(paragraph: Tag) -> bool:
    """判断段落是否为页面用于人物名单的居中段落。"""
    style = re.sub(r"\s+", "", str(paragraph.get("style", "")).lower())
    return "text-align:center" in style


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按正文顺序解析单人左右栏和跨连续段落的职务姓名名单。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#fontzoom")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    parser = str(page_rule.get("parser", ""))
    current_group_duty = ""
    selector_summary = (
        "strategy=custom_parse_page；region=#fontzoom；portrait=p>img仅作区域结构证据；"
        "pair=.spanleft+.spanright；group=居中冒号段落+紧邻纯姓名续段；detail=none"
    )
    for paragraph in region.find_all("p", recursive=False):
        if not isinstance(paragraph, Tag):
            continue
        duty_node = paragraph.select_one(":scope > .spanleft")
        name_node = paragraph.select_one(":scope > .spanright")
        if duty_node is not None and name_node is not None:
            current_group_duty = ""
            duty = clean_duty(duty_node.get_text(" ", strip=True))
            name = clean_name(name_node.get_text(" ", strip=True))
            append_row(rows, seen_names, name, duty, parser, selector_summary)
            continue

        raw_text = paragraph.get_text(" ", strip=True)
        match = re.fullmatch(r"\s*(?P<duty>[^：:]+)[：:]\s*(?P<names>.+?)\s*", raw_text)
        if match is not None and is_centered(paragraph):
            current_group_duty = clean_duty(match.group("duty"))
            for name in split_names(match.group("names")):
                append_row(rows, seen_names, name, current_group_duty, parser, selector_summary)
            continue

        continuation_names = split_names(raw_text)
        if current_group_duty and is_centered(paragraph) and continuation_names and all(
            is_name(name) for name in continuation_names
        ):
            for name in continuation_names:
                append_row(rows, seen_names, name, current_group_duty, parser, selector_summary)
        elif raw_text:
            current_group_duty = ""
    return rows


def main(rule_id: str) -> None:
    """运行当前页面级在线爬虫并禁止更新公共采集记忆。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(
        build_page_rule(rule_id),
        globals(),
        runtime_context=runtime_context,
        update_fetch_memory=False,
    )
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"尝试链路：{runtime_context.get('attempted_collectors', [])}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "3579"
    main(rule_id_value)
