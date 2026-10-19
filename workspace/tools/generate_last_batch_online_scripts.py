from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path
from pprint import pformat

try:
    from workspace.tools.project_paths import resolve_project_path
except ModuleNotFoundError:
    from project_paths import resolve_project_path


def write_log(log_path: Path, message: str) -> None:
    """同时向控制台和日志文件写入处理进度。"""
    print(message)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as file:
        file.write(message + "\n")


def load_business_records(rule_table_path: Path) -> list[dict[str, object]]:
    """读取启用的业务记录；规则主表不再承载页面技术配置。"""
    project_dir = rule_table_path.resolve().parents[2]
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.rule_table import load_generation_records

    return load_generation_records(rule_table_path)


def text_value(record: dict[str, object], key: str) -> str:
    """按字段名读取文本，并统一处理空值和首尾空白。"""
    value = record.get(key, "")
    return "" if value is None else str(value).strip()


def normalize_rule_id(value: str, fallback_index: int) -> str:
    """将 RULE_0001 等规则编号转换为四位数字字符串。"""
    match = re.search(r"(\d+)", str(value or ""))
    return match.group(1).zfill(4) if match else str(fallback_index).zfill(4)


def collect_existing_script_sequences(adapter_dir: Path) -> set[str]:
    """递归收集已有适配器脚本序号，防止重复生成。"""
    sequences: set[str] = set()
    if not adapter_dir.exists():
        return sequences
    for script_path in adapter_dir.rglob("*.py"):
        match = re.match(r"(\d+)_", script_path.name)
        if match:
            sequences.add(match.group(1).zfill(4))
    return sequences


def is_baike_or_placeholder(record: dict[str, object]) -> str:
    """仅依据业务字段识别百度百科和占位记录。"""
    organization = text_value(record, "机构")
    url = text_value(record, "领导信息链接")
    note = text_value(record, "备注")
    combined_text = " ".join([organization, url, note])
    if "baike.baidu.com" in combined_text.lower() or "百度百科" in combined_text:
        return "百度百科"
    if note in {"异常占位", "空缺占位"}:
        return "占位"
    return ""


def make_script_name(rule_id: str, organization: str) -> str:
    """待分析脚本统一使用“脚本序号_机构名称”命名。"""
    from crawler_core.naming import build_script_name

    return build_script_name(rule_id, organization)


def build_pending_page_rule(rule_id: str) -> dict[str, object]:
    """构造明确不可运行的待分析技术规则，所有技术值必须在脚本内复核。"""
    return {
        "rule_id": rule_id,
        "configuration_status": "pending",
        "page_type": "待分析",
        "structure_group": "",
        "reuse_scope": "single_page",
        "load_mode": "待分析",
        "fetch_mode": "disabled",
        "extract_mode": "待分析",
        "collector": "",
        "parser": "",
        "leader_region_selector": "",
        "name_selector": "",
        "duty_selector": "",
        "detail_link_selector": "",
        "content_scope": {
            "start_anchor": "",
            "end_anchor": "",
            "include_selectors": [],
            "exclude_selectors": [],
        },
        "detail_strategy": {"required": False, "mode": "none"},
        "risk_flag": "尚未分析网页结构，禁止直接运行",
        "confidence": "unverified",
        "profile_reusable": False,
        "profile_judgement": "待逐页分析",
        "filter_policy": "",
    }


def make_script_content(page_rule: dict[str, object]) -> str:
    """生成待配置脚本；完成网页分析前主动阻止运行。"""
    rule_text = pformat(page_rule, sort_dicts=False, width=120)
    return f'''from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def build_page_rule() -> dict[str, object]:
    """返回当前页面的技术规则；所有技术配置只在本脚本内维护。"""
    return {rule_text}


def main() -> None:
    """运行当前页面级爬虫。"""
    page_rule = build_page_rule()
    if page_rule.get("configuration_status") != "verified":
        raise RuntimeError("当前脚本仍处于待分析状态，请先核验网页并在脚本内填写技术规则")

    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(page_rule, globals())
    print(f"输出文件：{{output_path}}")


if __name__ == "__main__":
    main()
'''


