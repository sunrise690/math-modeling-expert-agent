# Model Route Candidates

Routes are selected from generic model cards according to task structure, constraints, and data support.

## Q1_baseline_empirical

| Item | Content |
| --- | --- |
| Route family | baseline_empirical |
| Route name | Transparent baseline |
| Suitable role | baseline |
| Applicable reason | Always included as a transparent comparator. |
| Mathematical object | simple rule, mean/median benchmark, or direct feasible heuristic |
| Inputs | M1/FY1 初始位置, 导弹速度 300 m/s, FY1 速度 120 m/s 且朝原点, 投放时刻 1.5 s, 引信延时 3.6 s, 云团半径/寿命/下沉速度, 圆柱目标几何 |
| Outputs | 中心视线口径遮蔽区间与时长, 完整圆柱口径遮蔽区间与时长, 边界残差与口径敏感性 |
| Decision/state variables | not central |
| Objective or rule | Use the simplest reproducible rule that answers the subquestion and exposes the value of added complexity. |
| Constraints or assumptions | 云团只在起爆后 20 s 内有效; 视线为导弹到目标的有限线段而非无限直线 |
| Validation plan | compare against main route; check residual or feasibility baseline |
| Recommended figures | baseline comparison; data profile |
| Failure modes | too simple for nonlinear or constrained structure; weak decision value |
| Model cards | simulation, differential_equation, sensitivity_analysis |

## Q1_simulation_scenario

| Item | Content |
| --- | --- |
| Route family | simulation_scenario |
| Route name | Scenario or stochastic simulation |
| Suitable role | main |
| Applicable reason | Selected because it matches confirmed task structure, available data, or decision requirements. |
| Mathematical object | random process or repeated-run simulator |
| Inputs | M1/FY1 初始位置, 导弹速度 300 m/s, FY1 速度 120 m/s 且朝原点, 投放时刻 1.5 s, 引信延时 3.6 s, 云团半径/寿命/下沉速度, 圆柱目标几何 |
| Outputs | 中心视线口径遮蔽区间与时长, 完整圆柱口径遮蔽区间与时长, 边界残差与口径敏感性 |
| Decision/state variables | state variables from the statement |
| Objective or rule | Propagate uncertainty through repeated scenarios and report intervals. |
| Constraints or assumptions | 云团只在起爆后 20 s 内有效; 视线为导弹到目标的有限线段而非无限直线 |
| Validation plan | repeated-run interval; convergence check; extreme scenario response |
| Recommended figures | scenario distribution; convergence curve; sensitivity band |
| Failure modes | unsupported distribution assumptions; too few replications; hidden parameter sensitivity |
| Model cards | simulation, differential_equation, sensitivity_analysis |

## Q1_hybrid_uncertainty_decision

| Item | Content |
| --- | --- |
| Route family | hybrid_uncertainty_decision |
| Route name | Prediction-to-decision with uncertainty |
| Suitable role | auxiliary |
| Applicable reason | Selected because it matches confirmed task structure, available data, or decision requirements. |
| Mathematical object | validated predictor plus decision rule under uncertainty |
| Inputs | M1/FY1 初始位置, 导弹速度 300 m/s, FY1 速度 120 m/s 且朝原点, 投放时刻 1.5 s, 引信延时 3.6 s, 云团半径/寿命/下沉速度, 圆柱目标几何 |
| Outputs | 中心视线口径遮蔽区间与时长, 完整圆柱口径遮蔽区间与时长, 边界残差与口径敏感性 |
| Decision/state variables | not central |
| Objective or rule | Use validated estimates as inputs to a decision or feasibility rule, with uncertainty propagation. |
| Constraints or assumptions | 云团只在起爆后 20 s 内有效; 视线为导弹到目标的有限线段而非无限直线 |
| Validation plan | baseline comparison; uncertainty propagation; decision sensitivity |
| Recommended figures | decision sensitivity; uncertainty interval; baseline vs final decision |
| Failure modes | prediction uncertainty ignored; decision thresholds unsupported; hard to communicate if not modular |
| Model cards | simulation, differential_equation, uncertainty_quantification, sensitivity_analysis |

