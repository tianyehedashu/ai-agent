"""
Product Info Constants - 产品信息原子能力常量与默认提示词

能力 ID 与步骤依赖关系；系统默认提示词不落库，由此模块提供。
业务能力配置与模型能力层分离：CapabilityConfig 仅含业务配置 + 模型特性需求引用。
"""

from dataclasses import dataclass

# 原子能力 ID（与前端、API 一致）
CAPABILITY_IMAGE_ANALYSIS = "image_analysis"
CAPABILITY_PRODUCT_LINK_ANALYSIS = "product_link_analysis"
CAPABILITY_COMPETITOR_LINK_ANALYSIS = "competitor_link_analysis"
CAPABILITY_VIDEO_SCRIPT = "video_script"
CAPABILITY_IMAGE_GEN_PROMPTS = "image_gen_prompts"


@dataclass(frozen=True)
class CapabilityConfig:
    """业务能力配置（与模型实现无关，仅引用模型特性名）"""

    id: str
    name: str
    sort_order: int
    output_key: str
    dependencies: tuple[str, ...]
    input_fields: tuple[str, ...]
    meta_prompt_params: tuple[tuple[str, str], ...]
    default_prompt: str
    optimize_system_prompt: str
    temperature: float = 0.3
    max_tokens: int = 2048
    required_features: frozenset[str] = frozenset()


# 系统默认提示词（用于「恢复模板」）。含 {{param}} 占位符，执行时自动替换为实际输入/前步输出
_DEFAULT_PROMPTS: dict[str, str] = {
    CAPABILITY_IMAGE_ANALYSIS: (
        "你是专业的电商产品图像分析专家和视觉设计顾问。"
        "请根据产品: {{product_name}}，分析提供的图片: {{image_urls}}：\n\n"
        "提取：产品类型/品类、产品名称、主要颜色和配色、材质、预估尺寸；"
        "产品形状轮廓、表面工艺、设计风格、重要部件；从图片推测的主要功能、卖点、使用场景；"
        "为每张产品图生成可用于重新生成类似商品图的中英文提示词。"
    ),
    CAPABILITY_PRODUCT_LINK_ANALYSIS: (
        "你是资深产品调研助手。根据商品链接 {{product_link}}、产品名称 {{product_name}} 或关键词 {{keywords}}，分析并输出：\n"
        "品类与定位、核心卖点（3-5 个）、主要使用场景、目标人群、差异化优势；"
        "产品规格（尺寸、重量、颜色、材质）若可获取；"
        "若提供 1688 产品标题，请结合理解主要特征和卖点。"
        "输出为结构化 JSON 或清晰段落，便于后续 Listing 文案与生图参考。"
    ),
    CAPABILITY_COMPETITOR_LINK_ANALYSIS: (
        "你是专业的电商竞品分析师，擅长从竞品页面提取商业情报，特别是用户评价的深度分析。\n\n"
        "根据竞品链接 {{competitor_link}}，结合产品 {{product_name}} 及已有产品信息 {{product_info}} 进行分析。\n\n"
        "【重点提取】基本信息（标题、价格、评分、品牌）；产品规格（尺寸、重量、颜色、材质）；"
        "卖点分析；评价深度分析：positive_reviews（用户称赞点如耐用、易用、尺寸合适）、"
        "negative_reviews（用户抱怨点如包装简陋、使用复杂）、improvement_opportunities（可改进机会）。\n\n"
        "以 JSON 格式输出，便于后续 Listing 文案中针对竞品缺点设计卖点策略。"
    ),
    CAPABILITY_VIDEO_SCRIPT: (
        "你是亚马逊商品视频分镜助手。根据产品信息 {{product_info}} 与竞品信息 {{competitor_info}}，"
        "结合产品名称 {{product_name}}、关键词 {{keywords}}，输出一个 JSON 对象，包含两个字段：\n\n"
        "1. shots: 5 镜分镜脚本数组，每镜含 镜号、焦点、简短描述、prompt（中文描述）：\n"
        "   - 镜 1: 整体展示（白底、产品居中、专业影棚灯光）\n"
        "   - 镜 2: 细节特写（关键卖点、材质工艺）\n"
        "   - 镜 3: 使用场景（生活化展示、自然光线）\n"
        "   - 镜 4: 卖点强化（针对竞品缺点的优势展示）\n"
        "   - 镜 5: 收尾/品牌（品牌主张、品质承诺）\n\n"
        "2. video_prompt: 一段完整的英文视频生成提示词（直接用于 Sora 等视频生成模型），"
        "将 5 镜内容融合为一段连贯的视频描述。要求：\n"
        "   - 用英文自然语言描述整个视频从开头到结尾的连续画面\n"
        "   - 包含镜头运动（如 smooth camera pan, close-up transition, zoom out）\n"
        "   - 描述灯光、色调、氛围变化\n"
        "   - 控制在 150-300 词，不要包含 JSON 结构，纯英文文字描述\n\n"
        "保持连贯与专业，可参考竞品的视觉优点进行设计。"
    ),
    CAPABILITY_IMAGE_GEN_PROMPTS: (
        "你是电商产品图设计 AI 提示词专家。根据产品信息 {{product_info}} 与视频脚本 {{video_script}}，"
        "结合竞品信息 {{competitor_info}}、图片描述 {{image_descriptions}}、产品名称 {{product_name}}，生成 8 张主图对应的英文图片生成提示词。\n\n"
        "【绝对红线】产品无变形、无失真、真实比例；商品必须是每张图片的绝对主角；"
        "若有产品参考图，生图必须严格参考产品外观。\n\n"
        "【结构要求】第 1 张：纯白背景 RGB(255,255,255)，只展示单个产品，产品占画面 85% 以上，"
        "无文字、无配件、无水印，1000x1000 以上高清。\n"
        "第 2-8 张：可包含细节特写、生活场景、卖点展示、使用演示等，2:3 比例。\n\n"
        "【竞品隐性打击】针对竞品常见差评（质量差、做工粗糙、材质差、不耐用、操作复杂等），"
        "在场景设计中体现我方优势，不直接攻击竞品。\n\n"
        "输出为 8 条字符串的 JSON 数组，每条 80 词以内，适合文生图模型。"
    ),
}

