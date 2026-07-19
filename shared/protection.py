import hashlib
import os
import sys
import struct
from ctypes import (
    windll, wintypes, byref, c_ulong, c_char_p, c_bool, sizeof,
    POINTER, Structure, GetLastError,
)
from ctypes.wintypes import DWORD, BOOL, HANDLE, LPCWSTR
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class EnvironmentCheck:
    name: str
    weight: int
    result: bool = False
    detail: str = ""


@dataclass
class EnvironmentAssessment:
    level: str
    score: int
    checks: list[EnvironmentCheck] = field(default_factory=list)


def verify_self_hash(embedded_hash_hex: str, salt: str = "") -> bool:
    try:
        exe_path = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
        if not os.path.isfile(exe_path):
            return False
        with open(exe_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        salted = hashlib.sha256((salt + file_hash).encode()).hexdigest()
        return salted == embedded_hash_hex
    except Exception:
        return False


def verify_embedded_signature(data: bytes, public_key_pem: bytes, algorithm: str = "RSA") -> bool:
    from shared.crypto import verify_signed_payload
    return verify_signed_payload(data, public_key_pem) is not None


PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
FLG_HEAP_ENABLE_TAIL_CHECK = 0x10
FLG_HEAP_ENABLE_FREE_CHECK = 0x20
FLG_HEAP_VALIDATE_PARAMETERS = 0x40

class PROCESS_BASIC_INFORMATION(Structure):
    _fields_ = [
        ("ExitStatus", c_ulong),
        ("PebBaseAddress", c_ulong),
        ("AffinityMask", c_ulong),
        ("BasePriority", c_ulong),
        ("UniqueProcessId", c_ulong),
        ("InheritedFromUniqueProcessId", c_ulong),
    ]


def run_debugger_checks() -> list[EnvironmentCheck]:
    checks = []

    checks.append(_safe_check(
        "IsDebuggerPresent",
        1,
        lambda: bool(windll.kernel32.IsDebuggerPresent()),
    ))

    checks.append(_safe_check(
        "CheckRemoteDebuggerPresent",
        1,
        lambda: _check_remote_debugger(),
    ))

    checks.append(_safe_check(
        "NtGlobalFlag",
        2,
        lambda: _check_nt_global_flag(),
    ))

    checks.append(_safe_check(
        "PEB.BeingDebugged",
        1,
        lambda: _check_peb_debugged(),
    ))

    return checks


def run_vm_checks() -> list[EnvironmentCheck]:
    checks = []

    checks.append(_safe_check(
        "VM MAC Address",
        1,
        lambda: _check_vm_mac(),
    ))

    checks.append(_safe_check(
        "VM Registry Keys",
        1,
        lambda: _check_vm_registry(),
    ))

    checks.append(_safe_check(
        "VM Processes",
        1,
        lambda: _check_vm_processes(),
    ))

    checks.append(_safe_check(
        "Low Hardware Specs",
        1,
        lambda: _check_low_specs(),
    ))

    checks.append(_safe_check(
        "VM Disk Model (WMI)",
        2,
        lambda: _check_disk_model(),
    ))

    return checks


def run_timing_check() -> list[EnvironmentCheck]:
    checks = []
    checks.append(_safe_check(
        "Timing Anomaly",
        1,
        lambda: _check_timing_anomaly(),
    ))
    return checks


def assess_environment(
    debugger_checks: list[EnvironmentCheck],
    vm_checks: list[EnvironmentCheck],
    timing_checks: list[EnvironmentCheck],
) -> EnvironmentAssessment:
    all_checks = debugger_checks + vm_checks + timing_checks
    score = sum(c.weight for c in all_checks if c.result)
    suspicious = [c for c in all_checks if c.result]

    if score <= 2:
        level = "clean"
    elif score <= 4:
        level = "suspicious"
    else:
        level = "high_confidence"

    return EnvironmentAssessment(level=level, score=score, checks=suspicious)


def run_full_assessment() -> EnvironmentAssessment:
    return assess_environment(
        run_debugger_checks(),
        run_vm_checks(),
        run_timing_check(),
    )


def _safe_check(name: str, weight: int, fn: Callable[[], bool]) -> EnvironmentCheck:
    try:
        result = fn()
        detail = "Detected" if result else "Clean"
    except Exception as e:
        result = False
        detail = f"Check failed: {e}"
    return EnvironmentCheck(name=name, weight=weight, result=result, detail=detail)


def _check_remote_debugger() -> bool:
    kernel32 = windll.kernel32
    h_process = kernel32.GetCurrentProcess()
    pb_debugger_present = c_bool(False)
    if hasattr(kernel32, 'CheckRemoteDebuggerPresent'):
        kernel32.CheckRemoteDebuggerPresent(h_process, byref(pb_debugger_present))
    return pb_debugger_present.value


def _check_nt_global_flag() -> bool:
    try:
        ntdll = windll.ntdll
        kernel32 = windll.kernel32
        process_handle = kernel32.GetCurrentProcess()

        pbi = PROCESS_BASIC_INFORMATION()
        ret = ntdll.NtQueryInformationProcess(
            process_handle,
            0,
            byref(pbi),
            sizeof(pbi),
            None,
        )
        if ret != 0:
            return False

        peb = pbi.PebBaseAddress
        if not peb:
            return False

        import platform
        offset = 0xBC if platform.architecture()[0] == '32bit' else 0x68

        ngl_buffer = c_ulong(0)
        bytes_read = c_ulong(0)
        kernel32.ReadProcessMemory(
            process_handle,
            peb + offset,
            byref(ngl_buffer),
            4,
            byref(bytes_read),
        )
        ngl = ngl_buffer.value
        return bool(ngl & (FLG_HEAP_ENABLE_TAIL_CHECK |
                           FLG_HEAP_ENABLE_FREE_CHECK |
                           FLG_HEAP_VALIDATE_PARAMETERS))
    except Exception:
        return False


def _check_peb_debugged() -> bool:
    try:
        ntdll = windll.ntdll
        kernel32 = windll.kernel32
        process_handle = kernel32.GetCurrentProcess()

        pbi = PROCESS_BASIC_INFORMATION()
        ret = ntdll.NtQueryInformationProcess(
            process_handle, 0, byref(pbi), sizeof(pbi), None,
        )
        if ret != 0:
            return False

        peb_addr = pbi.PebBaseAddress
        if not peb_addr:
            return False

        being_debugged = c_ulong(0)
        bytes_read = c_ulong(0)
        kernel32.ReadProcessMemory(
            process_handle,
            peb_addr + 0x2,
            byref(being_debugged),
            1,
            byref(bytes_read),
        )
        return bool(being_debugged.value)
    except Exception:
        return False


def _check_vm_mac() -> bool:
    try:
        import uuid
        mac = uuid.getnode()
        mac_bytes = struct.pack('!Q', mac)[2:]
        mac_str = ':'.join(f'{b:02X}' for b in mac_bytes)

        vm_prefixes = [
            "00:05:69", "00:0C:29", "00:1C:14", "00:50:56",
            "08:00:27", "00:15:5D", "00:03:FF",
        ]
        for prefix in vm_prefixes:
            if mac_str.upper().startswith(prefix.upper()):
                return True
        return False
    except Exception:
        return False


def _check_vm_registry() -> bool:
    import winreg
    vm_keys = [
        (winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\VMware, Inc.\\VMware Tools"),
        (winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\Oracle\\VirtualBox Guest Additions"),
        (winreg.HKEY_LOCAL_MACHINE, "HARDWARE\\ACPI\\DSDT\\VBOX__"),
        (winreg.HKEY_LOCAL_MACHINE, "SYSTEM\\ControlSet001\\Services\\VBoxSF"),
    ]
    for hkey, subkey in vm_keys:
        try:
            winreg.OpenKey(hkey, subkey)
            return True
        except OSError:
            continue
    return False


def _check_vm_processes() -> bool:
    import subprocess
    vm_procs = [
        "vmtoolsd.exe", "vmwaretray.exe", "VBoxService.exe",
        "VBoxTray.exe", "vmsrvc.exe", "xenservice.exe",
        "qemu-ga.exe", "prl_tools.exe",
    ]
    try:
        output = subprocess.check_output(
            "tasklist /FO CSV /NH", shell=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        ).decode("utf-8", errors="replace").lower()
        for proc in vm_procs:
            if proc.lower() in output:
                return True
        return False
    except Exception:
        return False


def _check_low_specs() -> bool:
    try:
        import ctypes.wintypes
        mem_status = ctypes.wintypes.MEMORYSTATUSEX()
        mem_status.dwLength = ctypes.sizeof(mem_status)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem_status))
        total_ram_gb = mem_status.ullTotalPhys / (1024 ** 3)
        cpu_count = os.cpu_count() or 1
        return total_ram_gb < 2.0 or cpu_count < 2
    except Exception:
        return False


def _check_disk_model() -> bool:
    try:
        import subprocess
        output = subprocess.check_output(
            'wmic diskdrive get model /format:csv 2>nul',
            shell=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        ).decode("utf-8", errors="replace").lower()
        vm_indicators = ["virtual", "vmware", "vbox", "qemu", "xen", "hyper-v"]
        for indicator in vm_indicators:
            if indicator in output:
                return True
        return False
    except Exception:
        return False


def _check_timing_anomaly() -> bool:
    try:
        import time
        start = time.perf_counter_ns()
        for _ in range(1000):
            _ = 2 * 2
        end = time.perf_counter_ns()
        delta_ns = end - start
        return delta_ns > 100_000
    except Exception:
        return False

