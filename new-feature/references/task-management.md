# JSON 状态管理

## 目录

- [调用约定](#调用约定)
- [最短完整流程](#最短完整流程)
- [任务与阶段操作](#任务与阶段操作)
- [数据契约](#数据契约)
- [校验与边界](#校验与边界)
- [已有工作与并发](#已有工作与并发)

## 调用约定

状态只能由技能内 `scripts/tasks.py` 修改。需要 Python 3.10+，无第三方依赖。不复制脚本，不另写 Python 片段修改 JSON。

以下例子中的两个变量分别是实际加载的技能脚本路径和目标功能目录，需按实际环境填写：

```bash
TASKS=/实际技能路径/new-feature/scripts/tasks.py
FEATURE=.ai/doc/input-validation
python3 "$TASKS" --help
python3 "$TASKS" add --help
```

每个命令成功返回退出码 0 和 JSON；`show` 输出完整状态，其余命令只输出阶段、模式、版本、任务数及相关任务编号和状态，避免每次更新重复传输完整计划。输入或状态错误返回 1，命令参数错误返回 2，原因写入标准错误。除 `init` 创建目录外，所有命令要求目录与状态已存在。拒绝的更新不会改变 `tasks.json`，不会把部分修改保存进去。

## 最短完整流程

### 需求与规范

```bash
python3 "$TASKS" init "$FEATURE" --mode lightweight --reason "单模块，无持久化或公共接口变化"
```

然后按需求模板写 `requirements.md`。审查需求门槛并登记**全部**验收编号：

```bash
python3 "$TASKS" advance "$FEATURE" --acceptance AC-001 --reason "范围与验收已明确，无阻塞问题"
```

按规范模板写 `specification.md`。审查规范门槛并登记**全部**设计编号：

```bash
python3 "$TASKS" advance "$FEATURE" --design DES-001 --reason "设计覆盖全部验收，验证路径可执行"
```

此时阶段是 `planning`。脚本不解析自然语言判断门槛是否满足；操作者负责审查并确保登记集合与文档完全一致。

### 添加计划并开始

```bash
python3 "$TASKS" add "$FEATURE" TASK-001 \
  --title "增加输入校验" \
  --design DES-001 --acceptance AC-001 \
  --scope src/input.py \
  --done-when "非法输入被拒绝，合法输入保持既有行为" \
  --verify "运行输入校验命令，分别检查合法与非法输入"
python3 "$TASKS" advance "$FEATURE" --reason "任务覆盖设计和验收，依赖及验证方法明确"
python3 "$TASKS" start "$FEATURE" TASK-001
```

`--design`、`--acceptance`、`--depends`、`--scope` 均接受空格分隔的多个值；依赖只能引用先添加的任务。没有依赖时省略 `--depends`。

### 实际验证后完成

先修改代码并实际运行验证；然后将真实命令或场景以及真实观察结果填入参数。以下仅说明字段形状，不代表已经运行了验证：

```bash
python3 "$TASKS" verify "$FEATURE" TASK-001 \
  --result passed \
  --check "实际运行的命令或操作步骤" \
  --observed "实际观察结果，含合法输入与非法输入行为"
python3 "$TASKS" complete "$FEATURE" TASK-001
python3 "$TASKS" validate "$FEATURE"
python3 "$TASKS" advance "$FEATURE" --reason "全部验收已实际验证，文档与实现一致"
python3 "$TASKS" show "$FEATURE"
```

验证失败用 `--result failed`，不能执行 `complete`。`--check` 只记录文本，**不会执行其中的命令**。可选 `--evidence logs/check.txt specification.md#验证策略` 附加引用；这些引用只是定位信息，脚本不会证明文件内容或锚点真实有效。

## 任务与阶段操作

| 命令 | 前提与效果 |
|---|---|
| `show DIR` | 读取并校验，输出完整 JSON；不写入 |
| `validate DIR` | 检查结构、关联、依赖环、状态不变量；不写入，不运行产品测试 |
| `add DIR ID ...` | 仅计划或执行阶段；创建 `pending` 任务；拒绝重复编号 |
| `update DIR ID ...` | 仅 `pending`；可更新标题、关联、依赖、范围、完成条件、验证计划；与 add 同名参数，不提供的字段保持不变 |
| `start DIR ID` | 仅执行阶段且流程未阻塞；`pending → in_progress`，全部依赖必须为 `completed` |
| `block DIR ID --reason ...` | `pending/in_progress → blocked`；记录原因与解除条件，清除可能过期的验证 |
| `unblock DIR ID` | `blocked → pending`；不自动开始任务 |
| `verify DIR ID ...` | 仅 `in_progress`；记录最新验证结果、命令/场景、观察和可选引用 |
| `complete DIR ID` | `in_progress → completed`；最新验证必须为 `passed` |
| `skip DIR ID --reason ...` | `pending/blocked → skipped`；必须说明不适用原因；不能替代完成依赖 |
| `reopen DIR ID --reason ...` | 重开非待处理任务及其全部下游任务；重置为 `pending` 并清除验证；已结束流程退回 `execution` |
| `hold DIR --reason ...` | 记录流程阻塞及解除条件；禁止开始新任务和推进阶段 |
| `resume DIR` | 解除流程阻塞；仅在实际问题已解决时调用；不会解除单个任务的阻塞 |
| `advance DIR --reason ...` | 只能推进下一阶段，要求无流程阻塞；首两次分别登记 AC 和 DES 编号 |
| `mode DIR --mode standard --reason ...` | 改模式并记录理由；只在需求、规范、计划阶段允许降为 lightweight |
| `replan DIR --reason ...` | 仅计划阶段及以后；退回 planning，保留任务定义，重置全部状态和验证；可传 --acceptance、--design 更新完整登记集合 |

清空依赖使用 `update DIR ID --depends`。移除依赖意味着改变计划，必须先确认相关任务真的独立，不能为了绕过未完成前置工作而删除依赖。

`replan` 的理由应概括重新审查需求和规范的结果。新增编号时传入包含旧编号的完整集合；移除旧编号前先更新所有引用它的待处理任务，再缩减登记集合，否则校验拒绝写入。不能把补全模板当作允许扩大需求的授权。

## 数据契约

`schema_version: 1` 固定；不支持的版本拒绝加载。以下字段由脚本维护：

| 字段 | 含义 |
|---|---|
| `workflow` | 固定 `new-feature` |
| `mode`、`mode_history` | 当前模式与每次选择的中文理由 |
| `phase` | `requirements → specification → planning → execution → completed` |
| `revision` | 初始化为 0；每次成功写入递增；失败与只读命令不递增 |
| `acceptance_ids`、`design_ids` | 全部验收和设计编号，用于覆盖校验 |
| `gates` | 已完成阶段的审查依据；阶段状态不在 Markdown 中重复维护 |
| `blocker` | 流程阻塞原因和解除条件；没有阻塞时为 null |
| `tasks` | 有序任务列表 |

每个任务包含：

- `id`：唯一 `TASK-001` 形式的编号；AC、DES、TASK 的数字部分至少三位。
- `title`、`completion_criteria`、`verification_plan`：非空中文说明。
- `design_refs`、`acceptance_refs`：非空且已登记的唯一编号列表；REQ 通过规范中的 DES/AC 关联追踪。
- `depends_on`：唯一任务编号列表，允许为空；不得存在未知编号、自依赖或循环。
- `scope`：非空修改范围列表，由主 Agent 据此协调代码写入所有权。
- `status`：`pending`、`in_progress`、`blocked`、`completed`、`skipped`。
- `reason`：阻塞、跳过或重开的原因；无原因时为 null。
- `verification`：`result` 为 `not_run/passed/failed`，以及 `command`、`observed`、`evidence_refs`。

任务 `completed` 与验证 `passed` 不混用。`not_run` 不得附带成功输出；完成任务必须有实际验证记录。重开会清除被影响任务的旧结果，防止修改前的证据被继续用于宣称完成。

## 校验与边界

- 计划进入执行前，全部 AC 和 DES 都必须被任务覆盖。
- 执行结束前，任务必须全部结束，且全部 AC 和 DES 被验证通过的完成任务覆盖；只有 skipped 覆盖的标准会阻止完成。
- 缺失 JSON、格式错误、未知字段、重复任务、非法状态、无效引用、依赖环和缺少验证均报告错误，不静默修复或重置。
- JSON 以 UTF-8 保存，保留中文。脚本不检测自然语言是否全为中文，不读取源码，也不判断需求、证据或模式选择是否正确。
- 不额外写状态数据库、进度 Markdown 或持久事件日志。详细证据可放在已有文档或日志，但其执行状态只在 JSON 中。

## 已有工作与并发

- 续接先 `show`；`init` 拒绝覆盖已有状态。
- 旧 Markdown 任务不会被脚本猜测解析。迁移已有功能时，用 `add` 录入任务定义，再按可确认的证据执行状态命令；缺失证据的任务保持未完成。核对后移除旧进度载体，只保留需求、设计和证据说明。本次技能升级不改写其他技能或历史项目记录。
- 所有写命令使用排他 `.tasks.lock`，并在同目录创建临时文件后原子替换 `tasks.json`。锁和临时文件不是第二状态源，正常退出即清理。
- 两个写入者冲突时命令失败，不自动重试。确认原进程已退出后，才允许移除崩溃遗留的锁。
- 所有写命令（除 init）可加 `--expect-revision N`，在锁内拒绝过期更新。主 Agent 读取后需要防止状态已变化时使用；脚本不会自动合并冲突。
- 功能目录和状态文件不允许符号链接。传入目录本身就是授权写入根，仅写其中的状态文件；不要把不可信外部文本直接用作目录参数。