## Q1_mechanism_state

| Item | Content |
| --- | --- |
| Route family | mechanism_state |
| Route name | State or mechanism model |
| Suitable role | auxiliary |
| Applicable reason | Selected because it matches confirmed task structure, available data, or decision requirements. |
| Mathematical object | state variables and transition or differential relations |
| Inputs | M1/FY1 初始位置, 导弹速度 300 m/s, FY1 速度 120 m/s 且朝原点, 投放时刻 1.5 s, 引信延时 3.6 s, 云团半径/寿命/下沉速度, 圆柱目标几何 |
| Outputs | 中心视线口径遮蔽区间与时长, 完整圆柱口径遮蔽区间与时长, 边界残差与口径敏感性 |
| Decision/state variables | state variables from the statement |
| Objective or rule | Represent system evolution with interpretable state equations and parameter checks. |
| Constraints or assumptions | 云团只在起爆后 20 s 内有效; 视线为导弹到目标的有限线段而非无限直线 |
| Validation plan | state trajectory check; parameter meaning; stability or conservation check |
| Recommended figures | state trajectory; parameter sensitivity; mechanism diagram |
| Failure modes | parameters not identifiable; mechanism oversimplified; state data unavailable |
| Model cards | simulation, differential_equation, sensitivity_analysis |

## Q2_baseline_empirical

| Item | Content |
| --- | --- |
| Route family | baseline_empirical |
| Route name | Transparent baseline |
| Suitable role | baseline |
| Applicable reason | Always included as a transparent comparator. |
| Mathematical object | simple rule, mean/median benchmark, or direct feasible heuristic |
| Inputs | Q1 的共享运动学与几何参数, FY1 速度范围 70–140 m/s |
| Outputs | 航向角 (deg), 速度 (m/s), 投放时刻/点, 起爆时刻/点, 有效区间与时长, 可行性和边界残差 |
| Decision/state variables | 航向角 theta, 速度 v, 投放时刻 tr, 引信延时 tau |
| Objective or rule | Use the simplest reproducible rule that answers the subquestion and exposes the value of added complexity. |
| Constraints or assumptions | 70<=v<=140; tr>=0; tau>=0; 起爆高度>=0; 起爆早于 M1 到达原点; 航向和速度选定后不变 |
| Validation plan | compare against main route; check residual or feasibility baseline |
| Recommended figures | baseline comparison; data profile |
| Failure modes | too simple for nonlinear or constrained structure; weak decision value |
| Model cards | optimization, simulation, sensitivity_analysis |

## Q2_mathematical_programming

| Item | Content |
| --- | --- |
| Route family | mathematical_programming |
| Route name | Objective-constrained decision model |
| Suitable role | main |
| Applicable reason | Selected because it matches confirmed task structure, available data, or decision requirements. |
| Mathematical object | decision vector x, objective F(x), constraints C(x) <= 0 |
| Inputs | Q1 的共享运动学与几何参数, FY1 速度范围 70–140 m/s |
| Outputs | 航向角 (deg), 速度 (m/s), 投放时刻/点, 起爆时刻/点, 有效区间与时长, 可行性和边界残差 |
| Decision/state variables | 航向角 theta, 速度 v, 投放时刻 tr, 引信延时 tau |
| Objective or rule | Optimize the objective while reporting feasibility and sensitivity to constraints. |
| Constraints or assumptions | 70<=v<=140; tr>=0; tau>=0; 起爆高度>=0; 起爆早于 M1 到达原点; 航向和速度选定后不变 |
| Validation plan | constraint satisfaction; objective value; scenario sensitivity; baseline comparison |
| Recommended figures | constraint status; feasible region; scenario comparison |
| Failure modes | infeasible constraints; poorly justified objective weights; unstable optimum |
| Model cards | optimization, simulation, sensitivity_analysis |

## Q2_hybrid_uncertainty_decision