def select_missing_records(
    rows: list[dict[str, object]],
    existing_sequences: set[str],
) -> tuple[list[tuple[str, dict[str, object]]], Counter[str]]:
    """筛选尚无脚本且不属于百科或占位的业务记录。"""
    selected: list[tuple[str, dict[str, object]]] = []
    skip_reasons: Counter[str] = Counter()
    for index, record in enumerate(rows, start=1):
        rule_id_text = text_value(record, "规则ID")
        if not rule_id_text:
            skip_reasons["空白规则ID"] += 1
            continue
        rule_id = normalize_rule_id(rule_id_text, index)
        if rule_id in existing_sequences:
            skip_reasons["脚本已存在"] += 1
            continue
        if not text_value(record, "领导信息链接"):
            skip_reasons["无领导信息链接"] += 1
            continue
        excluded_reason = is_baike_or_placeholder(record)
        if excluded_reason:
            skip_reasons[excluded_reason] += 1
            continue
        selected.append((rule_id, record))
    return selected, skip_reasons


def write_manifest(manifest_path: Path, rows: list[list[str]]) -> None:
    """导出UTF-8制表符清单。"""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as file:
        for row in rows:
            cleaned = [str(value or "").replace("\t", " ").replace("\r", " ").replace("\n", " ") for value in row]
            file.write("\t".join(cleaned) + "\n")


def generate_scripts(
    rule_table_path: Path,
    adapter_dir: Path,
    output_dir: Path,
    manifest_path: Path,
    log_path: Path,
) -> None:
    """为尚无脚本的业务记录生成安全的待分析脚本骨架。"""
    if log_path.exists():
        log_path.unlink()
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = load_business_records(rule_table_path)
    existing_sequences = collect_existing_script_sequences(adapter_dir)
    selected_records, skip_reasons = select_missing_records(rows, existing_sequences)
    write_log(log_path, f"读取业务规则主表：{rule_table_path}")
    write_log(log_path, f"业务记录数：{len(rows)}")
    write_log(log_path, f"已有脚本序号数：{len(existing_sequences)}")
    write_log(log_path, f"待生成分析骨架数：{len(selected_records)}")
    for reason, count in skip_reasons.most_common():
        write_log(log_path, f"跳过原因：{reason}={count}")

    try:
        from tqdm import tqdm
    except Exception:
        tqdm = None

    manifest_rows: list[list[str]] = [["脚本序号", "机构", "依据链接", "配置状态", "脚本路径"]]
    iterator = tqdm(selected_records, desc="生成待分析脚本") if tqdm else selected_records
    for rule_id, record in iterator:
        try:
            organization = text_value(record, "机构")
            url = text_value(record, "领导信息链接")
            script_path = output_dir / make_script_name(rule_id, organization)
            page_rule = build_pending_page_rule(rule_id)
            script_path.write_text(make_script_content(page_rule), encoding="utf-8")
            manifest_rows.append([rule_id, organization, url, "待逐页分析", str(script_path)])
        except Exception as error:
            write_log(log_path, f"生成失败：{rule_id} {text_value(record, '机构')}，原因：{error}")

    write_manifest(manifest_path, manifest_rows)
    write_log(log_path, f"生成待分析脚本数：{len(manifest_rows) - 1}")
    write_log(log_path, f"生成清单：{manifest_path}")


def main(
    rule_table_path: Path,
    adapter_dir: Path,
    output_dir: Path,
    manifest_path: Path,
    log_path: Path,
) -> None:
    """统一入口函数。"""
    generate_scripts(rule_table_path, adapter_dir, output_dir, manifest_path, log_path)


if __name__ == "__main__":
    rule_table_path_value = resolve_project_path(
        "important_people/workspace/source_data/规则主表.txt", anchor=__file__, must_exist=True
    )
    adapter_dir_value = resolve_project_path("important_people/site_adapters", anchor=__file__)
    output_dir_value = resolve_project_path("important_people/site_adapters/最后一批", anchor=__file__)
    manifest_path_value = resolve_project_path(
        "important_people/workspace/reports/最后一批待分析脚本生成清单.txt", anchor=__file__
    )
    log_path_value = resolve_project_path(
        "important_people/workspace/log/最后一批待分析脚本生成.log", anchor=__file__
    )
    main(rule_table_path_value, adapter_dir_value, output_dir_value, manifest_path_value, log_path_value)
