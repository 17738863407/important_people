from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3931",
    "page_type": "脚本注入富文本领导卡片",
    "structure_group": "deyang_cppcc_embedded_article_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML内嵌动态模板",
    "fetch_mode": "raw_http",
    "_fetch_mode_override": True,
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "page_inline_deyang_cppcc_embedded_article_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": "#Content script中的article模板",
    "name_selector": "居中人物职务行末尾姓名",
    "duty_selector": "人物行开头主席/副主席/秘书长职务",
    "detail_link_selector": "none_article_roster",
    "risk_flag": "可见正文由JavaScript模板注入；职责说明行不得并入职务证据",
    "confidence": "high",
}


def compact_text(value: object) -> str:
    """删除模板中的排版空白与不间断空格。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def extract_embedded_article(soup: BeautifulSoup) -> BeautifulSoup:
    """从正文脚本中取得站点实际注入的领导名单模板。"""
    content = soup.select_one("#Content")
    if content is None:
        raise RuntimeError("未定位到政协领导正文容器")

    for script in content.find_all("script"):
        script_text = script.get_text("", strip=False)
        match = re.search(r"(<article>.*?</article>)", script_text, flags=re.DOTALL | re.IGNORECASE)
        if match:
            return BeautifulSoup(match.group(1), "lxml")
    raise RuntimeError("正文脚本中未找到可复现的article领导模板")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """解析模板中的人物职务行，保持页面原始展示顺序。"""
    template = extract_embedded_article(BeautifulSoup(html, "lxml"))
    role_pattern = re.compile(
        r"^(党组书记、主席|党组副书记、副主席|副主席兼秘书长|副主席)"
        r"([\u3400-\u9fff·]{2,4})$"
    )

    rows: list[dict] = []
    seen_names: set[str] = set()
    for block in template.select("article > div"):
        line = compact_text(block.get_text("", strip=True))
        match = role_pattern.fullmatch(line)
        if match is None:
            continue
        duty, name = match.groups()
        if name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "confidence": "high",
                "parser": page_rule["parser"],
                "selector_summary": "#Content脚本内article直属人物职务行",
            }
        )

    if not rows:
        raise RuntimeError("政协领导模板未提取到有效人物")
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

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