# Runner 执行时的 JSON 输出系统指令（配合 response_format=json_object 使用）
RUNNER_JSON_SYSTEM_PROMPT = (
    "你是专业的电商AI助手。请严格以合法的 JSON 对象格式输出结果。"
    "直接输出 JSON，不要使用 markdown 代码块包裹，不要添加任何非 JSON 的解释文本。"
)

# 提示词优化的系统指令（可选功能：AI 改进用户提示词）
_OPTIMIZE_SYSTEM_PROMPT = (
    "你是一个提示词工程专家。用户会提供一段提示词和当前上下文信息。"
    "请根据这些内容，优化为一份更详细的、可直接发送给 AI 执行的提示词。"
    "优化后的提示词应包含完整的任务描述、输出格式要求和所有必要的上下文细节。"
    "直接输出最终提示词文本，不要添加任何解释或前缀。"
)

_OPTIMIZE_SYSTEM_PROMPTS: dict[str, str] = {
    CAPABILITY_IMAGE_ANALYSIS: (
        "你是一个提示词工程专家，专注于商品图分析任务。"
        "根据用户的提示词和上下文，优化为一份详细的商品图片分析提示词。"
        "优化后的提示词应明确分析维度、输出格式（结构化 JSON）和质量要求。"
        "直接输出最终提示词文本。"
    ),
    CAPABILITY_PRODUCT_LINK_ANALYSIS: (
        "你是一个提示词工程专家，专注于产品调研任务。"
        "根据用户的提示词和上下文，优化为一份详细的产品分析提示词。"
        "优化后的提示词应包含调研维度、输出结构和具体要求。"
        "直接输出最终提示词文本。"
    ),
    CAPABILITY_COMPETITOR_LINK_ANALYSIS: (
        "你是一个提示词工程专家，专注于竞品分析任务。"
        "根据用户的提示词和上下文，优化为一份详细的竞品对比分析提示词。"
        "直接输出最终提示词文本。"
    ),
    CAPABILITY_VIDEO_SCRIPT: (
        "你是一个提示词工程专家，专注于电商视频分镜脚本任务。"
        "根据用户的提示词和上下文（产品信息、竞品信息等），优化为一份详细的分镜脚本提示词。"
        "优化后的提示词应明确镜数、每镜要素和输出格式。"
        "直接输出最终提示词文本。"
    ),
    CAPABILITY_IMAGE_GEN_PROMPTS: (
        "你是一个提示词工程专家，专注于电商主图生成任务。"
        "根据用户的提示词和上下文，优化为一份详细的 8 图提示词生成指令。"
        "优化后的提示词应明确每张图的定位、风格要求和输出为 JSON 数组的格式。"
        "直接输出最终提示词文本。"
    ),
}

