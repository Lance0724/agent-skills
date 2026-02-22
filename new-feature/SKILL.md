---
name: new-feature
description: |
  Standardized workflow for implementing new features.
  - Process: Requirements -> Specification -> Planning -> Execution.
  - Constraint: Ensure all documentation and comments are in Chinese.
  - Triggers: "new feature", "add feature", "dev plan".
version: 1.1.0
author: lance
license: MIT
---

# 新功能开发工作流

此技能指导您完成开发新功能的标准化流程，确保所有需求、规范和测试策略都已记录。

**重要规则**：
1.  所有生成的文档（`requires.md`, `specification.md`, `TODO.md`）的内容**必须使用中文**编写。
2.  所有生成的代码中的**注释（comments）必须使用中文**编写。
3.  文件名和目录名使用英文 kebab-case (例如 `new-user-login`)。

## 流程概览

1.  **初始化**：确定功能名称（必须使用 kebab-case，例如 `new-user-login`），创建目录 `.ai/doc/[feature-name]/`。
2.  **需求收集**：讨论并明确需求（含验收标准），**必须使用中文**编写，然后保存到 `.ai/doc/[feature-name]/requires.md`。
3.  **方案规范**：讨论并确定技术解决方案（含测试策略），**必须使用中文**编写，然后保存到 `.ai/doc/[feature-name]/specification.md`。
4.  **执行计划**：根据规范创建详细计划，**必须使用中文**编写，然后保存到 `.ai/doc/[feature-name]/TODO.md`。
5.  **执行跟踪**：随着进展更新 `.ai/doc/[feature-name]/TODO.md`，并在执行前**必须**阅读设计文档。

## 第一步：需求收集

首先与用户讨论功能请求。提出澄清性问题以了解范围、用户故事、验收标准和约束条件。

一旦需求明确：
1.  确认功能名称并创建对应的目录（如果不存在）。
2.  参考下面的模板创建 `requires.md`。**注意：填写内容必须是中文。**

**模板参考**：`references/requirements-template.md`

## 第二步：方案规范

讨论技术方法。考虑架构、数据结构、API 变更、UI/UX 以及**测试策略**。

一旦方案达成一致：
1.  在功能目录中创建 `specification.md`。
2.  参考下面的模板。**注意：填写内容必须是中文。**

**模板参考**：`references/specification-template.md`

## 第三步：执行计划

将实施工作分解为具体任务。

1.  在功能目录中创建 `TODO.md`。
2.  列出所有任务并跟踪进度。**注意：填写内容必须是中文。**

**模板参考**：`references/todo-template.md`

## 第四步：执行与跟踪

**关键规则**：在开始编写任何代码之前，你必须先读取并理解 `specification.md` 中的设计细节和测试策略。

在实施功能时：
1.  **每次**开始一个新的任务项前，先确认 `TODO.md` 的状态。
2.  编写代码后，**必须**运行相关测试以验证是否满足验收标准。
3.  **特别注意**：生成的代码中所有注释（comments）必须使用中文编写，以便于理解和维护。
4.  更新 `TODO.md`，将任务标记为已完成，并简要备注结果（中文）。
