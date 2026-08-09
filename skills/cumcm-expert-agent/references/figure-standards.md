# 数模正式图标准

## 零、候选图前置硬门禁

正式图没有数量配额。一个子问题可以没有图，也可以有多张图；不得为了“每问一图”、`Q+2`、版面平衡、图型丰富或展示工作量而造图。提出候选图后，先在主张—证据台账中写 `display_decision`，再决定是否创建 `figure_intent`：

```yaml
display_decision:
  candidate_id: q2-optimum-evidence
  verification_task: 核验最优点是否位于稳定盆地而非孤立尖点
  visual_relation: 二维参数响应、等值边界与最优点的相对位置
  simpler_medium_checked: [text, formula, table]
  information_lost_without_figure: 盆地形状、边界距离和局部平坦度
  incremental_evidence: 相对既有表格新增最优点附近的空间稳定性证据
  final_size_readable: true
  decision: figure              # figure | table | formula | text | support | drop
```

只有以下各项全部通过，`decision` 才能为 `figure`：

1. **可视关系存在**：读者需要核验空间几何、连续演化、分布、区间交叠、不确定性、网络结构或多变量关系，而不是只读取一个数或一组精确值。
2. **更简媒介不能无损替代**：若公式、正文或紧凑表格能以相同或更高精度完成核验，则改用该媒介；“图更直观”“更好看”不算信息损失。
3. **新增证据非零**：相对正文、表格和已有图，候选图必须增加新的关系、尺度、反事实、诊断或不确定性证据；只把同一数值换一种画法则合并或删除。
4. **最终尺寸可读**：嵌入最终 PDF 后仍能在正常阅读倍率下辨认变量、单位和关键关系；只有全屏放大才可读的图不得进入正文。
5. **主张可指认**：正文或图注能明确指出读者应核验什么，且图内确有对应图层；“展示结果”“展示过程”不是可检验主张。

每个子图必须单独重复“更简媒介不能替代”和“新增证据非零”两项。任一子图失败就删除或拆到支撑材料，不能用 A/B/C 标签、不同颜色或不同图型为其制造存在理由。流程图同样只在依赖、分支或反馈关系无法用短段落清楚表达时保留。

### 折线图适用性测试

凡用线段连接数据点，必须在 `line_applicability` 中逐项回答；构造线、边界线和解析曲线不属于此测试。以下条件全部满足才能画折线：

1. 横轴或路径顺序具有真实含义，如时间、空间路径、网格尺度、迭代或连续参数；随机种子编号、算法名称、无人机编号和无序方案类别不具有连续顺序。
2. 相邻点之间的线段代表可解释的连续变化、已知路径或状态保持，而不是制图软件的默认连接。
3. 点来自同一过程或可配对对象；独立随机运行、独立样本和不同实体的最终值不得连成一条“趋势”。
4. 缺测、离散事件和不规则采样已如实表达；最佳值只在改进事件发生时变化，应画阶梯而不是平滑斜线。
5. 结论不依赖两点之间未经计算的插值。只有两个条件时可用哑铃图或配对斜率图，但图注不得把它解释为连续趋势。

测试失败时，按证据改用点图、区间图、ECDF、箱线/小提琴、事件栅格、阶梯、表格或分面。随机种子只比较终值时优先显示全部点和中位数/IQR；若要展示收敛，则每条线必须对应一次真实运行的迭代轨迹，不得按种子编号连接终值。

### 颜色预算

颜色按**色相角色**计数，不按曲线数量计数。纸白、黑、灰和同一色相的明度变化属于中性色/单一色相；单色顺序色图计 1 个色相，发散色图计 2 个色相。

- 一张正式图默认只允许“中性色 + 1 个主色相 + 1 个强调色相”，即整图和任一子图均最多 2 个有彩色相。多面板必须共享这两个色相，不能为每个面板另配一套粉彩色。
- 颜色只编码论文中稳定的语义角色。实体编号优先用位置、线型、标记和直接标签；不得把蓝、绿、橙、红轮流分给 FY1--FY5、M1--M3 来制造丰富感。
- 第 3 个及更多色相必须登记 `color_budget_waiver`，说明在分面、直接标签、线型/点型和两色方案下会丢失的具体比较任务。waiver 只允许颜色本身就是核心分类变量且类别需要同屏比较的图；不得用于面板装饰、区分问题编号或复用模板色。超过 5 个需同屏辨认的类别时优先分面或改表。
- waiver 图仍须有冗余编码，并且不能再叠加风险、最优点、阈值等另一套保留色。连续色条、分类色和事件色不得在同一面板争夺同一视觉通道。
- 红/绿不得作为唯一的正负或通过/失败编码；大面积淡蓝、淡绿、淡粉底色若不表示数据范围，视为装饰色并计入失败。

