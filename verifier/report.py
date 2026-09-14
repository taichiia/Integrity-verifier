import csv
from datetime import datetime
import json


STATUS_LABELS = {
    "pass": "通过",
    "fail": "失败",
    "missing": "缺失",
    "extra": "多余",
    "error": "错误",
}


def write_csv_report(filepath: str, results: list[dict], target_path: str = "") -> None:
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["状态", "文件路径", "期望哈希值", "实际哈希值"])
        for r in results:
            writer.writerow([
                r["status"],
                r["path"],
                r.get("expected", ""),
                r.get("actual", ""),
            ])


def write_txt_report(filepath: str, results: list[dict], target_path: str = "") -> None:
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("文件完整性验证报告\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"目标路径: {target_path}\n")
        f.write("-" * 60 + "\n")
        for r in results:
            status = STATUS_LABELS.get(r["status"], "?")
            actual = r.get("actual", "")
            if actual:
                f.write(f"[{status}] {r['path']}  (实际: {actual})\n")
            else:
                f.write(f"[{status}] {r['path']}\n")
        passed = sum(1 for r in results if r["status"] == "pass")
        total = len(results)
        f.write("-" * 60 + "\n")
        f.write(f"汇总: {passed}/{total} 通过, {total - passed} 项异常\n")


def write_json_report(filepath: str, results: list[dict], target_path: str = "") -> None:
    counts = {status: 0 for status in STATUS_LABELS}
    for result in results:
        status = result.get("status", "")
        counts[status] = counts.get(status, 0) + 1

    report = {
        "generated_at": datetime.now().isoformat(),
        "target_path": target_path,
        "status_labels": STATUS_LABELS,
        "results": [
            {
                "status": result.get("status", ""),
                "path": result.get("path", ""),
                "expected": result.get("expected", ""),
                "actual": result.get("actual", ""),
            }
            for result in results
        ],
        "summary": {
            **counts,
            "total": len(results),
        },
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