| Item | Content |
| --- | --- |
| Route family | hybrid_uncertainty_decision |
| Route name | Prediction-to-decision with uncertainty |
| Suitable role | auxiliary |
| Applicable reason | Selected because it matches confirmed task structure, available data, or decision requirements. |
| Mathematical object | validated predictor plus decision rule under uncertainty |
| Inputs | Q1 的共享运动学与几何参数, FY1 速度范围 70–140 m/s |
| Outputs | 航向角 (deg), 速度 (m/s), 投放时刻/点, 起爆时刻/点, 有效区间与时长, 可行性和边界残差 |
| Decision/state variables | 航向角 theta, 速度 v, 投放时刻 tr, 引信延时 tau |
| Objective or rule | Use validated estimates as inputs to a decision or feasibility rule, with uncertainty propagation. |
| Constraints or assumptions | 70<=v<=140; tr>=0; tau>=0; 起爆高度>=0; 起爆早于 M1 到达原点; 航向和速度选定后不变 |
| Validation plan | baseline comparison; uncertainty propagation; decision sensitivity |
| Recommended figures | decision sensitivity; uncertainty interval; baseline vs final decision |
| Failure modes | prediction uncertainty ignored; decision thresholds unsupported; hard to communicate if not modular |
| Model cards | optimization, simulation, uncertainty_quantification, sensitivity_analysis |

## Q2_simulation_scenario

| Item | Content |
| --- | --- |
| Route family | simulation_scenario |
| Route name | Scenario or stochastic simulation |
| Suitable role | auxiliary |
| Applicable reason | Selected because it matches confirmed task structure, available data, or decision requirements. |
| Mathematical object | random process or repeated-run simulator |
| Inputs | Q1 的共享运动学与几何参数, FY1 速度范围 70–140 m/s |
| Outputs | 航向角 (deg), 速度 (m/s), 投放时刻/点, 起爆时刻/点, 有效区间与时长, 可行性和边界残差 |
| Decision/state variables | 航向角 theta, 速度 v, 投放时刻 tr, 引信延时 tau, state variables from the statement |
| Objective or rule | Propagate uncertainty through repeated scenarios and report intervals. |
| Constraints or assumptions | 70<=v<=140; tr>=0; tau>=0; 起爆高度>=0; 起爆早于 M1 到达原点; 航向和速度选定后不变 |
| Validation plan | repeated-run interval; convergence check; extreme scenario response |
| Recommended figures | scenario distribution; convergence curve; sensitivity band |
| Failure modes | unsupported distribution assumptions; too few replications; hidden parameter sensitivity |
| Model cards | optimization, simulation, sensitivity_analysis |

## Q3_baseline_empirical

| Item | Content |
| --- | --- |
| Route family | baseline_empirical |
| Route name | Transparent baseline |
| Suitable role | baseline |
| Applicable reason | Always included as a transparent comparator. |
| Mathematical object | simple rule, mean/median benchmark, or direct feasible heuristic |
| Inputs | Q2 的共享运动学/几何参数, 同一无人机三枚弹, 相邻投放至少间隔 1 s, result1.xlsx 字段 |
| Outputs | 同一航向角与速度, 三枚弹投放点与起爆点, 各弹对 M1 的有效时长, 总并集时长, result1.xlsx |
| Decision/state variables | theta, v, tr_1..tr_3, tau_1..tau_3 |
| Objective or rule | Use the simplest reproducible rule that answers the subquestion and exposes the value of added complexity. |
| Constraints or assumptions | 70<=v<=140; tr_(k+1)-tr_k>=1; tau_k>=0; 各起爆点 z>=0; 各起爆早于 M1 到达原点; 同机 theta/v 固定 |
| Validation plan | compare against main route; check residual or feasibility baseline |
| Recommended figures | baseline comparison; data profile |
| Failure modes | too simple for nonlinear or constrained structure; weak decision value |
| Model cards | optimization, simulation, sensitivity_analysis |

## Q3_mathematical_programming

