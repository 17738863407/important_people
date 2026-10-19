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
    "rule_id": "0216",
    "page_type": "人物列表完整页",
    "structure_group": "第九届理事会现任领导职务组",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "ChinaCicGroupedLeaderBoxParser_v2",
    "leader_region_selector": "div.con",
    "name_selector": "职务标题后至下一职务标题前的姓名文本",
    "duty_selector": "理事长、副理事长、秘书长、副秘书长标题",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "姓名可能被多个span拆为单字且存在同名兼任；只取常务理事标题前四个现任领导组，按首次出现顺序合并同名",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ").replace("\u3000", " ")).strip()


def _split_names(value: str) -> list[tuple[str, bool]]:
    tokens = [token for token in _clean_text(value).split(" ") if token]
    names: list[tuple[str, bool]] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if (
            re.fullmatch(r"[\u4e00-\u9fff]", token)
            and index + 1 < len(tokens)
            and re.fullmatch(r"[\u4e00-\u9fff](?:[（(]兼[）)])?", tokens[index + 1])
        ):
            token += tokens[index + 1]
            index += 2
        else:
            index += 1
        concurrent = bool(re.search(r"[（(]兼[）)]", token))
        name = re.sub(r"[（(]兼[）)]", "", token)
        name = re.sub(r"[^\u4e00-\u9fff·]", "", name)
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
            names.append((name, concurrent))
    return names


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """解析第九届理事会正文前四个现任领导组，并合并同名职务。"""
    soup = BeautifulSoup(html, "html.parser")
    box = soup.select_one("div.con")
    if box is None:
        raise RuntimeError("未找到第九届理事会正文容器")

    groups: list[tuple[str, list[str]]] = []
    current_duty = ""
    current_lines: list[str] = []
    allowed_duties = {"理事长", "副理事长", "秘书长", "副秘书长"}
    for value in box.stripped_strings:
        line = _clean_text(str(value))
        if not line:
            continue
        normalized = re.sub(r"[\s：:]", "", line)
        if normalized == "常务理事":
            if current_duty and current_lines:
                groups.append((current_duty, current_lines))
            break
        if normalized in allowed_duties:
            if current_duty and current_lines:
                groups.append((current_duty, current_lines))
            current_duty = normalized
            current_lines = []
        elif current_duty:
            current_lines.append(line)
    if current_duty and current_lines:
        groups.append((current_duty, current_lines))

    records_by_name: dict[str, dict] = {}
    order: list[str] = []
    for duty, name_lines in groups:
        group_evidence = f"{duty}：{' '.join(name_lines)}"
        for name, concurrent in _split_names(" ".join(name_lines)):
            duty_text = duty
            if name not in records_by_name:
                order.append(name)
                records_by_name[name] = {"duties": [], "evidence": []}
            item = records_by_name[name]
            if duty_text not in item["duties"]:
                item["duties"].append(duty_text)
            if group_evidence not in item["evidence"]:
                item["evidence"].append(group_evidence)

    records: list[dict] = []
    for name in order:
        item = records_by_name[name]
        complete_evidence = "；".join(item["duties"])
        records.append(
            {
                "name": name,
                "duty": complete_evidence,
                "evidence": complete_evidence,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": "div.con；常务理事前四个职务组；跨span单字姓名；同名职务合并",
            }
        )
    if not records:
        raise RuntimeError("第九届理事会正文未解析到现任领导记录")
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