# 提示词可用占位符：每能力可引用的输入/输出参数，用于 {{param}} 渲染
_META_PROMPT_PARAMS: dict[str, list[tuple[str, str]]] = {
    CAPABILITY_IMAGE_ANALYSIS: [
        ("product_name", "产品名称"),
        ("image_urls", "图片链接"),
    ],
    CAPABILITY_PRODUCT_LINK_ANALYSIS: [
        ("product_link", "产品链接"),
        ("product_name", "产品名称"),
        ("keywords", "关键词"),
    ],
    CAPABILITY_COMPETITOR_LINK_ANALYSIS: [
        ("competitor_link", "竞品链接"),
        ("product_name", "产品名称"),
        ("product_info", "产品信息（前步）"),
    ],
    CAPABILITY_VIDEO_SCRIPT: [
        ("product_name", "产品名称"),
        ("keywords", "关键词"),
        ("product_info", "产品信息（前步）"),
        ("competitor_info", "竞品信息（前步）"),
    ],
    CAPABILITY_IMAGE_GEN_PROMPTS: [
        ("product_name", "产品名称"),
        ("product_info", "产品信息（前步）"),
        ("competitor_info", "竞品信息（前步）"),
        ("video_script", "视频脚本（前步）"),
        ("image_descriptions", "图片描述（前步）"),
    ],
}