| Item | Content |
| --- | --- |
| Route family | mathematical_programming |
| Route name | Objective-constrained decision model |
| Suitable role | main |
| Applicable reason | Selected because it matches confirmed task structure, available data, or decision requirements. |
| Mathematical object | decision vector x, objective F(x), constraints C(x) <= 0 |
| Inputs | Q2 的共享运动学/几何参数, 同一无人机三枚弹, 相邻投放至少间隔 1 s, result1.xlsx 字段 |
| Outputs | 同一航向角与速度, 三枚弹投放点与起爆点, 各弹对 M1 的有效时长, 总并集时长, result1.xlsx |
| Decision/state variables | theta, v, tr_1..tr_3, tau_1..tau_3 |
| Objective or rule | Optimize the objective while reporting feasibility and sensitivity to constraints. |
| Constraints or assumptions | 70<=v<=140; tr_(k+1)-tr_k>=1; tau_k>=0; 各起爆点 z>=0; 各起爆早于 M1 到达原点; 同机 theta/v 固定 |
| Validation plan | constraint satisfaction; objective value; scenario sensitivity; baseline comparison |
| Recommended figures | constraint status; feasible region; scenario comparison |
| Failure modes | infeasible constraints; poorly justified objective weights; unstable optimum |
| Model cards | optimization, simulation, sensitivity_analysis |

## Q3_hybrid_uncertainty_decision

| Item | Content |
| --- | --- |
| Route family | hybrid_uncertainty_decision |
| Route name | Prediction-to-decision with uncertainty |
| Suitable role | auxiliary |
| Applicable reason | Selected because it matches confirmed task structure, available data, or decision requirements. |
| Mathematical object | validated predictor plus decision rule under uncertainty |
| Inputs | Q2 的共享运动学/几何参数, 同一无人机三枚弹, 相邻投放至少间隔 1 s, result1.xlsx 字段 |
| Outputs | 同一航向角与速度, 三枚弹投放点与起爆点, 各弹对 M1 的有效时长, 总并集时长, result1.xlsx |
| Decision/state variables | theta, v, tr_1..tr_3, tau_1..tau_3 |
| Objective or rule | Use validated estimates as inputs to a decision or feasibility rule, with uncertainty propagation. |
| Constraints or assumptions | 70<=v<=140; tr_(k+1)-tr_k>=1; tau_k>=0; 各起爆点 z>=0; 各起爆早于 M1 到达原点; 同机 theta/v 固定 |
| Validation plan | baseline comparison; uncertainty propagation; decision sensitivity |
| Recommended figures | decision sensitivity; uncertainty interval; baseline vs final decision |
| Failure modes | prediction uncertainty ignored; decision thresholds unsupported; hard to communicate if not modular |
| Model cards | optimization, simulation, uncertainty_quantification, sensitivity_analysis |

## Q3_simulation_scenario

| Item | Content |
| --- | --- |
| Route family | simulation_scenario |
| Route name | Scenario or stochastic simulation |
| Suitable role | auxiliary |
| Applicable reason | Selected because it matches confirmed task structure, available data, or decision requirements. |
| Mathematical object | random process or repeated-run simulator |
| Inputs | Q2 的共享运动学/几何参数, 同一无人机三枚弹, 相邻投放至少间隔 1 s, result1.xlsx 字段 |
| Outputs | 同一航向角与速度, 三枚弹投放点与起爆点, 各弹对 M1 的有效时长, 总并集时长, result1.xlsx |
| Decision/state variables | theta, v, tr_1..tr_3, tau_1..tau_3, state variables from the statement |
| Objective or rule | Propagate uncertainty through repeated scenarios and report intervals. |
| Constraints or assumptions | 70<=v<=140; tr_(k+1)-tr_k>=1; tau_k>=0; 各起爆点 z>=0; 各起爆早于 M1 到达原点; 同机 theta/v 固定 |
| Validation plan | repeated-run interval; convergence check; extreme scenario response |
| Recommended figures | scenario distribution; convergence curve; sensitivity band |
| Failure modes | unsupported distribution assumptions; too few replications; hidden parameter sensitivity |
| Model cards | optimization, simulation, sensitivity_analysis |

