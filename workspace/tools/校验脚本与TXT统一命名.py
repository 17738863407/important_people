from __future__ import annotations

import ast
import json
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    from workspace.tools.project_paths import resolve_project_path, timestamped_output_path
except ModuleNotFoundError:
    from project_paths import resolve_project_path, timestamped_output_path


def write_log(log_path: Path, message: str) -> None:
    """同时向控制台和UTF-8日志写入消息。"""
    print(message)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as file:
        file.write(message + "\n")


def safe_cell(value: object) -> str:
    """清理TXT报告中的制表符和换行。"""
    return str(value or "").replace("\t", " ").replace("\r", " ").replace("\n", " ")


def write_report(report_path: Path, rows: list[dict[str, str]]) -> None:
    """以UTF-8制表符TXT写出校验问题。"""
    headers = ["类别", "脚本序号", "路径", "问题"]
    lines = ["\t".join(headers)]
    for row in rows:
        lines.append("\t".join(safe_cell(row.get(header, "")) for header in headers))
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_tsv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """不用csv模块读取UTF-8制表符TXT。"""
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if not lines:
        return [], []
    headers = lines[0].split("\t")
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        if not line.strip():
            continue
        cells = line.split("\t")
        rows.append(
            {
                header: cells[index] if index < len(cells) else ""
                for index, header in enumerate(headers)
            }
        )
    return headers, rows


def validate_scripts(
    script_root: Path,
    business_sources: dict[str, object],
    build_script_name: object,
) -> tuple[int, list[dict[str, str]]]:
    """校验全部页面脚本名称、序号唯一性和Python语法。"""
    problems: list[dict[str, str]] = []
    seen_sequences: dict[str, Path] = {}
    scripts = [
        path
        for path in script_root.rglob("*.py")
        if path.is_file() and "__pycache__" not in path.parts
    ]
    try:
        from tqdm import tqdm
    except Exception:
        tqdm = None
    iterator = tqdm(sorted(scripts), desc="校验页面脚本") if tqdm else sorted(scripts)
    for script_path in iterator:
        match = re.match(r"^(\d{4})_", script_path.name)
        sequence = match.group(1) if match else ""
        business_source = business_sources.get(sequence)
        if business_source is None:
            problems.append({"类别": "脚本", "脚本序号": sequence, "路径": str(script_path), "问题": "规则主表无对应记录"})
            continue
        expected_name = build_script_name(sequence, getattr(business_source, "organization", ""))
        if script_path.name != expected_name:
            problems.append({"类别": "脚本", "脚本序号": sequence, "路径": str(script_path), "问题": f"名称应为：{expected_name}"})
        old_path = seen_sequences.get(sequence)
        if old_path is not None:
            problems.append({"类别": "脚本", "脚本序号": sequence, "路径": str(script_path), "问题": f"序号与另一脚本重复：{old_path}"})
        else:
            seen_sequences[sequence] = script_path
        try:
            source = script_path.read_text(encoding="utf-8-sig")
            ast.parse(source, filename=str(script_path))
        except Exception as error:
            problems.append({"类别": "脚本语法", "脚本序号": sequence, "路径": str(script_path), "问题": str(error)})
    return len(scripts), problems


def validate_txt_files(
    txt_roots: list[Path],
    business_sources: dict[str, object],
    build_output_name: object,
) -> tuple[int, list[dict[str, str]]]:
    """校验三处抽取结果TXT名称。"""
    problems: list[dict[str, str]] = []
    count = 0
    for root in txt_roots:
        for txt_path in sorted(path for path in root.rglob("*.txt") if path.is_file()):
            count += 1
            match = re.match(r"^(\d{4})_", txt_path.name)
            sequence = match.group(1) if match else ""
            business_source = business_sources.get(sequence)
            if business_source is None:
                problems.append({"类别": "TXT", "脚本序号": sequence, "路径": str(txt_path), "问题": "规则主表无对应记录"})
                continue
            expected_name = build_output_name(sequence, getattr(business_source, "organization", ""))
            if txt_path.name != expected_name:
                problems.append({"类别": "TXT", "脚本序号": sequence, "路径": str(txt_path), "问题": f"名称应为：{expected_name}"})
    return count, problems