`figure_intent` 和 `figure_audit.json` 必须记录实际使用的有彩色相、语义角色、计数和 waiver。若从最终 PDF 取样所得颜色多于声明、同一语义跨图换色，或灰度后无法靠非颜色编码辨认，颜色门禁失败。

## 先写图的主张

只有 `display_decision.decision: figure` 的候选项才能创建结构化 `figure_intent`。不得只写一段自由文本；至少包含 `figure_id`、`role`、`claim`、`display_decision`、`visual_grammar`、`line_applicability`、`evidence_signature`、`nearest_figure`、`why_not_merge`、`data_sources`、`axes`、`color_budget`、`caption_layers`、`text_location` 和 `exports`。没有主张的图不进入正文；图注声称的最优点、阈值、事件根、并集或不确定性必须在图中真实存在。

```yaml
figure_id: fig_q2_landscape
role: paper                    # paper | support
claim: 全局最优解位于稳定低值盆地而非孤立尖点
display_decision:
  candidate_id: q2-optimum-evidence
  verification_task: 核验最优点是否位于稳定盆地而非孤立尖点
  simpler_medium_checked: [text, formula, table]
  information_lost_without_figure: 盆地形状、边界距离和局部平坦度
  incremental_evidence: 新增最优点附近的空间稳定性证据
  final_size_readable: true
  decision: figure
visual_grammar: optimization_landscape
line_applicability: {applies: false, reason: 响应面和等值线不是离散点默认连线}
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
color_budget:
  chromatic_hues: [mineral_blue, warm_ochre]
  hue_count: 2
  roles: {surface: primary_sequential, optimum: accent}
  waiver: null
caption_layers: [surface, optimum, confidence_contour]
text_location: sec:q2-results
exports: [figures/q2_landscape.pdf, figures/q2_landscape.png]
```

`visual_grammar` 必须使用全篇统一的规范枚举，例如 `geometry_schematic`、`optimization_landscape`、`event_timeline`、`interval_arithmetic`、`assignment_matrix`、`spatial_trajectory`、`convergence_diagnostic`、`paired_sensitivity`；不得用“图 3 风格”一类临时名称规避比对。`evidence_signature` 由规范化数据源及其内容哈希、变量与单位、样本/场景切片、聚合或变换、直接产出的证据结果组成；字段按键排序后计算 SHA-256。比较重复证据时同时比较规范化字段，不能只比较摘要文字或文件名。

同时写出 panel contract：每个子图提供哪一条不可替代的证据，并分别记录存在性测试结果。两个子图若只是在不同外观下重复同一组数值，合并或删除其中一个。多面板不是默认版式；只有共享坐标、共享图例或并置比较能降低认知成本时才合并。超过 3 个子图时必须证明每个子图均有独立证据增量，且缩至最终栏宽后仍可读。

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
- `convergence_audit`：误差/目标随网格或真实迭代演化，可设置对数轴与阈值；独立种子的终值用点/区间分布，不按种子编号连线。
- `paired_sensitivity`：基线—扰动配对点与差值，避免被量纲大的问题支配。
- `trajectory_geometry`：等比例轨迹、关键点、边界/圆/线段等几何图层。

没有专用语义时使用 `contest_paper`，但仍需填写主张、单位和数据来源。
多面板图的顶层使用 `contest_paper`，每个 `panels[]` 独立选择语义模板和填写意图，避免把同一个最优点或阈值错误复制到异构面板。

## 选择图形

- 时间/路径演化：先通过折线图适用性测试；连续过程可用折线/轨迹，分段常值状态用阶梯，离散事件用事件栅格或区间。
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
[`assets/matlab/contest_figure_theme.m`](../assets/matlab/contest_figure_theme.m)。国赛论文的层次主要来自线宽、留白、明度、线型、标记与局部标注，不来自“低饱和但很多色”的粉彩模板。主题只提供纸白/墨色/灰色、矿物蓝主色，以及暖赭或酒红两种**备选**强调色；一张图至多选其中一种强调色，不能同时把两者当作装饰色。

