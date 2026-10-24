from PySide6.QtWidgets import QMessageBox

from builder.ui.step3_pack import Step3Pack
from shared.project import ProjectData


def test_step3_key_packaging_controls_have_accessible_names(qapp):
    step = Step3Pack(ProjectData())

    assert step._title_edit.accessibleName() == "验证器窗口标题"
    assert step._icon_edit.accessibleName() == "验证器图标文件路径"
    assert step._ver_edit.accessibleName() == "验证器版本号"
    assert step._company_edit.accessibleName() == "公司名称"
    assert step._copyright_edit.accessibleName() == "版权信息"
    assert step._pack_btn.accessibleName() == "打包生成验证器"
    step.deleteLater()


def test_missing_private_key_blocks_packing_with_warning(qapp, monkeypatch):
    project = ProjectData(verifier_enable_signature_verify=True)
    main_project = ProjectData(private_key_path=r"Q:/missing/private.pem")
    step = Step3Pack(project)
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning",
        lambda *args, **kwargs: warnings.append(args[2]),
    )

    assert step._prepare_signing_key(main_project) is None
    assert len(warnings) == 1
    assert "找不到私钥文件" in warnings[0]
    step.deleteLater()


def test_invalid_private_key_blocks_packing_with_error(qapp, monkeypatch, tmp_path):
    project = ProjectData(verifier_enable_signature_verify=True)
    key_path = tmp_path / "private.pem"
    key_path.write_text("not a private key", encoding="utf-8")
    main_project = ProjectData(
        private_key_path=str(key_path),
        signature_algorithm="RSA",
    )
    step = Step3Pack(project)
    errors = []
    monkeypatch.setattr(
        QMessageBox, "critical",
        lambda *args, **kwargs: errors.append(args[2]),
    )

    assert step._prepare_signing_key(main_project) is None
    assert len(errors) == 1
    assert "无法读取签名私钥" in errors[0]
    step.deleteLater()
