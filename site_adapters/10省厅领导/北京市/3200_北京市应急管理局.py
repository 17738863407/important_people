from __future__ import annotations
import html as html_lib
import re
import sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3200", "domain": "yjglj.beijing.gov.cn", "page_type": "人物表格页",
    "structure_group": "beijing_emergency_js_leader_arrays_v1", "reuse_scope": "single_page",
    "load_mode": "接口数据加载", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "page_inline_beijing_emergency_js_leader_arrays_v1",
    "risk_flag": "人物由页面JS数组生成；必须按数组赋值顺序关联姓名、职务HTML和详情路径",
    "confidence": "high", "locator_strategy": "custom_parse_page",
}


def compact_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").replace("\u200b", ""))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    paths = re.findall(r"urls\[i\]\s*=\s*'([^']*)';", html)
    headers = re.findall(r"headers\[i\]\s*=\s*'(.*?)';", html, re.S)
    names = re.findall(r"ldname\[i\]\s*=\s*'([^']*)';", html)
    if not (len(paths) == len(headers) == len(names)):
        raise RuntimeError(f"领导数组长度不一致：urls={len(paths)}, headers={len(headers)}, ldname={len(names)}")
    rows: list[dict[str, str]] = []
    for path, header, raw_name in zip(paths, headers, names, strict=True):
        name = compact_text(raw_name)
        header_html = html_lib.unescape(header)
        evidence = compact_text(BeautifulSoup(header_html, "html.parser").get_text("", strip=True))
        duty = evidence.removesuffix("。").strip()
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or not duty:
            continue
        rows.append({"name": name, "duty": duty, "detail_url": urljoin(final_url, path),
                     "evidence": duty, "confidence": "high", "parser": str(page_rule.get("parser", "")),
                     "selector_summary": "页面JS数组ldname/headers/urls同索引字段"})
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
