# MCP Prompts、Tools 与 Resources 的关系与配合使用

## 协议层面的区别（MCP 规范）

| 能力 | 谁控制 | 作用 |
|------|--------|------|
| **Tools** | **模型控制** | LLM 根据上下文和用户请求**自动决定**何时调用；执行具体操作（查库、调 API、计算等）。 |
| **Prompts** | **用户控制** | 客户端把预定义模板展示给用户，**用户显式选择**用哪个；生成一段可带参数的「指令/消息」插入对话。 |
| **Resources** | **应用/用户驱动** | 服务端暴露**可被读取的上下文数据**（文件、数据库、应用信息等），由 URI 唯一标识；客户端通过 `resources/list` 发现、`resources/read` 按 URI 读取内容，供模型或界面使用。 |

三者是**三套独立能力**，服务端不需要把 Prompt、Tool、Resource 两两绑定。

### Resources 补充说明

- **是什么**：Resources 是 MCP 里「可被列出和按 URI 读取」的静态或动态数据，用于给模型或用户提供上下文，例如：
  - 文件（`file:///project/README.md`）
  - 数据库表结构、查询结果
  - 应用内实体（用户信息、会话摘要等）
- **怎么用**：客户端先 `resources/list` 发现资源列表（含 name、uri、mimeType、description 等），再按需 `resources/read` 传入 URI 获取内容（文本或二进制）。可选能力包括：
  - **Resource Templates**：带参数的 URI 模板（如 `file:///{path}`），由服务端根据参数解析出实际 URI；
  - **订阅**：客户端订阅某 URI，资源变更时服务端推送通知；
  - **列表变更通知**：资源列表变化时服务端通知客户端。
- **和 Prompts/Tools 的关系**：Resources 提供「可读的上下文」，Prompts 提供「可插入的指令模板」，Tools 提供「可执行的动作」。例如：Prompt 模板里可以引用「从 Resource 读到的内容」；模型在决定是否调用 Tool 时，也可以结合已读入的 Resource 内容。协议层面三者独立，结合方式由客户端/产品设计决定。

## 在本项目中的实现

- **动态 Tools**（`mcp_dynamic_tools`）：如 `http_call` 类型，注册到 FastMCP 后，客户端/LLM 可**直接调用**，得到执行结果（例如调用外部 API 做总结、翻译）。
- **动态 Prompts**（`mcp_dynamic_prompts`）：如 `summarize`、`translate`，根据模板和参数**生成一段用户消息**（例如「请总结以下内容：\n\n{{content}}」），由客户端插入对话。
- **Resources**：当前系统 MCP（如 llm-server）**未暴露 Resources**（未实现 `resources/list`、`resources/read` 或动态 Resource 配置）。若后续需要（例如暴露会话摘要、项目文件列表等），可在 FastMCP 上注册资源提供方，或增加「动态 Resources」表与 API，与 Tools/Prompts 并列管理。

## 「结合使用」指的是什么？

- **不是**：在服务端把 Prompt 和 Tool 绑死（例如「summarize 这个 Prompt 必须调用 summarize 这个 Tool」）。MCP 里没有这种强制绑定。
- **是**：在**使用流程**上的配合：
  1. 用户在 Cursor 里选了一个 Prompt（如「总结」），填入参数；
  2. 客户端向 MCP 请求该 Prompt，拿到渲染后的**用户消息**；
  3. 客户端把这段消息**插入对话**；
  4. 随后 **LLM 可能自动选择调用某个 Tool**（例如我们配置的 `http_call` 总结接口）来执行，或者直接用模型能力生成总结。

所以：**Prompt 负责「生成要做什么的指令」**，**Tool 负责「真正执行」**。是否调用 Tool、调用哪个 Tool，由客户端/模型在对话中决定，而不是由服务端把 Prompt 和 Tool 一一对应。

## 只用 Prompt、不加 Tool 可以吗？

可以。例如只配置「总结」Prompt：

- 用户选择 Prompt 并填入内容后，对话里会出现「请总结以下内容：\n\nxxx」；
- 总结动作可以由 **Cursor 自带的模型**根据这段消息直接生成，不一定要我们提供 summarize Tool。

若希望「一点就得到结果」且结果来自**我们自己的 API**（例如统一走我们的 LLM 或第三方总结服务），则可以**再配置一个 summarize 类型的动态 Tool**（如 `http_call`）；模型在对话中可以选择调用该 Tool，从而与我们提供的 Tool 结合使用。

## 总结

- **Prompts**、**Tools**、**Resources** 在 MCP 里是三套独立能力；不需要在系统里把其中两者「绑定」才能用。
- **结合**发生在**使用流程**中：Prompt 生成指令/消息 → 插入对话；Resources 提供可读上下文（列表 + 按 URI 读内容）；Tool 由模型决定调用并执行。若只想要「插入一段固定格式的提示」，只配 Prompt 即可；若还要提供「可被模型调用的执行能力」，再配 Tool；若需要「暴露可被列出和读取的数据」，则需服务端实现 Resources（本项目当前未实现）。
