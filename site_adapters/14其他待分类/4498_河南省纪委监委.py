from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    "rule_id": "4498",
    "page_type": "纪委监委同页强结构领导机构",
    "structure_group": "henan_discipline_supervision_combined_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "extract_mode": "custom",
    "parser": "page_henan_discipline_supervision_combined_v1",
    "leader_region_selector": ".article-cont",
    "name_selector": "允许角色标题同容器或紧邻人物容器中的a",
    "duty_selector": ".article-cont strong角色标签及机构标题",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "纪委和监委同页展示；仅保留纪委书记、副书记、常委及监委主任、副主任，排除纪委委员图片名单和监委委员；空href及onclick链接不是人物详情页。",
}


def compact_text(value: str) -> str:
    """删除页面为排版插入的空白字符。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value or "")


def valid_name(value: str) -> str:
    """清理姓名中的排版空格及民族括注，并校验字符形态。"""
    name = re.sub(r"（[^）]*）|\([^)]*\)", "", compact_text(value)).strip("，,、；;：:")
    return name if re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) else ""


def names_from_container(container: object, label_node: object) -> list[str]:
    """从单个角色对应的人物容器读取可见姓名锚点。"""
    names: list[str] = []
    for link in container.select("a"):  # type: ignore[attr-defined]
        if label_node is link:
            continue
        name = valid_name(link.get_text(" ", strip=True))
        if name and name not in names:
            names.append(name)
    return names


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按页面顺序提取允许角色，并按首次出现顺序合并同人职务。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(".article-cont")
    if region is None:
        raise RuntimeError("未找到领导机构正文 .article-cont")

    discipline_subject = "中国共产党河南省第十一届纪律检查委员会"
    supervision_subject = "河南省监察委员会"
    allowed = {
        "discipline": {"书记", "副书记", "常委"},
        "supervision": {"主任", "副主任"},
    }
    subject_by_kind = {"discipline": discipline_subject, "supervision": supervision_subject}
    current_kind = "discipline"
    ordered_names: list[str] = []
    duties_by_name: dict[str, list[str]] = {}

    for strong in region.select("strong"):
        text = compact_text(strong.get_text(" ", strip=True)).rstrip("：:")
        if text == supervision_subject:
            current_kind = "supervision"
            continue
        if text == discipline_subject:
            current_kind = "discipline"
            continue
        if text not in allowed[current_kind]:
            continue

        container = strong.parent
        names = names_from_container(container, strong)
        if not names:
            sibling = container.find_next_sibling()
            while sibling is not None:
                if sibling.select_one("strong") is not None:
                    break
                names = names_from_container(sibling, strong)
                if names:
                    break
                sibling = sibling.find_next_sibling()
        if not names:
            raise RuntimeError(f"角色{text}未找到对应姓名容器")

        duty = f"{subject_by_kind[current_kind]}{text}"
        for name in names:
            if name not in duties_by_name:
                duties_by_name[name] = []
                ordered_names.append(name)
            if duty not in duties_by_name[name]:
                duties_by_name[name].append(duty)

    if not ordered_names:
        raise RuntimeError("领导机构正文未提取到允许角色记录")
    return [
        {
            "name": name,
            "duty": "；".join(duties_by_name[name]),
            "evidence": "；".join(duties_by_name[name]),
            "detail_url": "",
            "confidence": "high",
            "parser": str(page_rule.get("parser", "")),
            "selector_summary": ".article-cont内机构标题与strong角色标签；同容器或紧邻人物容器a",
        }
        for name in ordered_names
    ]

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)}")

if __name__ == "__main__":
    main()