- 默认实体全部使用 `T.entityNeutral`，靠 `T.entityLineStyle`、`T.entityMarker` 与直接标签区分。主题不提供现成 5--7 色实体板，防止把实体编号自动映射成一排柔和色。
- 事件跨图固定：释放用深墨菱形，起爆用所选强调色圆点，进入与退出共用矿物蓝并分别使用上/下三角。颜色是冗余编码，形状与文字必须独立可辨。
- 口径比较固定：主评分为矿物蓝实线圆点；保守或风险口径才选酒红虚线方点。若图中已经使用暖赭表示最优点/事件，则不得再加入酒红，除非 `color_budget_waiver` 通过。
- 连续值优先使用同一主色相的单调顺序色图；最优点可用所选强调色。仅当零点两侧方向本身是结论时使用两色发散图。禁用 `jet`、彩虹、霓虹黄绿和大跨度紫—绿—黄组合。
- 坐标区与面板默认保持纸白。只有置信区间、容差区、可行域等数据语义范围才能填浅色；不得为每个子图铺不同淡色底、卡片头或状态带。
- MATLAB 脚本在导出前统计实际有彩色相并调用 `T.assertColorBudget(hueCount, accentCount, hasWaiver)`；同时调用 `T.assertGrayscaleEncoding(lineStyles, markers, directLabels)` 检查每对序列都有非颜色冗余编码。任一断言失败不得导出正式图；通过后仍须生成灰度版并在最终 PDF 尺寸下人工复核。超预算时先删色、改线型/点型或分面，不得仅把颜色调淡后宣称合格。

## 人工论文风格检查

自动 lint 不能替代人工判断。完成排版后，必须对**实际最终 PDF**做一次非自动化视觉检查，并在 `figure_audit.json` 的 `human_paper_style_review` 中记录评阅者、PDF SHA-256、检查时间、结论和具体问题。至少同时查看整篇页面联系表、100% 正常阅读倍率下的关键页和关键图灰度版。

以下各项必须全部为 `PASS`：

1. 页面首先像连续的学术论文，而不是演示文稿、数据驾驶舱、产品报告或“证据海报”；标题、图、表与正文形成普通论文层级。
2. 没有重复的圆角容器、卡片头、状态条、图标、胶囊标签、渐变背景、每面板一色或大块粉彩底色；非数据边框和背景不成为联系表中的第一视觉层。
3. 每张图和每个子图都能说出独立的核验任务；仅为填满页面、对齐网格或展示工作量的面板已经删除。
4. 折线、颜色和坐标尺度均通过对应硬门禁；图注不靠“蓝线/红点”才能理解，灰度下仍可辨。
5. 图嵌入正文后仍可读，且相邻两页没有机械重复同一 3 面板模板、同一粉彩配色或相同装饰结构。
6. 附录中的代码、表格和复现证据保持论文排版，不是整页截图墙；内部审计联系表、哈希清单和 UI 预览不得回流正文或附录。

任一项失败就回到媒介选择、布局或绘图脚本修改。不得用“低饱和”“风格统一”“信息量大”覆盖人工风格否决。

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
10. 逐图复核存在性、折线适用性和颜色预算，并完成 `human_paper_style_review`；任何自动审计通过都不能覆盖人工 `FAIL`。

每轮门禁还必须生成可追溯审计包，默认置于 `support/figure-audit/`：

- `figure-contact-sheet.png`：只使用本轮正式导出文件，按最终 PDF 的 `paper_order` 排列，并在缩略图下标出 `figure_id`、`visual_grammar` 和主张短句；它只用于内部审计，不进入论文正文或附录。
- `figure-contact-sheet-gray.png`：与彩色联系表同尺寸、同顺序、同源文件的灰度版；不得另行手工调整图层。
- `figure_audit.json`：至少记录 `schema_version`、`paper_order`、`figures[]`、`contact_sheets`、`manuscript`、`human_paper_style_review`、`status` 和 `reviewed_at`。每个 `figures[]` 条目必须包含 `figure_id`、`role`、`display_decision`、`visual_grammar`、`line_applicability`、规范化 `evidence_signature` 及其 SHA-256、`nearest_figure`、`why_not_merge`、`color_budget`、panel contract，以及每个 PNG/PDF/SVG 的相对路径和 SHA-256；两张联系表与最终论文 PDF 也必须记录路径和 SHA-256。
- `figure_audit.json.sha256`：记录审计 JSON 自身的 SHA-256。`paper_order` 同时计算规范化列表哈希，保证联系表顺序与正文顺序一致。

只要正式图文件、`paper_order`、联系表或最终 PDF 任一哈希变化，既有审计立即视为 `stale`，必须从当前导出物重建联系表、重算全部哈希并重新执行跨全文重复语法/证据门禁；不得手改 JSON 的 `status: pass`。

## 交付规范

- 中文标题、轴名、图例和单位；字体缺失时使用可用中文字体并记录。
- 使用色盲友好配色；颜色之外再用线型、标记或注释编码。
- 不截断坐标轴夸大差异；对数轴必须标注。
- 输出至少 300 dpi PNG，并保留 PDF/SVG；MATLAB/Origin 同时保留可编辑工程。
- 图、表、正文中的数值和单位必须由同一次运行生成。