## Q4_baseline_empirical

| Item | Content |
| --- | --- |
| Route family | baseline_empirical |
| Route name | Transparent baseline |
| Suitable role | baseline |
| Applicable reason | Always included as a transparent comparator. |
| Mathematical object | simple rule, mean/median benchmark, or direct feasible heuristic |
| Inputs | FY1–FY3 初始位置, 共享运动学/几何参数, result2.xlsx 字段 |
| Outputs | 每机航向与速度, 每弹投放/起爆点, 单弹时长与总并集时长, result2.xlsx |
| Decision/state variables | 每机 theta_i, 每机 v_i, 每机 tr_i, 每机 tau_i |
| Objective or rule | Use the simplest reproducible rule that answers the subquestion and exposes the value of added complexity. |
| Constraints or assumptions | 每机 70<=v_i<=140; tr_i,tau_i>=0; 起爆高度>=0; 起爆早于 M1 到达原点 |
| Validation plan | compare against main route; check residual or feasibility baseline |
| Recommended figures | baseline comparison; data profile |
| Failure modes | too simple for nonlinear or constrained structure; weak decision value |
| Model cards | optimization, simulation, sensitivity_analysis |

## Q4_mathematical_programming

| Item | Content |
| --- | --- |
| Route family | mathematical_programming |
| Route name | Objective-constrained decision model |
| Suitable role | main |
| Applicable reason | Selected because it matches confirmed task structure, available data, or decision requirements. |
| Mathematical object | decision vector x, objective F(x), constraints C(x) <= 0 |
| Inputs | FY1–FY3 初始位置, 共享运动学/几何参数, result2.xlsx 字段 |
| Outputs | 每机航向与速度, 每弹投放/起爆点, 单弹时长与总并集时长, result2.xlsx |
| Decision/state variables | 每机 theta_i, 每机 v_i, 每机 tr_i, 每机 tau_i |
| Objective or rule | Optimize the objective while reporting feasibility and sensitivity to constraints. |
| Constraints or assumptions | 每机 70<=v_i<=140; tr_i,tau_i>=0; 起爆高度>=0; 起爆早于 M1 到达原点 |
| Validation plan | constraint satisfaction; objective value; scenario sensitivity; baseline comparison |
| Recommended figures | constraint status; feasible region; scenario comparison |
| Failure modes | infeasible constraints; poorly justified objective weights; unstable optimum |
| Model cards | optimization, simulation, sensitivity_analysis |

## Q4_hybrid_uncertainty_decision

| Item | Content |
| --- | --- |
| Route family | hybrid_uncertainty_decision |
| Route name | Prediction-to-decision with uncertainty |
| Suitable role | auxiliary |
| Applicable reason | Selected because it matches confirmed task structure, available data, or decision requirements. |
| Mathematical object | validated predictor plus decision rule under uncertainty |
| Inputs | FY1–FY3 初始位置, 共享运动学/几何参数, result2.xlsx 字段 |
| Outputs | 每机航向与速度, 每弹投放/起爆点, 单弹时长与总并集时长, result2.xlsx |
| Decision/state variables | 每机 theta_i, 每机 v_i, 每机 tr_i, 每机 tau_i |
| Objective or rule | Use validated estimates as inputs to a decision or feasibility rule, with uncertainty propagation. |
| Constraints or assumptions | 每机 70<=v_i<=140; tr_i,tau_i>=0; 起爆高度>=0; 起爆早于 M1 到达原点 |
| Validation plan | baseline comparison; uncertainty propagation; decision sensitivity |
| Recommended figures | decision sensitivity; uncertainty interval; baseline vs final decision |
| Failure modes | prediction uncertainty ignored; decision thresholds unsupported; hard to communicate if not modular |
| Model cards | optimization, simulation, uncertainty_quantification, sensitivity_analysis |

## Q4_simulation_scenario