def validate_memory(
    memory_path: Path,
    business_sources: dict[str, object],
    build_script_name: object,
) -> tuple[int, list[dict[str, str]]]:
    """校验采集方式记忆仅以脚本序号唯一记录。"""
    headers, rows = read_tsv_rows(memory_path)
    problems: list[dict[str, str]] = []
    if not headers or headers[0] != "脚本序号":
        problems.append({"类别": "采集记忆", "脚本序号": "", "路径": str(memory_path), "问题": "首列不是脚本序号"})
    seen: set[str] = set()
    for row in rows:
        sequence = str(row.get("脚本序号") or "")
        business_source = business_sources.get(sequence)
        if business_source is None:
            problems.append({"类别": "采集记忆", "脚本序号": sequence, "路径": str(memory_path), "问题": "规则主表无对应记录"})
            continue
        if sequence in seen:
            problems.append({"类别": "采集记忆", "脚本序号": sequence, "路径": str(memory_path), "问题": "脚本序号重复"})
        seen.add(sequence)
        expected_name = build_script_name(sequence, getattr(business_source, "organization", ""))
        if str(row.get("脚本名") or "") != expected_name:
            problems.append({"类别": "采集记忆", "脚本序号": sequence, "路径": str(memory_path), "问题": f"脚本名应为：{expected_name}"})
    return len(rows), problems


def validate_extension(
    extension_data_path: Path,
    business_sources: dict[str, object],
    build_output_name: object,
) -> tuple[int, list[dict[str, str]]]:
    """校验Chrome扩展中的TXT名和实际脚本路径。"""
    data = json.loads(extension_data_path.read_text(encoding="utf-8"))
    pages = data.get("pages", []) if isinstance(data, dict) else []
    problems: list[dict[str, str]] = []
    for page in pages:
        source_file = str(page.get("sourceFile") or "") if isinstance(page, dict) else ""
        match = re.match(r"^(\d{4})_", source_file)
        sequence = match.group(1) if match else ""
        business_source = business_sources.get(sequence)
        if business_source is None:
            problems.append({"类别": "Chrome扩展", "脚本序号": sequence, "路径": str(extension_data_path), "问题": f"无法映射页面：{source_file}"})
            continue
        expected_name = build_output_name(sequence, getattr(business_source, "organization", ""))
        if source_file != expected_name:
            problems.append({"类别": "Chrome扩展", "脚本序号": sequence, "路径": str(extension_data_path), "问题": f"源文件名应为：{expected_name}"})
        script_path = Path(str(page.get("crawlerScriptPath") or ""))
        if not script_path.is_file():
            problems.append({"类别": "Chrome扩展", "脚本序号": sequence, "路径": str(script_path), "问题": "脚本路径不存在"})
    return len(pages), problems


def main(
    project_dir: Path,
    script_root: Path,
    txt_roots: list[Path],
    memory_path: Path,
    extension_data_path: Path,
    report_path: Path,
    log_path: Path,
) -> None:
    """执行统一命名的全量只读验收。"""
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.business_sources import load_business_sources
    from crawler_core.naming import build_output_name, build_script_name

    if log_path.exists():
        log_path.unlink()
    business_sources = load_business_sources()
    script_count, script_problems = validate_scripts(script_root, business_sources, build_script_name)
    txt_count, txt_problems = validate_txt_files(txt_roots, business_sources, build_output_name)
    memory_count, memory_problems = validate_memory(memory_path, business_sources, build_script_name)
    extension_count, extension_problems = validate_extension(extension_data_path, business_sources, build_output_name)
    problems = script_problems + txt_problems + memory_problems + extension_problems
    write_report(report_path, problems)
    write_log(log_path, f"脚本数：{script_count}")
    write_log(log_path, f"TXT数：{txt_count}")
    write_log(log_path, f"采集记忆数：{memory_count}")
    write_log(log_path, f"Chrome扩展页面数：{extension_count}")
    write_log(log_path, f"问题数：{len(problems)}")
    write_log(log_path, f"校验报告：{report_path}")
    if problems:
        raise RuntimeError(f"统一命名验收发现 {len(problems)} 个问题")


if __name__ == "__main__":
    run_timestamp_value = datetime.now().strftime("%Y%m%d_%H%M%S")
    project_dir_value = resolve_project_path("important_people", anchor=__file__)
    script_root_value = project_dir_value / "site_adapters"
    txt_roots_value = [
        project_dir_value / "成功脚本的结果2026.07.29 星期三 0935",
        project_dir_value / "成功脚本的结果-国资委央企-2026.08.04 星期二 1824",
        project_dir_value / "outputs",
    ]
    memory_path_value = project_dir_value / "workspace" / "module" / "采集方式成功记录.txt"
    extension_data_path_value = project_dir_value / "chrome_extension" / "重要人物抽取结果对照" / "data" / "extraction-results.json"
    report_path_value = timestamped_output_path(
        project_dir_value / "workspace" / "reports" / "脚本与TXT统一命名全量验收.txt",
        run_timestamp_value,
    )
    log_path_value = timestamped_output_path(
        project_dir_value / "workspace" / "log" / "脚本与TXT统一命名全量验收.log",
        run_timestamp_value,
    )
    main(
        project_dir=project_dir_value,
        script_root=script_root_value,
        txt_roots=txt_roots_value,
        memory_path=memory_path_value,
        extension_data_path=extension_data_path_value,
        report_path=report_path_value,
        log_path=log_path_value,
    )
