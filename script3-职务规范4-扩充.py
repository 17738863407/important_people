from __future__ import annotations

import importlib.util
import re
from datetime import datetime
from pathlib import Path
from types import ModuleType

from tqdm import tqdm

from crawler_core.paths import resolve_path_argument, timestamped_output_path


def load_cleaning_module(script_path: Path) -> ModuleType:
    """加载清理脚本，复用十二列读写和日志函数。"""
    if not script_path.is_file():
        raise FileNotFoundError(f"未找到清理脚本：{script_path}")
    spec = importlib.util.spec_from_file_location("duty_cleaning", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载清理脚本：{script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def clean_base_organization(value: str) -> str:
    """提取当前行机构主名称。"""
    text = re.sub(r"[（(][^（）()]*[）)]", "", re.sub(r"\s+", "", str(value or "")))
    return re.split(r"[—–－-]|[:：]", text, maxsplit=1)[0].strip()


def build_alias_pairs(base_org: str) -> list[tuple[str, str]]:
    """结合当前机构上下文，生成“完整简称主体—完整全称主体”映射。"""
    pairs: list[tuple[str, str]] = []
    # 保留少量稳定机构简称规则，避免依赖外部别称文件。
    definitions = (
        ("国有资产监督管理委员会", "国资委"),
        ("发展和改革委员会", "发改委"),
        ("卫生健康委员会", "卫健委"),
        ("住房和城乡建设局", "住建局"),
        ("工业和信息化局", "工信局"),
    )
    for full_suffix, alias in definitions:
        if not base_org.endswith(full_suffix):
            continue
        prefix = base_org[: -len(full_suffix)]
        if prefix.endswith("人民政府"):
            prefix = prefix.removesuffix("人民政府")
        short_subject = prefix + alias
        if short_subject and short_subject != base_org:
            pairs.append((short_subject, base_org))
    if base_org.endswith("管理委员会"):
        area_name = base_org.removesuffix("管理委员会")
        short_subject = area_name + "管委会"
        if short_subject != base_org:
            pairs.append((short_subject, base_org))
    return list(dict.fromkeys(pairs))


def build_short_only_alias_pairs(base_org: str) -> list[tuple[str, str]]:
    """构造只允许从原文简称扩充到全称的上下文映射。"""
    city_bureau_match = re.match(r"([\u4e00-\u9fff]{2,8}市).+局$", base_org)
    if not city_bureau_match:
        return []
    short_subject = city_bureau_match.group(1) + "局"
    return [(short_subject, base_org)] if short_subject != base_org else []


def expand_government_leader_aliases(token: str) -> tuple[list[str], list[str]]:
    """扩充省、市政府行政首长职务的地域简称、政府简称和政府全称。"""
    patterns = (
        re.compile(
            r"(?P<region>[\u4e00-\u9fff]{1,16}省)"
            r"(?:人民政府|政府)?"
            r"(?P<title>(?:常务副|代理|代|副)?省长)"
        ),
        re.compile(
            r"(?P<region>[\u4e00-\u9fff]{1,16}市)"
            r"(?:人民政府|政府)?"
            r"(?P<title>(?:常务副|代理|代|副)?市长)"
        ),
    )
    for pattern in patterns:
        match = pattern.search(token)
        if match is None:
            continue
        prefix = token[: match.start()]
        suffix = token[match.end() :]
        region = match.group("region")
        title = match.group("title")
        variants = list(
            dict.fromkeys(
                (
                    prefix + region + title + suffix,
                    prefix + region + "政府" + title + suffix,
                    prefix + region + "人民政府" + title + suffix,
                )
            )
        )
        reason = f"政府行政首长扩充：{'——'.join(variants)}"
        return variants, [reason]
    return [token], []


def expand_token_aliases(
    token: str,
    alias_pairs: list[tuple[str, str]],
    short_only_alias_pairs: list[tuple[str, str]],
) -> tuple[list[str], list[str]]:
    """保留完整简称职务，并紧随其后增加对应全称职务。"""
    for short_subject, full_subject in alias_pairs:
        if full_subject in token:
            short_variant = token.replace(full_subject, short_subject, 1)
            if short_variant != token:
                return [short_variant, token], [f"别称扩充：{short_variant}——{token}"]
    for short_subject, full_subject in alias_pairs:
        if short_subject in token:
            full_variant = token.replace(short_subject, full_subject, 1)
            if token != full_variant:
                return [token, full_variant], [f"别称扩充：{token}——{full_variant}"]
    for short_subject, full_subject in short_only_alias_pairs:
        if short_subject in token:
            full_variant = token.replace(short_subject, full_subject, 1)
            if token != full_variant:
                return [token, full_variant], [f"别称扩充：{token}——{full_variant}"]
    return [token], []


def expand_duty_token(
    token: str,
    alias_pairs: list[tuple[str, str]],
    short_only_alias_pairs: list[tuple[str, str]],
) -> tuple[list[str], list[str]]:
    """优先处理政府行政首长，再处理普通机构简称和全称。"""
    government_variants, government_reasons = expand_government_leader_aliases(token)
    if government_reasons:
        return government_variants, government_reasons
    return expand_token_aliases(token, alias_pairs, short_only_alias_pairs)


def expand_row_aliases(row: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """对已补全职务执行简称与全称的双表示扩充。"""
    output = dict(row)
    duty = row.get("职务*", "").strip()
    if not duty:
        return output, []
    base_org = clean_base_organization(row.get("机构", ""))
    alias_pairs = build_alias_pairs(base_org)
    short_only_alias_pairs = build_short_only_alias_pairs(base_org)
    expanded_tokens: list[str] = []
    reasons: list[str] = []
    for token in [part for part in duty.split("、") if part]:
        variants, token_reasons = expand_duty_token(token, alias_pairs, short_only_alias_pairs)
        expanded_tokens.extend(variants)
        reasons.extend(token_reasons)
    output["职务*"] = "、".join(dict.fromkeys(expanded_tokens))
    return output, list(dict.fromkeys(reasons))


def build_audit_row(
    line_number: int,
    source: dict[str, str],
    output: dict[str, str],
    reasons: list[str],
) -> dict[str, str]:
    """构造扩充阶段审计行。"""
    return {
        "行号": str(line_number),
        "姓名*": source.get("姓名*", ""),
        "扩充前职务*": source.get("职务*", ""),
        "扩充后职务*": output.get("职务*", ""),
        "机构": source.get("机构", ""),
        "脚本序号": source.get("脚本序号", ""),
        "审计原因": "；".join(reasons),
    }


def validate_expanded_rows(
    source_path: Path,
    output_path: Path,
    cleaning_module: ModuleType,
) -> list[str]:
    """验证扩充阶段只修改职务列，并保留扩充前全部职务。"""
    config = cleaning_module.build_runtime_config()
    source_headers, source_rows = cleaning_module.read_rows(source_path)
    output_headers, output_rows = cleaning_module.read_rows(output_path)
    errors: list[str] = []
    if source_headers != config["headers"] or output_headers != config["headers"]:
        errors.append("表头不是规定的十二列或列序错误")
    if len(source_rows) != len(output_rows):
        errors.append(f"行数不一致：输入{len(source_rows)}，输出{len(output_rows)}")
    protected_fields = [header for header in config["headers"] if header != "职务*"]
    for line_number, (source, output) in enumerate(zip(source_rows, output_rows), start=2):
        for field in protected_fields:
            if source.get(field, "") != output.get(field, ""):
                errors.append(f"第{line_number}行非目标字段被修改：{field}")
        source_tokens = [part for part in source.get("职务*", "").split("、") if part]
        output_tokens = [part for part in output.get("职务*", "").split("、") if part]
        base_org = clean_base_organization(source.get("机构", ""))
        alias_pairs = build_alias_pairs(base_org)
        short_only_alias_pairs = build_short_only_alias_pairs(base_org)
        for source_token in source_tokens:
            variants, _ = expand_duty_token(
                source_token,
                alias_pairs,
                short_only_alias_pairs,
            )
            if not all(variant in output_tokens for variant in variants):
                errors.append(f"第{line_number}行未完整保留简称与全称：{source_token}")
    return errors


def process_all_rows(
    input_path: Path,
    output_path: Path,
    audit_path: Path,
    log_path: Path,
    cleaning_module: ModuleType,
) -> None:
    """逐行扩充简称与全称；单行失败时保留补全结果。"""
    config = cleaning_module.build_runtime_config()
    headers, rows = cleaning_module.read_rows(input_path)
    if headers != config["headers"]:
        raise ValueError(f"输入表头不符合十二列契约：{headers}")
    outputs: list[dict[str, str]] = []
    audits: list[dict[str, str]] = []
    for line_number, row in enumerate(tqdm(rows, desc="职务简称全称扩充", unit="行"), start=2):
        try:
            output, reasons = expand_row_aliases(row)
        except Exception as error:
            output = dict(row)
            reasons = [f"别称扩充失败，保留补全结果：{error}"]
        outputs.append(output)
        if reasons:
            audits.append(build_audit_row(line_number, row, output, reasons))
    audit_headers = list(build_audit_row(0, {}, {}, []).keys())
    cleaning_module.write_rows(output_path, headers, outputs)
    cleaning_module.write_rows(audit_path, audit_headers, audits)
    cleaning_module.write_log(log_path, f"输入记录：{len(rows)}")
    cleaning_module.write_log(log_path, f"发生简称全称扩充或异常的记录：{len(audits)}")
    validation_errors = validate_expanded_rows(input_path, output_path, cleaning_module)
    cleaning_module.write_log(log_path, f"全量质量门禁错误：{len(validation_errors)}")
    if validation_errors:
        raise ValueError(f"扩充质量门禁未通过，共{len(validation_errors)}项：{'；'.join(validation_errors[:20])}")
    cleaning_module.write_log(log_path, f"扩充结果：{output_path}")
    cleaning_module.write_log(log_path, f"审计报告：{audit_path}")


def build_output_paths(project_dir: Path) -> tuple[Path, Path, Path]:
    """构造扩充结果、审计报告和日志路径。"""
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return (
        project_dir / "职务规范4：扩充.txt",
        timestamped_output_path(
            project_dir / "workspace" / "reports" / "职务规范4：扩充审计报告.txt",
            run_timestamp,
        ),
        timestamped_output_path(
            project_dir / "workspace" / "log" / "职务规范4：扩充日志.txt",
            run_timestamp,
        ),
    )


def main(
    input_path: str | Path,
    project_dir: str | Path,
    cleaning_script_path: str | Path,
) -> None:
    """统一入口：保留简称职务并增加对应全称职务。"""
    input_path = resolve_path_argument(input_path, anchor=__file__, must_exist=True)
    project_dir = resolve_path_argument(project_dir, anchor=__file__, must_exist=True)
    cleaning_script_path = resolve_path_argument(
        cleaning_script_path, anchor=__file__, must_exist=True
    )
    if not input_path.is_file():
        raise FileNotFoundError(f"未找到补全结果：{input_path}")
    if not project_dir.is_dir():
        raise NotADirectoryError(f"未找到项目根目录：{project_dir}")
    cleaning_module = load_cleaning_module(cleaning_script_path)
    output_path, audit_path, log_path = build_output_paths(project_dir)
    if input_path.resolve() == output_path.resolve():
        raise ValueError("输出路径不得覆盖输入文件")
    process_all_rows(input_path, output_path, audit_path, log_path, cleaning_module)
    print(f"扩充结果：{output_path}")
    print(f"审计报告：{audit_path}")
    print(f"运行日志：{log_path}")


if __name__ == "__main__":
    input_path_value = r"important_people/职务规范3：补全.txt"
    project_dir_value = r"important_people"
    cleaning_script_path_value = r"important_people/script3-职务规范2-清理.py"
    main(
        input_path=input_path_value,
        project_dir=project_dir_value,
        cleaning_script_path=cleaning_script_path_value,
    )
