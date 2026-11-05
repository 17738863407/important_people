from __future__ import annotations
import sys
from pathlib import Path
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    "rule_id": "4504",
    "page_type": "图片型纪委监委领导名单",
    "structure_group": "jiangxi_discipline_supervision_vision_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML跳转后图片",
    "extract_mode": "custom",
    "parser": "page_jiangxi_discipline_supervision_vision_v2",
    "leader_region_selector": "最新文章正文唯一领导名单PNG",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "requests",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "完整提取当前省纪委监委班子成员名单图片中的明确成员，包括省监委委员；不得扩展到图片外的普通纪委全体委员或新闻人物。",
    "vision_strategy": {
        "required": True,
        "provider": "deepseek_v4_flash_vision_exp",
        "mode": "deepseek_vision_json",
        "target_image_selector": "img[src*='W020'][src$='.png']",
        "prompt_path": "workspace/prompts/DeepSeek视觉人物抽取_v1.txt",
        "prompt_version": "deepseek_vision_v1",
        "tile_edge": 3000,
        "evidence_validation": "exact_normalized_substring",
        "instruction": "逐字转写整张图片。标题为省纪委监委班子成员名单，必须按自上而下逐行原序完整提取标题所辖全部明确成员，包括仅任省监委委员并兼任驻省级单位纪检监察组组长者；不按职务等级缩窄名单，不扩展到图片外普通纪委全体委员。每人raw_duty完整保留该行全部原始职务，不补写机构前缀，evidence回指同次逐字转写，详情页为空。",
    },
}

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    entry = requests.get(str(page_rule["url"]), timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    entry.raise_for_status()
    entry_text = entry.content.decode("gb18030", errors="replace")
    redirect = re.search(r"URL=([^'\"]+)", entry_text, re.I)
    article_url = urljoin(entry.url, redirect.group(1)) if redirect else entry.url
    article = requests.get(article_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    article.raise_for_status()
    soup = BeautifulSoup(article.content.decode("gb18030", errors="replace"), "html.parser")
    image = soup.select_one("img[src*='W020'][src$='.png']")
    if image is None:
        raise RuntimeError("最新领导机构文章未发现领导名单PNG")
    if len(soup.select("img[src*='W020'][src$='.png']")) != 1:
        raise RuntimeError("当前领导正文包含多张候选PNG，需重新核验图片边界")
    from crawler_core.vision_llm import parse_vision_llm_records

    rows = parse_vision_llm_records(page_rule, str(soup), article.url, 180)
    if not rows:
        raise RuntimeError("同次视觉转写未返回本页班子成员记录")
    return rows

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)}")

if __name__ == "__main__":
    main()
