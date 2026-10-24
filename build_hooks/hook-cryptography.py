import glob
import os
import pathlib

from PyInstaller import compat
from PyInstaller import isolated
from PyInstaller.utils.hooks import (
    collect_submodules,
    copy_metadata,
    get_module_file_attribute,
    is_module_satisfies,
    logger,
)


datas = copy_metadata("cryptography")
hiddenimports = collect_submodules("cryptography.hazmat.backends")
hiddenimports += collect_submodules("cryptography.hazmat.bindings.openssl") + ["_cffi_backend"]

binaries = []
cryptography_dir = os.path.dirname(get_module_file_attribute("cryptography"))
for ext in compat.EXTENSION_SUFFIXES:
    ffimods = glob.glob(os.path.join(cryptography_dir, "*_cffi_*%s*" % ext))
    for ffi_mod in ffimods:
        binaries.append((ffi_mod, "cryptography"))

try:
    @isolated.decorate
    def _check_cryptography_openssl3():
        from cryptography.hazmat.backends.openssl.backend import backend
        openssl_version = backend.openssl_version_number()
        if openssl_version < 0x30000000:
            return False, None

        try:
            import cryptography.hazmat.bindings._openssl as bindings_module
        except ImportError:
            import cryptography.hazmat.bindings._rust as bindings_module

        return True, str(bindings_module.__file__)

    uses_openssl3, bindings_module = _check_cryptography_openssl3()
except Exception:
    logger.warning(
        "hook-cryptography: failed to determine whether cryptography is using OpenSSL >= 3.0.0",
        exc_info=True,
    )
    uses_openssl3, bindings_module = False, None

if uses_openssl3 and is_module_satisfies("PyInstaller >= 6.0"):
    from PyInstaller.depend import bindepend

    if compat.is_win:
        ssl_lib_name = "libssl-3-x64.dll" if compat.is_64bits else "libssl-3.dll"
    elif compat.is_darwin:
        ssl_lib_name = "libssl.3.dylib"
    else:
        ssl_lib_name = "libssl.so.3"

    linked_libs = bindepend.get_imports(bindings_module)
    openssl_lib = [
        lib_fullpath for lib_name, lib_fullpath in linked_libs
        if os.path.basename(lib_name) == ssl_lib_name
    ]
    openssl_lib = openssl_lib[0] if openssl_lib else None

    if openssl_lib:
        openssl_lib_dir = pathlib.Path(openssl_lib).parent
        ossl_modules_dir = openssl_lib_dir / "ossl-modules"

        if not ossl_modules_dir.is_dir() and openssl_lib_dir.name == "bin":
            ossl_modules_dir = openssl_lib_dir.parent / "lib" / "ossl-modules"

        if not ossl_modules_dir.is_dir() and openssl_lib_dir == pathlib.Path("/lib"):
            ossl_modules_dir = pathlib.Path("/usr/lib/ossl-modules")

        if ossl_modules_dir.is_dir():
            binaries.append((str(ossl_modules_dir), "ossl-modules"))
