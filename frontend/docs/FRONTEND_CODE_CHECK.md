# Frontend Code Check 报告

> 检查范围：类型安全、规范符合、重复代码、架构与目录、可访问性、测试与文档缺口。

---

## 一、总体结论

| 维度         | 状态   | 说明                                                      |
| ------------ | ------ | --------------------------------------------------------- |
| 类型安全     | 通过   | 未发现 `any` / `as any`；仅测试中有合理 eslint-disable    |
| 规范符合     | 通过   | 导入顺序、API/类型分层、状态管理符合 CODE_STANDARDS       |
| 重复代码     | 轻微   | 图片灯箱逻辑在 step-output-view 与 image-gen-panel 中重复 |
| 架构与目录   | 通过   | product-info 按页面/组件拆分清晰，常量与类型分离          |
| 可访问性     | 待改进 | 灯箱为自定义实现，缺少 role/dialog、焦点陷阱与 aria       |
| 测试         | 缺口   | product-info 页面及组件无单测/集成测                      |
| localStorage | 合规   | 仅 theme-provider 使用，属主题偏好，非认证数据            |

---

## 二、类型与 API 一致性

- **types/product-info.ts** 与后端 Schema 对齐（Job、Step、Capability、Template、ImageGenTask、RunStepBody 等），无缺口。
- **api/productInfo.ts** 全部使用 `import type` 与泛型，与类型定义一致。
- **建议**：`pages/product-info/index.tsx` 中 `refetchInterval` 的 `query.state.data` 断言可改为 `ProductInfoJob`，避免内联 `{ status?: string }`（已在下文修复）。

---

## 三、重复与可复用

1. **图片灯箱（高优先级可做）**  
   `step-output-view.tsx` 与 `image-gen-panel.tsx` 中均有「点击缩略图 → 全屏遮罩展示大图 → 点击/Esc 关闭」逻辑，结构相同。  
   **建议**：抽成通用组件，例如 `components/ui/image-lightbox.tsx` 或 `components/shared/ImageLightbox.tsx`，接收 `src: string | null`、`onClose`，内部处理 `role="dialog"`、`aria-modal`、Esc 与焦点，两处改为复用。

2. **复制到剪贴板 + 短暂 “已复制” 状态**  
   在 `step-output-view.tsx`（JsonBlock、PromptsList）与 `image-gen-panel.tsx` 中重复。  
   **建议**：可抽成 `hooks/use-copy-to-clipboard.ts` 返回 `[copy, copied]`，或使用已有/引入的小工具统一行为（低优先级）。

---

## 四、架构与目录

- **product-info**
  - 页面：`pages/product-info/index.tsx`；子组件：`input-panel`、`job-selector`、`capability-block`、`step-output-view`、`job-detail-drawer`、`image-gen-panel`。
  - 常量：`constants/product-info.ts`；类型：`types/product-info.ts`；API：`api/productInfo.ts`。  
    职责清晰，无越层调用，符合「页面 → 组件 → API/类型」分层。

- **通用组件**
  - 使用 shadcn/ui（Button、Card、Tabs、Sheet、Select、Textarea、Input、Label 等），无重复造轮子。

---

## 五、可访问性（a11y）

1. **灯箱**
   - 当前为 `div` + `role="button"`，语义不准确。  
     **建议**：使用 `role="dialog"`、`aria-modal="true"`、`aria-label="图片预览"`，关闭按钮或遮罩可设 `aria-label="关闭"`，并实现焦点陷阱（打开时焦点移入、关闭时还原），Esc 已支持。

2. **能力区块 / 步骤输出**
   - 折叠面板使用 `button` 触发，可加 `aria-expanded`、`aria-controls` 指向内容区 id，便于读屏。

3. **产品信息输入区**
   - 已使用 `<Label htmlFor={key}>` 与对应 `Input` id，表单关联正确。

---

## 六、测试缺口

- **product-info**：当前无 `*.test.tsx` / `*.test.ts`。
- **建议**（按优先级）：
  1. 对 `inputsToUserInput`（或含该逻辑的 util）做单测，覆盖空输入、部分字段、`image_urls`。
  2. 对 `StepOutputView` 或 `step-output-view` 做组件测：传入 mock step，断言展示的 key 与复制按钮存在。
  3. 对 `productInfoApi` 的请求 URL/body 做 mock 集成测（与现有 `api/client.test.ts` 风格一致）。

---

## 七、其他

- **theme-provider 与 localStorage**  
  仅用于主题持久化（`vite-ui-theme`），符合「认证信息不直接写 localStorage」的规范，无需修改。

- **CapabilityBlock 保存模板**  
  「模板名」使用裸 `<input type="text">`，与其它表单项风格略不一致；可改为 `<Label>` + `<Input>` 以统一规范（低优先级）。

---

## 八、已做修复（本次）

- **refetchInterval 类型**：`pages/product-info/index.tsx` 中 `refetchInterval` 的回调里，将 `(query.state.data as { status?: string } | undefined)` 改为使用 `ProductInfoJob` 类型，保持类型与 `getJob` 返回一致。

---

## 九、建议执行顺序

| 优先级 | 项                           | 说明                           |
| ------ | ---------------------------- | ------------------------------ |
| 高     | refetchInterval 类型         | 已修复                         |
| 中     | 抽 ImageLightbox + a11y      | 两处灯箱复用并补 role/焦点/Esc |
| 中     | product-info 单测            | 先 util/组件，再 API mock      |
| 低     | useCopyToClipboard           | 复制逻辑复用                   |
| 低     | CapabilityBlock 模板名表单项 | 换 Label+Input                 |

---

## 十、后续项已全部完成（本次实施）

| 项                         | 实施内容                                                                                                                                                                                                                                                          |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **ImageLightbox + a11y**   | 新增 `components/ui/image-lightbox.tsx`：`role="dialog"`、`aria-modal="true"`、`aria-label="图片预览"`、关闭按钮 `aria-label="关闭"`、打开时焦点到关闭按钮、Tab 焦点陷阱、Esc 关闭。`step-output-view` 与 `image-gen-panel` 改为复用该组件。                      |
| **useCopyToClipboard**     | 新增 `hooks/use-copy-to-clipboard.ts`：`useCopyToClipboard()` 返回 `[copy, copied]`，`useCopyToClipboardKeyed<K>()` 返回 `[copy, copiedKey]`。JsonBlock、PromptsList、image-gen-panel 的复制逻辑改为使用上述 hook。                                               |
| **CapabilityBlock 模板名** | 「模板名」改为 `<Label htmlFor>` + `<Input id>`，与规范一致。                                                                                                                                                                                                     |
| **product-info 单测**      | 新增 `input-panel.test.ts`（inputsToUserInput 共 4 条用例）、`step-output-view.test.tsx`（StepOutputView 共 5 条用例）、`api/productInfo.test.ts`（listJobs/getJob/runStep/run 共 4 条用例）、`hooks/use-copy-to-clipboard.test.ts`（单测与 keyed 共 4 条用例）。 |