| Item | Content |
| --- | --- |
| Route family | simulation_scenario |
| Route name | Scenario or stochastic simulation |
| Suitable role | auxiliary |
| Applicable reason | Selected because it matches confirmed task structure, available data, or decision requirements. |
| Mathematical object | random process or repeated-run simulator |
| Inputs | FY1–FY3 初始位置, 共享运动学/几何参数, result2.xlsx 字段 |
| Outputs | 每机航向与速度, 每弹投放/起爆点, 单弹时长与总并集时长, result2.xlsx |
| Decision/state variables | 每机 theta_i, 每机 v_i, 每机 tr_i, 每机 tau_i, state variables from the statement |
| Objective or rule | Propagate uncertainty through repeated scenarios and report intervals. |
| Constraints or assumptions | 每机 70<=v_i<=140; tr_i,tau_i>=0; 起爆高度>=0; 起爆早于 M1 到达原点 |
| Validation plan | repeated-run interval; convergence check; extreme scenario response |
| Recommended figures | scenario distribution; convergence curve; sensitivity band |
| Failure modes | unsupported distribution assumptions; too few replications; hidden parameter sensitivity |
| Model cards | optimization, simulation, sensitivity_analysis |

## Q5_baseline_empirical

| Item | Content |
| --- | --- |
| Route family | baseline_empirical |
| Route name | Transparent baseline |
| Suitable role | baseline |
| Applicable reason | Always included as a transparent comparator. |
| Mathematical object | simple rule, mean/median benchmark, or direct feasible heuristic |
| Inputs | M1–M3/FY1–FY5 初始位置, 每机至多 3 枚, 相邻投放至少 1 s, result3.xlsx 字段 |
| Outputs | 每机固定航向与速度, 至多 15 枚弹的投放/起爆点, 每弹干扰导弹编号与时长, 各导弹并集时长, result3.xlsx |
| Decision/state variables | 每机 theta_i,v_i, 每枚弹 tr_ik,tau_ik, 弹到导弹的离散指派 a_ikj, 是否使用该弹 y_ik |
| Objective or rule | Use the simplest reproducible rule that answers the subquestion and exposes the value of added complexity. |
| Constraints or assumptions | 每机至多 3 枚; 同机投放间隔>=1 s; 同机 theta_i/v_i 固定; 每个已用弹指派至一枚导弹; 70<=v_i<=140; 起爆高度>=0; 起爆在对应导弹到达原点前 |
| Validation plan | compare against main route; check residual or feasibility baseline |
| Recommended figures | baseline comparison; data profile |
| Failure modes | too simple for nonlinear or constrained structure; weak decision value |
| Model cards | optimization, graph_network, simulation, sensitivity_analysis |

## Q5_mathematical_programming

| Item | Content |
| --- | --- |
| Route family | mathematical_programming |
| Route name | Objective-constrained decision model |
| Suitable role | main |
| Applicable reason | Selected because it matches confirmed task structure, available data, or decision requirements. |
| Mathematical object | decision vector x, objective F(x), constraints C(x) <= 0 |
| Inputs | M1–M3/FY1–FY5 初始位置, 每机至多 3 枚, 相邻投放至少 1 s, result3.xlsx 字段 |
| Outputs | 每机固定航向与速度, 至多 15 枚弹的投放/起爆点, 每弹干扰导弹编号与时长, 各导弹并集时长, result3.xlsx |
| Decision/state variables | 每机 theta_i,v_i, 每枚弹 tr_ik,tau_ik, 弹到导弹的离散指派 a_ikj, 是否使用该弹 y_ik |
| Objective or rule | Optimize the objective while reporting feasibility and sensitivity to constraints. |
| Constraints or assumptions | 每机至多 3 枚; 同机投放间隔>=1 s; 同机 theta_i/v_i 固定; 每个已用弹指派至一枚导弹; 70<=v_i<=140; 起爆高度>=0; 起爆在对应导弹到达原点前 |
| Validation plan | constraint satisfaction; objective value; scenario sensitivity; baseline comparison |
| Recommended figures | constraint status; feasible region; scenario comparison |
| Failure modes | infeasible constraints; poorly justified objective weights; unstable optimum |
| Model cards | optimization, graph_network, simulation, sensitivity_analysis |

