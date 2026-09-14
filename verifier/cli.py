import argparse
import json
import os
import sys

EXIT_OK = 0
EXIT_VERIFY_FAILED = 1
EXIT_NO_DATA = 2
EXIT_BAD_TARGET = 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="File Integrity Verifier (CLI)")
    parser.add_argument("--target", required=True, help="待验证的目标目录")
    parser.add_argument("--algorithm", default=None,
                        help="哈希算法（默认使用内嵌配置中的算法）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出完整报告")
    args = parser.parse_args(argv)

    from verifier.embedded import (
        EmbeddedConfigError, load_embedded_config, manifest_mismatch_message,
    )
    from verifier.report import STATUS_LABELS

    try:
        config = load_embedded_config()
    except EmbeddedConfigError as e:
        print(f"{e.title}: {e.message}", file=sys.stderr)
        return EXIT_NO_DATA

    warning = manifest_mismatch_message(config)
    if warning:
        print(f"警告: {warning}", file=sys.stderr)

    entries = config.get("checksum_entries", [])
    if not entries:
        print("错误: 验证器不包含校验清单。", file=sys.stderr)
        return EXIT_NO_DATA

    target = args.target
    if not os.path.isdir(target):
        print(f"错误: 目标目录不存在: {target}", file=sys.stderr)
        return EXIT_BAD_TARGET

    algorithm = args.algorithm or config.get("algorithm", "sha256")

    exclude = []
    if getattr(sys, "frozen", False):
        exclude.append(sys.executable)

    from shared.verify_worker import VerifyWorker
    reports: list[dict] = []
    worker = VerifyWorker(entries, target, algorithm, exclude_paths=exclude)
    worker.finished.connect(reports.append)
    worker.run()
    if not reports:
        print("错误: 验证过程未返回结果。", file=sys.stderr)
        return EXIT_NO_DATA
    report = reports[0]

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for d in report.get("details", []):
            label = STATUS_LABELS.get(d["status"], d["status"])
            print(f"[{label}] {d['path']}")
        print(
            f"汇总: 通过 {report['passed']}/{report['total']} "
            f"失败 {report['failed']} 缺失 {report['missing']} "
            f"多余 {report.get('extra_count', 0)}"
        )

    if report["failed"] > 0 or report["missing"] > 0:
        return EXIT_VERIFY_FAILED
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
