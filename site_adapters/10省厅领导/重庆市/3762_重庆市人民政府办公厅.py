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
    "rule_id": "3762", "page_type": "机构职能页负责人卡片", "structure_group": "cqgov_jgzn_responsible_card_v1",
    "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http",
    "parser": "page_inline_cqgov_jgzn_responsible_card_v1", "leader_region_selector": ".jgzn-fzrxx",
    "name_selector": ".jgzn-fzrxx li .name", "duty_selector": ".jgzn-fzrxx li .job", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"}, "confidence": "high", "filter_policy": "strong_no_wordlist",
    "risk_flag": "只解析负责人信息卡片，不扫描机构职责、内设机构或全站导航；多项现职按网页顺序保留",
    "locator_strategy": "responsible_card_name_job_fields",
}


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict[str, str]] = []
    for card in soup.select(".jgzn-fzrxx li"):
        name_node = card.select_one(".name")
        duty_node = card.select_one(".job")
        name = clean_text(name_node.get_text(" ", strip=True)).replace(" ", "") if name_node else ""
        duty = clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        duty = re.sub(r"[、，]+", "；", duty).strip("；")
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) and duty:
            rows.append({"name": name, "duty": duty, "detail_url": "", "source_text": duty, "method": page_rule["parser"], "note": "scope=responsible_card；order=card_order"})
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