## Q5_hybrid_uncertainty_decision

| Item | Content |
| --- | --- |
| Route family | hybrid_uncertainty_decision |
| Route name | Prediction-to-decision with uncertainty |
| Suitable role | auxiliary |
| Applicable reason | Selected because it matches confirmed task structure, available data, or decision requirements. |
| Mathematical object | validated predictor plus decision rule under uncertainty |
| Inputs | M1–M3/FY1–FY5 初始位置, 每机至多 3 枚, 相邻投放至少 1 s, result3.xlsx 字段 |
| Outputs | 每机固定航向与速度, 至多 15 枚弹的投放/起爆点, 每弹干扰导弹编号与时长, 各导弹并集时长, result3.xlsx |
| Decision/state variables | 每机 theta_i,v_i, 每枚弹 tr_ik,tau_ik, 弹到导弹的离散指派 a_ikj, 是否使用该弹 y_ik |
| Objective or rule | Use validated estimates as inputs to a decision or feasibility rule, with uncertainty propagation. |
| Constraints or assumptions | 每机至多 3 枚; 同机投放间隔>=1 s; 同机 theta_i/v_i 固定; 每个已用弹指派至一枚导弹; 70<=v_i<=140; 起爆高度>=0; 起爆在对应导弹到达原点前 |
| Validation plan | baseline comparison; uncertainty propagation; decision sensitivity |
| Recommended figures | decision sensitivity; uncertainty interval; baseline vs final decision |
| Failure modes | prediction uncertainty ignored; decision thresholds unsupported; hard to communicate if not modular |
| Model cards | optimization, graph_network, simulation, uncertainty_quantification, sensitivity_analysis |

## Q5_graph_path_flow

| Item | Content |
| --- | --- |
| Route family | graph_path_flow |
| Route name | Network path or flow model |
| Suitable role | main |
| Applicable reason | Selected because it matches confirmed task structure, available data, or decision requirements. |
| Mathematical object | graph G=(V,E), edge weights/capacities, path or flow variables |
| Inputs | M1–M3/FY1–FY5 初始位置, 每机至多 3 枚, 相邻投放至少 1 s, result3.xlsx 字段 |
| Outputs | 每机固定航向与速度, 至多 15 枚弹的投放/起爆点, 每弹干扰导弹编号与时长, 各导弹并集时长, result3.xlsx |
| Decision/state variables | 每机 theta_i,v_i, 每枚弹 tr_ik,tau_ik, 弹到导弹的离散指派 a_ikj, 是否使用该弹 y_ik |
| Objective or rule | Solve path, connectivity, bottleneck, or flow decisions under network constraints. |
| Constraints or assumptions | 每机至多 3 枚; 同机投放间隔>=1 s; 同机 theta_i/v_i 固定; 每个已用弹指派至一枚导弹; 70<=v_i<=140; 起爆高度>=0; 起爆在对应导弹到达原点前 |
| Validation plan | path or flow feasibility; bottleneck analysis; network robustness |
| Recommended figures | network solution; bottleneck chart; route comparison |
| Failure modes | missing adjacency information; edge weights not justified; network changes over time |
| Model cards | optimization, graph_network, simulation, sensitivity_analysis |

## Q5_simulation_scenario

