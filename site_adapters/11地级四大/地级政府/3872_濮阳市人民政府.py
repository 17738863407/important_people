from __future__ import annotations
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """调用入口页公开使用的领导JSON接口并按接口数组顺序抽取。"""
    import requests
    session = requests.Session(); session.trust_env = False
    response = session.post("https://www.puyang.gov.cn/japi/sldList", timeout=35, verify=False)
    response.raise_for_status(); payload = response.json(); rows = []
    for item in payload.get("rows", []):
        name, duty = clean_text(item.get("name", "")).replace(" ", ""), clean_text(item.get("post", ""))
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) and duty:
            detail = urljoin(final_url or "https://www.puyang.gov.cn/", f"/zwxx/zfld-show.thtml?id={item.get('id')}")
            rows.append({"name": name, "duty": "", "evidence": duty, "detail_url": detail,
                         "confidence": "high", "parser": "page_inline_puyang_public_leader_api_v1"})
    return rows

PAGE_RULE = {"rule_id": "3872", "page_type": "公开JSON接口", "load_mode": "入口HTML指向公开接口",
             "fetch_mode": "raw_http", "_fetch_mode_override": True, "extract_mode": "json_api",
             "parser": "page_inline_puyang_public_leader_api_v1", "api_url": "https://www.puyang.gov.cn/japi/sldList",
             "api_method": "POST", "array_path": "rows", "name_field": "name", "duty_field": "post",
             "locator_strategy": "custom_parse_page", "risk_flag": "", "confidence": "high"}

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")

if __name__ == "__main__": main()
