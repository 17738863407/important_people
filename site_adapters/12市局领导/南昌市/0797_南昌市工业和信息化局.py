from __future__ import annotations

import sys
from pathlib import Path


PAGE_RULE = {
    "rule_id": "0797",
    "page_type": "人物列表完整页",
    "structure_group": "nanchang_industry_separator_profile_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online",
    "parser": "page_inline_nanchang_industry_separator_profile_v1",
    "leader_region_selector": "#zoomcon",
    "name_selector": "姓名与⠂分隔符相邻文本",
    "duty_selector": "⠂后的职务字段（排除党员、党派身份）",
    "detail_link_selector": "",
    "risk_flag": "姓名与职务由特殊分隔符连接，职务段末尾混有党员或党派身份",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩网页文本中的换行、全角空格和连续空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def clean_duty(value: str) -> str:
    """从页面混合字段中确定性移除党员、党派身份后缀。"""
    duty = clean_text(value).strip("⠂ ：:")
    for marker in [",中共党员", "，中共党员", ",民盟盟员", "，民盟盟员"]:
        duty = duty.replace(marker, "")
    return duty.strip(" ，,。；;")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析领导简介正文中的姓名、原始职务字段和页面顺序。"""
    from bs4 import BeautifulSoup

    del final_url
    if not str(html or "").strip():
        raise RuntimeError("在线入口返回空页面")

    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one("#zoomcon")
    if not root:
        raise RuntimeError("权威入口未找到领导正文容器 #zoomcon")

    lines = [clean_text(text) for text in root.stripped_strings if clean_text(text)]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    index = 0
    while index < len(lines):
        line = lines[index]
        name = ""
        duty_parts: list[str] = []
        if "⠂" in line:
            before, after = line.split("⠂", 1)
            name = clean_text(before)
            if after.strip():
                duty_parts.append(after)
            elif index + 1 < len(lines):
                duty_parts.append(lines[index + 1])
                index += 1
        elif index + 1 < len(lines) and lines[index + 1].startswith("⠂"):
            name = line
            after = lines[index + 1].replace("⠂", "", 1)
            if after.strip():
                duty_parts.append(after)
            if index + 2 < len(lines) and not lines[index + 2].startswith(("主持", "分管")):
                duty_parts.append(lines[index + 2])
                index += 1
            index += 1

        raw_duty = clean_text("".join(duty_parts)).strip("⠂ ：:")
        duty = clean_duty(raw_duty)
        if name and duty and name not in seen:
            seen.add(name)
            rows.append(
                {
                    "organization": str(page_rule["organization"]),
                    "url": str(page_rule["url"]),
                    "name": name,
                    "duty": duty,
                    "detail_url": "",
                    "evidence": duty,
                    "confidence": "high",
                    "parser": "page_inline_nanchang_industry_separator_profile_v1",
                    "selector_summary": "leader=#zoomcon；name=⠂相邻姓名；duty=⠂后字段；detail=none",
                }
            )
        index += 1
    if not rows:
        raise RuntimeError("未从领导正文中提取到有效人物")
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