| Item | Content |
| --- | --- |
| Route family | simulation_scenario |
| Route name | Scenario or stochastic simulation |
| Suitable role | auxiliary |
| Applicable reason | Selected because it matches confirmed task structure, available data, or decision requirements. |
| Mathematical object | random process or repeated-run simulator |
| Inputs | M1–M3/FY1–FY5 初始位置, 每机至多 3 枚, 相邻投放至少 1 s, result3.xlsx 字段 |
| Outputs | 每机固定航向与速度, 至多 15 枚弹的投放/起爆点, 每弹干扰导弹编号与时长, 各导弹并集时长, result3.xlsx |
| Decision/state variables | 每机 theta_i,v_i, 每枚弹 tr_ik,tau_ik, 弹到导弹的离散指派 a_ikj, 是否使用该弹 y_ik, state variables from the statement |
| Objective or rule | Propagate uncertainty through repeated scenarios and report intervals. |
| Constraints or assumptions | 每机至多 3 枚; 同机投放间隔>=1 s; 同机 theta_i/v_i 固定; 每个已用弹指派至一枚导弹; 70<=v_i<=140; 起爆高度>=0; 起爆在对应导弹到达原点前 |
| Validation plan | repeated-run interval; convergence check; extreme scenario response |
| Recommended figures | scenario distribution; convergence curve; sensitivity band |
| Failure modes | unsupported distribution assumptions; too few replications; hidden parameter sensitivity |
| Model cards | optimization, graph_network, simulation, sensitivity_analysis |

## Rejected Route Families

| Subquestion | Route family | Rejection reason |
| --- | --- | --- |
| Q1 | interpretable_regression | not selected because the confirmed task structure does not require this mathematical object |
| Q1 | time_series_forecast | not selected because the confirmed task structure does not require this mathematical object |
| Q1 | classification_threshold | not selected because the confirmed task structure does not require this mathematical object |
| Q1 | mathematical_programming | not selected because the confirmed task structure does not require this mathematical object |
| Q1 | evaluation_index | not selected because the confirmed task structure does not require this mathematical object |
| Q1 | grouping_structure | not selected because the confirmed task structure does not require this mathematical object |
| Q1 | graph_path_flow | not selected because the confirmed task structure does not require this mathematical object |
| Q2 | interpretable_regression | not selected because the confirmed task structure does not require this mathematical object |
| Q2 | time_series_forecast | not selected because the confirmed task structure does not require this mathematical object |
| Q2 | classification_threshold | not selected because the confirmed task structure does not require this mathematical object |
| Q2 | evaluation_index | not selected because the confirmed task structure does not require this mathematical object |
| Q2 | grouping_structure | not selected because the confirmed task structure does not require this mathematical object |
| Q2 | mechanism_state | not selected because the confirmed task structure does not require this mathematical object |
| Q2 | graph_path_flow | not selected because the confirmed task structure does not require this mathematical object |
| Q3 | interpretable_regression | not selected because the confirmed task structure does not require this mathematical object |
| Q3 | time_series_forecast | not selected because the confirmed task structure does not require this mathematical object |
| Q3 | classification_threshold | not selected because the confirmed task structure does not require this mathematical object |
| Q3 | evaluation_index | not selected because the confirmed task structure does not require this mathematical object |
| Q3 | grouping_structure | not selected because the confirmed task structure does not require this mathematical object |
| Q3 | mechanism_state | not selected because the confirmed task structure does not require this mathematical object |
| Q3 | graph_path_flow | not selected because the confirmed task structure does not require this mathematical object |
| Q4 | interpretable_regression | not selected because the confirmed task structure does not require this mathematical object |
| Q4 | time_series_forecast | not selected because the confirmed task structure does not require this mathematical object |
| Q4 | classification_threshold | not selected because the confirmed task structure does not require this mathematical object |
| Q4 | evaluation_index | not selected because the confirmed task structure does not require this mathematical object |
| Q4 | grouping_structure | not selected because the confirmed task structure does not require this mathematical object |
| Q4 | mechanism_state | not selected because the confirmed task structure does not require this mathematical object |
| Q4 | graph_path_flow | not selected because the confirmed task structure does not require this mathematical object |
| Q5 | interpretable_regression | not selected because the confirmed task structure does not require this mathematical object |
| Q5 | time_series_forecast | not selected because the confirmed task structure does not require this mathematical object |
| Q5 | classification_threshold | not selected because the confirmed task structure does not require this mathematical object |
| Q5 | evaluation_index | not selected because the confirmed task structure does not require this mathematical object |
| Q5 | grouping_structure | not selected because the confirmed task structure does not require this mathematical object |
| Q5 | mechanism_state | not selected because the confirmed task structure does not require this mathematical object |
