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
    "rule_id": "0356",
    "page_type": "人物列表完整页",
    "structure_group": "taiyuan_urban_title_before_colon_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "taiyuan_urban_title_before_colon_v2",
    "leader_region_selector": "div#Zoom",
    "name_selector": "人物段落冒号前标题末尾姓名",
    "duty_selector": "人物段落冒号前标题去除末尾姓名",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "正文同时含首行标题和冒号后的长篇职责，仅冒号前标题属于人物职务依据",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


FAMILY_NAME_CHARS = set(
    "赵钱孙李周吴郑王冯陈蒋沈韩杨朱秦许何吕张曹金魏陶姜谢邹喻柏章苏潘葛范彭鲁韦昌马苗方俞任袁柳鲍史唐费薛雷贺倪汤滕罗毕郝安常乐于傅齐康伍余顾孟平黄穆萧尹姚邵汪毛戴宋庞熊舒屈董梁杜阮席季麻贾路江颜郭梅盛林钟徐邱骆高夏蔡田胡霍万柯管卢莫房解应宗丁邓杭洪包左石崔龚程邢陆翁曲封储靳段焦巴车侯全班秋仲宫宁仇甘祖武符刘詹龙叶司黎白蒲从索赖卓蒙池乔翟谭劳姬申冉雍桑桂牛通边尚温庄晏柴阎连古易戈廖耿时关查游权曾饶丰海钮"
)


def clean_text(value: str) -> str:
    """合并排版空白，并清理中文标点两侧的无意义空格。"""
    text = re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()
    return re.sub(r"\s*([、，；：])\s*", r"\1", text)


def split_title(title: str) -> tuple[str, str]:
    """从冒号前标题末尾识别二至四字姓名，保留其前完整职务原文。"""
    compact = clean_text(title).rstrip("：:")
    for length in range(4, 1, -1):
        name = compact[-length:]
        if re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name) and name[0] in FAMILY_NAME_CHARS:
            evidence = compact[:-length].strip("，、； ")
            if evidence:
                return name, evidence
    return "", ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按正文顺序解析“职务姓名：职责”段落，仅以冒号前标题作为职务证据。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select("div#Zoom")
    if len(regions) != 1:
        raise RuntimeError(f"领导正文数量异常：{len(regions)}")

    records: list[object] = []
    seen_names: set[str] = set()
    for paragraph in regions[0].select("p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        title = re.split(r"[：:]", text, maxsplit=1)[0] if re.search(r"[：:]", text) else ""
        name, evidence = split_title(title)
        if not name:
            continue
        if name in seen_names:
            raise RuntimeError(f"人物姓名重复：{name}")
        if paragraph.select_one("a[href]") is not None:
            raise RuntimeError(f"人物段落出现未审计链接：{name}")
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url="",
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    if not records:
        raise RuntimeError("领导正文没有可验证的冒号标题人物段落")
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