# 统一能力配置（单一数据源，派生以下所有常量）
CAPABILITIES: dict[str, CapabilityConfig] = {
    CAPABILITY_IMAGE_ANALYSIS: CapabilityConfig(
        id=CAPABILITY_IMAGE_ANALYSIS,
        name="图片分析",
        sort_order=1,
        output_key="image_descriptions",
        dependencies=(),
        input_fields=("image_urls", "product_name"),
        meta_prompt_params=tuple(_META_PROMPT_PARAMS[CAPABILITY_IMAGE_ANALYSIS]),
        default_prompt=_DEFAULT_PROMPTS[CAPABILITY_IMAGE_ANALYSIS],
        optimize_system_prompt=_OPTIMIZE_SYSTEM_PROMPTS[CAPABILITY_IMAGE_ANALYSIS],
        temperature=0.3,
        max_tokens=2048,
        required_features=frozenset({"vision"}),
    ),
    CAPABILITY_PRODUCT_LINK_ANALYSIS: CapabilityConfig(
        id=CAPABILITY_PRODUCT_LINK_ANALYSIS,
        name="商品链接分析",
        sort_order=2,
        output_key="product_info",
        dependencies=(),
        input_fields=("product_link", "product_name", "keywords"),
        meta_prompt_params=tuple(_META_PROMPT_PARAMS[CAPABILITY_PRODUCT_LINK_ANALYSIS]),
        default_prompt=_DEFAULT_PROMPTS[CAPABILITY_PRODUCT_LINK_ANALYSIS],
        optimize_system_prompt=_OPTIMIZE_SYSTEM_PROMPTS[CAPABILITY_PRODUCT_LINK_ANALYSIS],
        temperature=0.3,
        max_tokens=2048,
        required_features=frozenset(),
    ),
    CAPABILITY_COMPETITOR_LINK_ANALYSIS: CapabilityConfig(
        id=CAPABILITY_COMPETITOR_LINK_ANALYSIS,
        name="竞品链接分析",
        sort_order=3,
        output_key="competitor_info",
        dependencies=(),
        input_fields=("competitor_link", "product_name"),
        meta_prompt_params=tuple(_META_PROMPT_PARAMS[CAPABILITY_COMPETITOR_LINK_ANALYSIS]),
        default_prompt=_DEFAULT_PROMPTS[CAPABILITY_COMPETITOR_LINK_ANALYSIS],
        optimize_system_prompt=_OPTIMIZE_SYSTEM_PROMPTS[CAPABILITY_COMPETITOR_LINK_ANALYSIS],
        temperature=0.3,
        max_tokens=2048,
        required_features=frozenset(),
    ),
    CAPABILITY_VIDEO_SCRIPT: CapabilityConfig(
        id=CAPABILITY_VIDEO_SCRIPT,
        name="视频脚本/分镜",
        sort_order=4,
        output_key="video_script",
        dependencies=(CAPABILITY_PRODUCT_LINK_ANALYSIS, CAPABILITY_COMPETITOR_LINK_ANALYSIS),
        input_fields=("product_name", "keywords"),
        meta_prompt_params=tuple(_META_PROMPT_PARAMS[CAPABILITY_VIDEO_SCRIPT]),
        default_prompt=_DEFAULT_PROMPTS[CAPABILITY_VIDEO_SCRIPT],
        optimize_system_prompt=_OPTIMIZE_SYSTEM_PROMPTS[CAPABILITY_VIDEO_SCRIPT],
        temperature=0.4,
        max_tokens=4096,
        required_features=frozenset(),
    ),
    CAPABILITY_IMAGE_GEN_PROMPTS: CapabilityConfig(
        id=CAPABILITY_IMAGE_GEN_PROMPTS,
        name="8 图生成提示词",
        sort_order=5,
        output_key="prompts",
        dependencies=(CAPABILITY_PRODUCT_LINK_ANALYSIS, CAPABILITY_VIDEO_SCRIPT),
        input_fields=("product_name",),
        meta_prompt_params=tuple(_META_PROMPT_PARAMS[CAPABILITY_IMAGE_GEN_PROMPTS]),
        default_prompt=_DEFAULT_PROMPTS[CAPABILITY_IMAGE_GEN_PROMPTS],
        optimize_system_prompt=_OPTIMIZE_SYSTEM_PROMPTS[CAPABILITY_IMAGE_GEN_PROMPTS],
        temperature=0.3,
        max_tokens=2048,
        required_features=frozenset(),
    ),
}

# 派生常量
CAPABILITY_IDS: list[str] = [c.id for c in CAPABILITIES.values()]
CAPABILITY_ORDER: list[tuple[int, str]] = [
    (c.sort_order, c.id) for c in sorted(CAPABILITIES.values(), key=lambda x: x.sort_order)
]
CAPABILITY_DEPENDENCIES: dict[str, list[str]] = {
    cid: list(cfg.dependencies) for cid, cfg in CAPABILITIES.items()
}
CAPABILITIES_REQUIRING_VISION: frozenset[str] = frozenset(
    cid for cid, cfg in CAPABILITIES.items() if "vision" in cfg.required_features
)
DEFAULT_PROMPTS: dict[str, str] = {cid: cfg.default_prompt for cid, cfg in CAPABILITIES.items()}
OPTIMIZE_SYSTEM_PROMPT = _OPTIMIZE_SYSTEM_PROMPT
OPTIMIZE_SYSTEM_PROMPTS: dict[str, str] = {
    cid: cfg.optimize_system_prompt for cid, cfg in CAPABILITIES.items()
}
META_PROMPT_PARAMS: dict[str, list[tuple[str, str]]] = {
    cid: list(cfg.meta_prompt_params) for cid, cfg in CAPABILITIES.items()
}

# 8 图默认提示词（image_gen_prompts 的 prompts 数组，用于模板）
DEFAULT_IMAGE_GEN_PROMPTS_8: list[str] = [
    "Product on plain white background, centered, studio lighting, 5600K, high resolution, e-commerce",
    "Product detail shot, close-up, key feature highlight, clean background",
    "Product in lifestyle context, natural use scenario, soft lighting",
    "Product key selling point, feature focus, professional photography",
    "Product multi-angle or packaging, commercial style",
    "Product with benefits text or icon overlay, minimalist",
    "Product comparison or before-after style, clear layout",
    "Product with brand logo or tagline, premium feel",
]
