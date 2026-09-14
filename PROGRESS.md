# PROGRESS

## 基线

- 提交 `4142989`: 主题集中化、打包临时目录清理、验证器自排除、QSS 告警修复、测试补齐（30 通过）。

## 第 1 轮

- 上一轮遗留: 无。
- 候选功能: ① 验证结果"实际哈希值"列并导出 ② 验证器 CLI 模式 ③ 验证耗时统计。
- 选择: ①（价值 5 / 成本 2 / 风险 2，排障与篡改分析必需）。
- 已完成: 验证结果表新增"实际哈希值"列（extra/missing 为空）；报告导出迁移到 `verifier/report.py`（CSV/TXT 均含实际哈希与汇总）；状态名单一来源 `STATUS_LABELS`。
- 测试: 36 通过（新增 `test_report.py` 4 个、`test_verifier_model.py` 2 个；覆盖 pass/fail/missing/extra 四态与空报告边界）。
- 遗留项: 无。
- 下一轮计划: 验证器 CLI 模式（无 GUI 命令行验证，退出码反映结果）。

## 第 2 轮

- 上一轮遗留: 无。
- 候选功能: ① 验证器 CLI 模式 ② 验证耗时统计 ③ QSettings 主题记忆。
- 选择: ①（价值 4 / 成本 3 / 风险 2，CI/自动化集成入口）。
- 已完成: `verifier/cli.py`（`python -m verifier.cli --target <dir>`，退出码 0=通过/1=验证失败/2=无数据/3=目标无效，`--json` 机器可读报告）；`VerifyWorker` 移至 `shared/verify_worker.py` 并新增 `exclude_paths` 参数（builder 侧转发 shim，公共 API 不变）；内嵌配置加载提取至 `verifier/embedded.py`（GUI/CLI 共用，无 GUI 弹窗）；README 补充 CLI 用法。
- 测试: 46 通过（新增 `test_cli.py` 9 个含子进程端到端与 `--help` 冒烟、`test_verify_worker.py` 新增 exclude_paths 1 个；覆盖成功/篡改/缺失/多余/坏目标/无数据/JSON 全路径）。测试发现并修复 `EmbeddedConfigError.message` 缺失问题。
- 遗留项: 无。
- 下一轮计划: 验证耗时与速度统计（verifier GUI 显示用时与文件/秒）。

## 第 3 轮

- 上一轮遗留: 无。
- 候选功能: ① 验证耗时与速度统计 ② QSettings 主题/几何记忆 ③ 拖拽目录到验证器。
- 选择: ①（价值 3 / 成本 1 / 风险 1；现有速度标签是从未更新的死 UI）。
- 已完成: 验证进度中实时显示文件/秒，完成时显示"用时 X 秒 · Y 文件/秒"；提取 `format_verify_stats` 纯函数；修复 `_all_results` 在无校验数据路径下未初始化的边界问题。
- 测试: 50 通过（新增 `test_verifier_stats.py` 4 个；覆盖带文件/零文件/零耗时边界与 GUI 完成回调更新标签）。
- 遗留项: 无。
- 下一轮计划: QSettings 记住主题模式与窗口几何（builder + verifier）。

## Round 4
- ��һ������: �ޡ�
- ��ѡ����: CSV �㷨�Զ����; QSettings ��������/����; ��קĿ¼����֤��Ŀ��·����
- ѡ��: CSV �㷨�Զ���⣨��ֵ 3 / �ɱ� 1 / ���� 1����ͬʱ�޸����߲˵��ⲿУ����·����
- �����: `shared/checksum_file.py` ���� `load_checksum_entries()`��CSV ��ͷ��ʶ���㷨��SFV ʹ�û����㷨��Step 3 �ⲿ����ʹ�ü������Builder ���߲˵������л��� Step 3 �����������ⲿУ�����̣���������ع����ȷ�ϲ������ `box-shadow`��������ʷ��������� `verifier/build/` �� `.spec`��
- ����: 55 ͨ�������� CSV ͷ���㷨����ͷ��Ĭ��ֵ��SFV ���ˡ�Builder ���߲˵��� Step 3 ����·������ع顣
- ������: �û������ unknown box shadow �ж�Ϊ�ɴ�� Builder ����ʷ��־����ǰԴ�������������ȷ�ϲ��������ԡ�
- ��һ�ּƻ�: QSettings ��ס Builder/Verifier ������ģʽ�봰�ڼ��Ρ�

## Round 5
- ��һ������: �ޡ�
- ��ѡ����: QSettings ��������/����; ��קĿ¼����֤��; �Ҽ���������·����
- ѡ��: QSettings ��������/���Σ���ֵ 3 / �ɱ� 2 / ���� 1����
- �����: `shared/preferences.py` �ṩ QSettings ��д��Builder �� Verifier ������ʱ�ָ������봰�ڼ��Σ������л��������棬�ر�ʱ���漸�Σ�������������ѡ `settings` ����������Ĭ����Ϊ���䡣
- ����: 59 ͨ�������������д���Ƿ�ֵ���ˡ�Builder/Verifier �����뼸�λָ���
- ������: �ޡ�
- ��һ�ּƻ�: ��ק�ļ��е� Verifier Ŀ��·�������
