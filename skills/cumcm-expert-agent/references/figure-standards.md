# 数模正式图标准

## 先写图的主张

每张图在绘制前以 YAML 或 JSON 定义结构化 `figure_intent`。不得只写一段自由文本；至少包含 `figure_id`、`role`、`claim`、`visual_grammar`、`evidence_signature`、`nearest_figure`、`why_not_merge`、`data_sources`、`axes`、`color_roles`、`entity_color_waiver`、`caption_layers`、`text_location` 和 `exports`。没有主张的图不进入正文；图注声称的最优点、阈值、事件根、并集或不确定性必须在图中真实存在。

```yaml
figure_id: fig_q2_landscape
role: paper                    # paper | support
claim: 全局最优解位于稳定低值盆地而非孤立尖点
visual_grammar: optimization_landscape
evidence_signature:
  sources: [results/q2_grid.csv#sha256:<digest>]
  variables: [objective_s, release_time_s, heading_deg]
  slice: {scenario: baseline, cohort: FY1}
  transform: median_over_seed
  result: optimum_and_basin
nearest_figure:
  figure_id: fig_q2_sensitivity
  grammar_relation: different  # same | similar | different
  evidence_overlap: partial     # none | partial | same
why_not_merge: 两图分别证明可识别性与扰动稳健性；合并后最终栏宽无法读出置信区间
data_sources: [results/q2_grid.csv]
axes: {x: release_time_s, y: heading_deg, color: objective_s}
color_roles: {surface: sequential_value, optimum: event_detonation}
entity_color_waiver: null
caption_layers: [surface, optimum, confidence_contour]
text_location: sec:q2-results
exports: [figures/q2_landscape.pdf, figures/q2_landscape.png]
```

`visual_grammar` 必须使用全篇统一的规范枚举，例如 `geometry_schematic`、`optimization_landscape`、`event_timeline`、`interval_arithmetic`、`assignment_matrix`、`spatial_trajectory`、`convergence_diagnostic`、`paired_sensitivity`；不得用“图 3 风格”一类临时名称规避比对。`evidence_signature` 由规范化数据源及其内容哈希、变量与单位、样本/场景切片、聚合或变换、直接产出的证据结果组成；字段按键排序后计算 SHA-256。比较重复证据时同时比较规范化字段，不能只比较摘要文字或文件名。

同时写出 panel contract：每个子图提供哪一条不可替代的证据。两个子图若只是在不同外观下重复同一组数值，合并或删除其中一个。多面板图通常控制在 2--3 个子图；超过 3 个时必须证明缩至最终栏宽后每个子图仍可读。

完整论文还必须在单图 contract 之上建立按最终 PDF 顺序排列的“主张—视觉语法—证据签名”组合表，并执行跨全文门禁；门禁比较全部 `role: paper` 图，不受是否相邻、是否隔章或是否交替出现影响：

1. 按 `visual_grammar` 对全文分组。任意语法出现第二次起，每张重复图都必须把全文中证据最接近的正式图写入 `nearest_figure`，并给出非空 `why_not_merge`。
2. 再跨语法比较 `evidence_signature`。证据签名相同的图原则上合并或删除；签名部分重叠时，`why_not_merge` 必须说明各自新增的可检验推断，以及合并为何会损失该推断。
3. `why_not_merge` 不能使用“丰富图型”“版面更好看”“分别展示更清楚”等审美理由。若不能指出不可替代的变量关系、尺度、反事实、诊断或不确定性证据，则门禁失败。
4. `nearest_figure` 指全文证据重叠最高的正式图，不是版面上最近的图；确无可比图时仍写 `{figure_id: null, grammar_relation: different, evidence_overlap: none}`。
5. `role: support` 只用于附录、调试和复核，不能通过改角色规避重复门禁；与正文图同证据的支撑图不得回流正式图清单。

“图型丰富”只能来自证据关系不同，不得为满足种类数额创造无意义的柱图、雷达图或环图。

## 学术图形语法

正式论文图不是仪表盘、信息海报或软件界面。除真正的流程图外，禁止用圆角卡片、胶囊标签、状态徽章、彩色卡片头、大面积文字框和装饰性气泡组织定量证据。不要把每个主体画成一张独立卡片；应把同类实体放到共享坐标轴上，使位置、长度、斜率或面积可以直接比较。

- 连续事件：使用共享时间轴上的事件栅格、区间、阶梯或事件函数；投放、起爆、进入、退出用固定形状冗余编码。
- 几何关系：使用等比例主图和必要的一个局部放大；辅助视线、构造线和边界降低明度。
- 参数响应：主响应面占主要面积，剖面放在下方或侧面并保持可读尺寸；文字不得压在深色填充上。
- 多主体轨迹：共享坐标轴，直接标注实体；局部窗只保留主图无法看清的证据，不重复坐标、比例尺和图例。
- 覆盖与调度：保留事件或状态阶梯；减少重复实体标签，让总覆盖、最大空窗和冲突位置成为第一视觉层级。

图内不重复论文图题。大段解释放入正文和图注，图内只保留变量、单位、关键事件、阈值与少量结论性数值。若缩略图中首先看到的是卡片边框、装饰箭头或一排文字，而不是数据关系，视为构图失败。

## 语义模板

优先让 `create_plot` 的 `template` 承担论文语义，不把所有任务退化成折线或柱状图：

- `root_event_zoom`：连续事件函数、阈值线和精化根；传入 `event_times`。
- `coverage_timeline`：多主体时间窗及自动计算的并集、重叠、内部空档。
- `optimization_landscape`：二维响应面及 `optimum` 标记，颜色条必须有指标和单位。
- `convergence_audit`：误差/目标随网格、迭代或种子演化，可设置对数轴与阈值。
- `paired_sensitivity`：基线—扰动配对点与差值，避免被量纲大的问题支配。
- `trajectory_geometry`：等比例轨迹、关键点、边界/圆/线段等几何图层。

没有专用语义时使用 `contest_paper`，但仍需填写主张、单位和数据来源。
多面板图的顶层使用 `contest_paper`，每个 `panels[]` 独立选择语义模板和填写意图，避免把同一个最优点或阈值错误复制到异构面板。

## 选择图形

- 时间/路径演化：折线或轨迹图，必要时标注关键事件。
- 变量关系：散点 + 合理拟合与不确定性，不用折线制造顺序。
- 方案比较：排序点图、哑铃图或斜率图，同时显示基线；类别少时不默认用柱状图。
- 分布与误差：直方图、ECDF、箱线/小提琴图或残差图。
- 灵敏度：单参数响应、龙卷风图或二维响应面。
- 多目标：Pareto 前沿并突出代表解，不用仅给三维装饰图。
- 空间覆盖/可见性：等比例坐标、边界与关键几何体同时显示。

小于 10 个样本时优先显示全部点；少于 5 个样本禁止用箱线图。若全部波动不超过数值容差，报告“在容差内一致”，不得截断纵轴放大成有意义的分布差异。

## 版式与质检

- 正文已有完整图注时，图内不重复超大总标题；多面板使用简短 A/B 标签。
- 颜色只编码语义角色，并用线型、标记或文字形成冗余；网格只保留读数必需方向。
- `figureLint` 的错误必须清零；逐项处理单位、图层和区间摘要警告。
- 比较返回的请求尺寸与实际尺寸，宽高误差均不超过 5%；在论文最终栏宽下检查 7--9 pt 文字仍可读。
- 主数据线通常取 1.2--1.6 pt，坐标轴和辅助线取 0.5--0.9 pt；强调线不超过 1.8 pt。刻度控制在 4--7 个，避免把数值逐点写在图上。
- 图的留白用于分组和视线引导，不为“卡片感”预留大块空区。局部图应共享坐标范围或明确给出断轴/局部范围，不得用非连续位置暗示连续几何关系。
- LaTeX/Word 中使用图浮动与合理缩放，避免强制定位造成半页空白。逐页检查图、图注与首次解释是否相邻。

## MATLAB 语义配色

正式 MATLAB 图先确定整篇的语义映射，再绘制单图。优先复用
[`assets/matlab/contest_figure_theme.m`](../assets/matlab/contest_figure_theme.m)。国赛论文的层次主要来自线宽、留白、明度、线型、标记与局部标注，不来自增加高饱和颜色。默认采用暖纸白 `#FAFAF7`、深墨 `#1E2A32`、矿物蓝主色 `#2F6079`、矿物绿辅色 `#3D7A70`，暖赭 `#B5782F` 强调关键事件、阈值和最大空档，酒红 `#8B4E5A` 表示风险或离散。大面积底色必须是纸白或 `#F1F4F2` 一类近白中性色。

- 每个单面板最多出现 2 个主数据色；整张多面板图通常不超过 3 个低饱和数据色。若读者第一眼先注意到“配色”而非结论，视为视觉门禁失败。
- 资源—目标指派、类别空间轨迹等确实需要 4--7 个实体颜色时，必须在 `figure_intent` 和审计 JSON 中登记 `entity_color_waiver`；少于 4 个或多于 7 个实体不得使用此例外。waiver 至少包含 `enabled: true`、`reason`、`entity_count`、`entities`、`palette_source`、`redundant_encoding`、`coexisting_semantic_roles` 和 `reserved_color_conflict: false`。`reason` 必须说明颜色承担的类别比较任务，不能写“更美观”或“更丰富”；每个实体还必须有不同线型、点型或直接标签。
- `entity_color_waiver` 仅在 `coexisting_semantic_roles: []` 时有效。同一面板一旦出现释放、起爆、进入、退出、风险、主/保守评分或阈值等保留语义，禁止再使用 4--7 色实体类别板；实体统一改用 `T.entityNeutral`，靠 `T.entityLineStyle`、`T.entityMarker` 与直接标签区分，事件继续使用 `T.event.*`。这条规则避免类别色与事件色在同图发生换义或近似色误读。
- 多实体不再逐实体分配彩虹色。FY1--FY5、M1--M3 默认使用中性蓝灰、实线/虚线/点划线、圆/方/三角等标记和直接标签区分；仅在 waiver 通过且图中没有保留语义色时，才可显式调用 `T.entityCategorical`。不得把 `T.blue`、`T.teal`、`T.amber`、`T.coral` 或 `T.ink` 当作实体编号色。
- 事件跨图固定：释放=深墨菱形，起爆=暖赭圆，进入=青灰上三角，退出=蓝灰下三角。颜色只是冗余编码，形状与文字必须独立可辨。
- 口径跨图固定：主评分为蓝灰实线圆点，保守审计为酒红虚线方点，阈值为深墨点划线。
- 连续值使用近白—浅蓝灰—青灰—深蓝灰的单调色图；最优点另用暖赭标记。禁用 `jet`、彩虹、霓虹黄绿和大跨度紫—绿—黄组合。
- 面板标题、卡片头、状态带与区间填充不得使用整块饱和色；改用近白填充配窄色条、边线或小标记。
- 不用颜色单独承担结论；同时固定线型、标记和直接标注，确保灰度输出可辨。

## 视觉迭代门禁

完整论文不通过“单图成功导出”就默认视觉合格。每轮必须生成全部正式图的彩色联系表，并对关键图另做灰度版检查：

1. 在最终栏宽下查文字、图例、标注、色条和面板是否重叠或裁切。
2. 检查同一实体、事件和指标在所有图中颜色是否一致，不得为了局部好看而换义。
3. 检查引导顺序：读者应先看到结论或关键事件，再看到辅助网格与次要数值。
4. 灰度下若两组数据难以区分，先增加线型、标记或直接标注，不是盲目增色。
5. 长条、柱状或大段数值罗列若不直接证明主张，改为事件节点、区间并集、阶梯、斜率图或几何局部图。
6. 缩小查看整篇彩色联系表：若形成“彩虹墙”、相邻图主色频繁跳变或大色块抢过正文，必须回退色彩预算；丰富度应由图形结构和证据层级提供。
7. 在最终 PDF 页面而非单张 PNG 中检查视觉质量；单图可读但嵌入正文后文字小于 7 pt、剖面过窄或标签相撞，仍判为失败。
8. 将“正文正式图”和“支撑诊断图”分开管理。未进入正文、与现有图重复或只有开发统计意义的图不得混入正式图清单。
9. 检查图题与实际面板数量一致，A/B/C 的每个说明都必须对应真实子图；更改布局后同步改正文、图题和图清单。

每轮门禁还必须生成可追溯审计包，默认置于 `support/figure-audit/`：

- `figure-contact-sheet.png`：只使用本轮正式导出文件，按最终 PDF 的 `paper_order` 排列，并在缩略图下标出 `figure_id`、`visual_grammar` 和主张短句。
- `figure-contact-sheet-gray.png`：与彩色联系表同尺寸、同顺序、同源文件的灰度版；不得另行手工调整图层。
- `figure_audit.json`：至少记录 `schema_version`、`paper_order`、`figures[]`、`contact_sheets`、`manuscript`、`status` 和 `reviewed_at`。每个 `figures[]` 条目必须包含 `figure_id`、`role`、`visual_grammar`、规范化 `evidence_signature` 及其 SHA-256、`nearest_figure`、`why_not_merge`、`color_roles`、`entity_color_waiver`，以及每个 PNG/PDF/SVG 的相对路径和 SHA-256；两张联系表与最终论文 PDF 也必须记录路径和 SHA-256。
- `figure_audit.json.sha256`：记录审计 JSON 自身的 SHA-256。`paper_order` 同时计算规范化列表哈希，保证联系表顺序与正文顺序一致。

只要正式图文件、`paper_order`、联系表或最终 PDF 任一哈希变化，既有审计立即视为 `stale`，必须从当前导出物重建联系表、重算全部哈希并重新执行跨全文重复语法/证据门禁；不得手改 JSON 的 `status: pass`。

## 交付规范

- 中文标题、轴名、图例和单位；字体缺失时使用可用中文字体并记录。
- 使用色盲友好配色；颜色之外再用线型、标记或注释编码。
- 不截断坐标轴夸大差异；对数轴必须标注。
- 输出至少 300 dpi PNG，并保留 PDF/SVG；MATLAB/Origin 同时保留可编辑工程。
- 图、表、正文中的数值和单位必须由同一次运行生成。
