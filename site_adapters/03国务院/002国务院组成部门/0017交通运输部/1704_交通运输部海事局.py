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
    "rule_id": "1704",
    "page_type": "多人物详情合并页",
    "structure_group": "海事局领导介绍合并列表",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MsaLeaderListParser_v2",
    "leader_region_selector": "ul.leader_wrap li.leader_list",
    "name_selector": ".leader_img p:nth-of-type(2)",
    "duty_selector": ".leader_img p:nth-of-type(1)",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面为同页合并介绍且无独立人物链接；入口页不得误作详情页，履历与分工段落不得混入职务依据",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ").replace("\u3000", " ")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按领导介绍列表DOM顺序抽取独立姓名与职务节点。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for item in soup.select("ul.leader_wrap li.leader_list"):
        duty_node = item.select_one(".leader_img p:nth-of-type(1)")
        name_node = item.select_one(".leader_img p:nth-of-type(2)")
        evidence = _clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        evidence = evidence.replace("（挂职）", "").replace("(挂职)", "").strip()
        name = re.sub(r"\s+", "", _clean_text(name_node.get_text(" ", strip=True))) if name_node else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence or name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": "ul.leader_wrap li.leader_list；.leader_img前两个p；排除履历与分工；无独立详情链接",
            }
        )
    if not records:
        raise RuntimeError("海事局领导介绍列表未解析到人物记录")
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
