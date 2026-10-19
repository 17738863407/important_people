from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path
from pprint import pformat

try:
    from workspace.tools.project_paths import resolve_project_path, timestamped_output_path
except ModuleNotFoundError:
    from project_paths import resolve_project_path, timestamped_output_path


def write_log(log_path: Path, message: str) -> None:
    """同时向控制台和UTF-8日志输出消息。"""
    print(message)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as file:
        file.write(message + "\n")


def normalize_sequence(value: object) -> str:
    """把任务清单中的脚本序号统一为四位数字。"""
    match = re.search(r"(\d+)", str(value or ""))
    return match.group(1).zfill(4) if match else ""


def read_tsv_rows(path: Path) -> list[dict[str, str]]:
    """读取DeepSeek视觉脚本任务清单并严格校验表头。"""
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if not lines:
        raise ValueError(f"任务清单为空：{path}")
    headers = [item.strip() for item in lines[0].split("\t")]
    expected_headers = ["脚本序号", "图片选择器", "补充要求", "配置状态"]
    if headers != expected_headers:
        raise ValueError(f"任务清单表头错误：{headers}")
    rows: list[dict[str, str]] = []
    for line_number, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        cells = line.split("\t")
        if len(cells) != len(headers):
            raise ValueError(f"任务清单第{line_number}行列数错误")
        rows.append({header: cells[index].strip() for index, header in enumerate(headers)})
    return rows


def load_business_source_map(project_dir: Path) -> dict[str, object]:
    """读取权威规则主表中的启用业务记录。"""
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.business_sources import load_business_sources

    return load_business_sources()


def collect_existing_sequences(adapter_dir: Path) -> set[str]:
    """递归收集已有页面脚本序号，防止生成同序号副本。"""
    sequences: set[str] = set()
    for script_path in adapter_dir.rglob("*.py"):
        match = re.match(r"(\d{4})_", script_path.name)
        if match:
            sequences.add(match.group(1))
    return sequences


def build_page_rule(task: dict[str, str], sequence: str) -> dict[str, object]:
    """通过公共构造器生成DeepSeek直接视觉抽取规则。"""
    if task.get("配置状态", "").strip().lower() not in {"verified", "已核验", "已验证"}:
        raise ValueError("任务尚未完成真实图片结构核验")
    image_selector = task.get("图片选择器", "").strip()
    if not image_selector:
        raise ValueError("已核验任务必须填写图片选择器")
    from crawler_core.vision_llm import build_vision_page_rule

    return build_vision_page_rule(
        rule_id=sequence,
        image_selector=image_selector,
        instruction=task.get("补充要求", "").strip(),
        fetch_mode="online",
    )


def make_script_content(page_rule: dict[str, object]) -> str:
    """生成符合V3入口规范的DeepSeek视觉页面脚本。"""
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


PAGE_RULE = {rule_text}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[object]:
    """使用DeepSeek视觉模型直接识别目标图片并校验证据。"""
    from crawler_core.settings import get_settings
    from crawler_core.vision_llm import parse_vision_llm_records

    return parse_vision_llm_records(
        rule=page_rule,
        html=html,
        final_url=final_url,
        timeout_seconds=max(get_settings().browser_timeout_seconds, 180),
    )


def main() -> None:
    """运行当前DeepSeek视觉页面脚本。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{{output_path}}")


if __name__ == "__main__":
    run_timestamp_value = datetime.now().strftime("%Y%m%d_%H%M%S")
    main()
'''


def write_manifest(path: Path, rows: list[list[str]]) -> None:
    """写出制表符分隔的脚本生成报告。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            cleaned = [
                str(value or "").replace("\t", " ").replace("\r", " ").replace("\n", " ")
                for value in row
            ]
            file.write("\t".join(cleaned) + "\n")


def main(
    project_dir: Path,
    task_path: Path,
    adapter_dir: Path,
    output_dir: Path,
    manifest_path: Path,
    log_path: Path,
) -> None:
    """按显式任务清单生成DeepSeek视觉页面脚本。"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("", encoding="utf-8")
    tasks = read_tsv_rows(task_path)
    sources = load_business_source_map(project_dir)
    from crawler_core.naming import build_script_name

    existing_sequences = collect_existing_sequences(adapter_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_rows: list[list[str]] = [["脚本序号", "机构", "状态", "脚本路径", "说明"]]

    try:
        from tqdm import tqdm
    except Exception:
        tqdm = None
    iterator = tqdm(tasks, desc="生成DeepSeek视觉人物抽取脚本") if tqdm else tasks
    for task in iterator:
        sequence = normalize_sequence(task.get("脚本序号"))
        try:
            source = sources.get(sequence)
            if source is None:
                raise KeyError("规则主表中不存在该脚本序号")
            if not getattr(source, "enabled", False):
                raise ValueError("规则主表中的脚本已停用")
            if sequence in existing_sequences:
                raise FileExistsError("已有相同脚本序号，禁止重复生成")
            page_rule = build_page_rule(task, sequence)
            script_name = build_script_name(sequence, getattr(source, "organization", ""))
            script_path = output_dir / script_name
            if script_path.exists():
                raise FileExistsError("目标脚本已存在，未覆盖")
            script_path.write_text(make_script_content(page_rule), encoding="utf-8")
            existing_sequences.add(sequence)
            report_rows.append([sequence, getattr(source, "organization", ""), "已生成，可运行", str(script_path), ""])
        except Exception as error:
            report_rows.append([sequence, "", "跳过", "", str(error)])
            write_log(log_path, f"跳过：{sequence or '无序号'}，原因：{error}")

    write_manifest(manifest_path, report_rows)
    write_log(log_path, f"任务数：{len(tasks)}")
    write_log(log_path, f"生成报告：{manifest_path}")


if __name__ == "__main__":
    project_dir_value = resolve_project_path("important_people", anchor=__file__)
    task_path_value = resolve_project_path(
        "important_people/workspace/tools/configs/DeepSeek视觉人物抽取任务.txt", anchor=__file__
    )
    adapter_dir_value = resolve_project_path("important_people/site_adapters", anchor=__file__)
    output_dir_value = resolve_project_path("important_people/site_adapters/17待检测", anchor=__file__)
    manifest_path_value = timestamped_output_path(resolve_project_path(
        "important_people/workspace/reports/DeepSeek视觉人物抽取脚本生成报告.txt", anchor=__file__
    ), run_timestamp_value)
    log_path_value = timestamped_output_path(resolve_project_path(
        "important_people/workspace/log/生成DeepSeek视觉人物抽取脚本.log", anchor=__file__
    ), run_timestamp_value)
    main(
        project_dir=project_dir_value,
        task_path=task_path_value,
        adapter_dir=adapter_dir_value,
        output_dir=output_dir_value,
        manifest_path=manifest_path_value,
        log_path=log_path_value,
    )
