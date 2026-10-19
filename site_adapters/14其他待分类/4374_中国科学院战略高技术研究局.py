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
    "rule_id": "4374",
    "page_type": "机关部门现任领导正文页",
    "structure_group": "cas_department_current_leaders_article",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "custom_cas_bmrdp_current_leaders_v1",
    "leader_region_selector": ".trs_editor_view",
    "name_selector": ".trs_editor_view p",
    "duty_selector": ".trs_editor_view p",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".trs_editor_view"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "排版空白同时出现在姓名内部和姓名之间，需按中文姓氏边界动态分词",
    "confidence": "high",
    "profile_reusable": False,
    "profile_judgement": "已核验正文职务段落和领导姓名顺序",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": ".trs_editor_view", "name_selector": ".trs_editor_view p", "duty_selector": ".trs_editor_view p", "detail_link_selector": "", "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".trs_editor_view"], "exclude_selectors": []}},
        "api": {"enabled": False, "reason": "现任领导姓名和职务直接呈现在正文HTML中"},
        "migration": {"verified_status": "verified"},
    },
}


COMMON_SURNAMES = "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍虞万支柯昝管卢莫经房裘缪干解应宗丁宣贲邓郁单杭洪包诸左石崔吉龚程嵇邢滑裴陆荣翁荀羊甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全班仰秋仲伊宫宁仇栾暴甘钭厉戎祖武符刘景詹束龙叶幸司韶郜黎蓟薄印宿白怀蒲台从鄂索咸籍赖卓蔺屠蒙池乔阴胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍郤璩桑桂濮牛寿通边扈燕冀郏浦尚农温别庄晏柴瞿阎充慕连茹习艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙东欧沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺权逯盖益桓公"


def compact(value: str) -> str:
    return re.sub(r"[\s\u00a0\u2002\u2003\u3000]+", "", value or "").strip()


def split_names(value: str) -> list[str]:
    """依据后续常见姓氏起点拆分页面中空白边界缺失的姓名串。"""
    text = compact(value)
    starts = [0]
    for index in range(2, len(text) - 1):
        if text[index] in COMMON_SURNAMES and index - starts[-1] in {2, 3, 4}:
            starts.append(index)
    starts.append(len(text))
    return [text[starts[i] : starts[i + 1]] for i in range(len(starts) - 1)]


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(".trs_editor_view")
    if root is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in root.select("p"):
        match = re.match(r"^(.+?)[：:]\s*(.+)$", paragraph.get_text("", strip=True))
        if match is None:
            continue
        duty = compact(match.group(1))
        for name in split_names(match.group(2)):
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or name in seen:
                continue
            seen.add(name)
            rows.append({"name": name, "duty": duty, "detail_url": "", "evidence": duty, "parser": str(page_rule.get("parser", "")), "selector_summary": ".trs_editor_view p职务段落+姓氏边界"})
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
