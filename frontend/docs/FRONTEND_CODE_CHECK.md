# Frontend Code Check 报告

> 检查范围：类型安全、规范符合、重复代码、架构与目录、可访问性、测试与文档缺口。

---

## 一、总体结论

| 维度         | 状态 | 说明                                                      |
| ------------ | ---- | --------------------------------------------------------- |
| 类型安全     | 通过 | 未发现 `any` / `as any`；仅测试中有合理 eslint-disable    |
| 规范符合     | 通过 | 导入顺序、API/类型分层、状态管理符合 CODE_STANDARDS       |
| 重复代码     | 轻微 | 图片灯箱逻辑在 step-output-view 与 image-gen-panel 中重复 |
| 架构与目录   | 通过 | listing-studio 按页面/组件拆分清晰，常量与类型分离        |
| 可访问性     | 通过 | ImageLightbox 已补 role/dialog、焦点陷阱与 Esc            |
| 测试         | 通过 | listing-studio 组件与 API 已有单测                        |
| localStorage | 合规 | 仅 theme-provider 使用，属主题偏好，非认证数据            |

---

## 二、类型与 API 一致性

- **types/listing-studio.ts** 与后端 Schema 对齐（Job、Step、Capability、Template、ImageGenTask、RunStepBody 等），无缺口。
- **api/listingStudio.ts** 全部使用 `import type` 与泛型，与类型定义一致。
- **capabilities**：`GET /listing-studio/capabilities` 返回 `{ capabilities, execution_layers }`，前端不再重复编排分层逻辑。

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

- **listing-studio**
  - 页面：`pages/listing-studio/index.tsx`；子组件：`input-panel`、`job-selector`、`capability-block`、`step-output-view`、`job-detail-drawer`、`image-gen-panel`。
  - 常量：`constants/listing-studio.ts`；类型：`types/listing-studio.ts`；API：`api/listingStudio.ts`。
  - 旧 `/product-info/*` 路由重定向至 `/listing-studio/*`。

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

- **listing-studio**：`input-panel.test.ts`、`step-output-view.test.tsx`、`api/listingStudio.test.ts`、`hooks/use-copy-to-clipboard.test.ts`。

---

## 七、其他

- **theme-provider 与 localStorage**  
  仅用于主题持久化（`vite-ui-theme`），符合「认证信息不直接写 localStorage」的规范，无需修改。

- **CapabilityBlock 保存模板**  
  「模板名」使用裸 `<input type="text">`，与其它表单项风格略不一致；可改为 `<Label>` + `<Input>` 以统一规范（低优先级）。

---

## 八、已做修复（本次）

- **refetchInterval 类型**：`pages/listing-studio/index.tsx` 使用 `ListingStudioJob` 类型。

---

## 九、建议执行顺序

| 优先级 | 项                           | 说明                           |
| ------ | ---------------------------- | ------------------------------ |
| 高     | refetchInterval 类型         | 已修复                         |
| 中     | 抽 ImageLightbox + a11y      | 两处灯箱复用并补 role/焦点/Esc |
| 中     | listing-studio 单测          | 已完成                         |
| 低     | useCopyToClipboard           | 复制逻辑复用                   |
| 低     | CapabilityBlock 模板名表单项 | 换 Label+Input                 |

---

## 十、后续项已全部完成（本次实施）

| 项                         | 实施内容                                                                                                                                                                                                 |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **ImageLightbox + a11y**   | 已抽到 `components/ui/image-lightbox.tsx`；`step-output-view` 与 `image-gen-panel` 复用。                                                                                                                |
| **useCopyToClipboard**     | 已抽到 `hooks/use-copy-to-clipboard.ts`。                                                                                                                                                                |
| **CapabilityBlock 模板名** | 已用 `<Label>` + `<Input>`。                                                                                                                                                                             |
| **listing-studio 单测**    | `input-panel.test.ts`、`step-output-view.test.tsx`、`listingStudio.test.ts`、`output-preview-shared.test.ts`、`use-listing-studio-capabilities.test.ts`。                                                |
| **Listing Studio 迁移**    | 主路径 `/listing-studio`；`types/listing-studio.ts` 单源；capabilities hook 返回 `{ config, isLoading, isError, isFallback }`；生产默认空 inputs；`capability-block` 手风琴 a11y；`npm run check` 通过。 |
