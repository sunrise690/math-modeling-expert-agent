function render_q5_figures()
%RENDER_Q5_FIGURES Render the three Q5 evidence figures in MATLAB.
%
% The script reads the independently reproduced Q5 result directly from
% validation/q3_q5_independent.json.  It intentionally avoids bars and
% Gantt strips: time coverage is encoded by entry/exit event nodes, event
% arcs, an event-driven coverage-count staircase, and explicit gap arrows.

scriptDir = fileparts(mfilename('fullpath'));
projectDir = fileparts(fileparts(scriptDir));
jsonPath = fullfile(projectDir, 'validation', 'q3_q5_independent.json');
outDir = fullfile(projectDir, 'figures');

assert(isfile(jsonPath), 'Validation data not found: %s', jsonPath);
if ~isfolder(outDir)
    mkdir(outDir);
end

payload = jsondecode(fileread(jsonPath));
q5 = payload.results.Q5;
fullAudit = payload.full_cylinder_secondary_audit.Q5;
plans = q5.plans;
assert(numel(plans) == 15, 'Q5 figure expects 15 selected smoke bombs.');

C = editorialPalette();
fontName = chooseChineseFont();
shotIndex = computeShotIndex(plans);

renderXYStrategy(plans, shotIndex, outDir, C, fontName);
renderCoverageEvents(q5, plans, shotIndex, outDir, C, fontName);
renderPairedAudit(q5, fullAudit, outDir, C, fontName);

fprintf('Rendered Q5 MATLAB figures in %s\n', outDir);
end


function renderXYStrategy(plans, shotIndex, outDir, C, fontName)
% Global geometry on a true metric scale plus three event-level facets.
fig = figure('Visible', 'off', 'Color', C.paper, 'Renderer', 'painters', ...
    'Units', 'inches', 'Position', [0.5, 0.5, 6.20, 4.75], ...
    'PaperPositionMode', 'auto');

axGlobal = axes(fig, 'Position', [0.085, 0.500, 0.880, 0.420]);
axLocal = [ ...
    axes(fig, 'Position', [0.075, 0.105, 0.275, 0.270]), ...
    axes(fig, 'Position', [0.382, 0.105, 0.275, 0.270]), ...
    axes(fig, 'Position', [0.689, 0.105, 0.275, 0.270])];

droneNames = {'FY1', 'FY2', 'FY3', 'FY4', 'FY5'};
lineStyles = {'-', '--', '-.', ':', '-'};
startMarkers = {'o', 's', '^', 'd', 'v'};
missileStyles = {'--', '-.', ':'};
hold(axGlobal, 'on');

% Incoming missile directions from the official initial positions to the
% false target.  The coordinates are shown in kilometres.
missileStarts = [20.0, 0.0; 19.0, 0.6; 18.0, -0.6];
for k = 1:3
    plot(axGlobal, [missileStarts(k, 1), 0], [missileStarts(k, 2), 0], ...
        missileStyles{k}, 'Color', C.missile(k, :), 'LineWidth', 1.00);
    plot(axGlobal, missileStarts(k, 1), missileStarts(k, 2), '<', ...
        'MarkerSize', 5.2, 'MarkerFaceColor', C.paper, ...
        'MarkerEdgeColor', C.missile(k, :), 'LineWidth', 0.95);
    text(axGlobal, missileStarts(k, 1) - 0.18, missileStarts(k, 2) + 0.23, ...
        sprintf('M%d', k), 'HorizontalAlignment', 'center', ...
        'FontName', fontName, 'FontSize', 7.2, 'FontWeight', 'bold', ...
        'Color', C.missile(k, :));
end

for d = 1:numel(droneNames)
    drone = droneNames{d};
    idx = find(strcmp({plans.drone_id}, drone));
    [~, order] = sort([plans(idx).explosion_time]);
    idx = idx(order);
    firstPlan = plans(idx(1));
    startXY = reshape(firstPlan.release_position(1:2), 1, 2) - ...
        firstPlan.speed * firstPlan.release_time * ...
        [cosd(firstPlan.heading_deg), sind(firstPlan.heading_deg)];
    lastPlan = plans(idx(end));
    endXY = reshape(lastPlan.explosion_position(1:2), 1, 2);
    startKm = startXY / 1000;
    endKm = endXY / 1000;
    color = C.drone(d, :);

    plot(axGlobal, [startKm(1), endKm(1)], [startKm(2), endKm(2)], ...
        lineStyles{d}, 'Color', color, 'LineWidth', 1.70);
    direction = endKm - startKm;
    direction = direction / max(norm(direction), eps);
    arrowPoint = endKm - 0.12 * direction;
    plot(axGlobal, arrowPoint(1), arrowPoint(2), '>', ...
        'MarkerSize', 5.5, 'MarkerFaceColor', color, ...
        'MarkerEdgeColor', C.paper, 'LineWidth', 0.55);

    releaseXY = zeros(numel(idx), 2);
    explosionXY = zeros(numel(idx), 2);
    for k = 1:numel(idx)
        releaseXY(k, :) = reshape(plans(idx(k)).release_position(1:2), 1, 2) / 1000;
        explosionXY(k, :) = reshape(plans(idx(k)).explosion_position(1:2), 1, 2) / 1000;
    end
    plot(axGlobal, releaseXY(:, 1), releaseXY(:, 2), 'd', ...
        'LineStyle', 'none', 'MarkerSize', 4.4, ...
        'MarkerFaceColor', C.paper, 'MarkerEdgeColor', color, 'LineWidth', 0.85);
    plot(axGlobal, explosionXY(:, 1), explosionXY(:, 2), 'o', ...
        'LineStyle', 'none', 'MarkerSize', 4.4, ...
        'MarkerFaceColor', color, 'MarkerEdgeColor', C.paper, 'LineWidth', 0.55);
    plot(axGlobal, startKm(1), startKm(2), startMarkers{d}, 'MarkerSize', 6.5, ...
        'MarkerFaceColor', color, 'MarkerEdgeColor', C.paper, 'LineWidth', 0.60);

    if startKm(2) >= 0
        dy = 0.26;
        va = 'bottom';
    else
        dy = -0.27;
        va = 'top';
    end
    text(axGlobal, startKm(1), startKm(2) + dy, drone, ...
        'HorizontalAlignment', 'center', 'VerticalAlignment', va, ...
        'FontName', fontName, 'FontSize', 7.4, 'FontWeight', 'bold', ...
        'Color', C.ink);
end

plot(axGlobal, 0, 0, 'x', 'MarkerSize', 6.4, 'Color', C.ink, 'LineWidth', 1.25);
plot(axGlobal, 0, 0.2, 'o', 'MarkerSize', 5.8, 'MarkerFaceColor', C.paper, ...
    'MarkerEdgeColor', C.ink, 'LineWidth', 1.0);
text(axGlobal, 0.34, -0.16, '假目标', 'FontName', fontName, 'FontSize', 7.0, ...
    'Color', C.muted, 'Interpreter', 'none');
text(axGlobal, 0.34, 0.39, '真目标', 'FontName', fontName, 'FontSize', 7.0, ...
    'Color', C.muted, 'Interpreter', 'none');

% A quiet metric scale replaces a decorative legend box.
plot(axGlobal, [0.75, 2.75], [-3.02, -3.02], '-', 'Color', C.ink, 'LineWidth', 1.35);
plot(axGlobal, [0.75, 0.75], [-3.10, -2.94], '-', 'Color', C.ink, 'LineWidth', 0.85);
plot(axGlobal, [2.75, 2.75], [-3.10, -2.94], '-', 'Color', C.ink, 'LineWidth', 0.85);
text(axGlobal, 1.75, -2.81, '2 km', 'HorizontalAlignment', 'center', ...
    'FontName', fontName, 'FontSize', 7.0, 'Color', C.muted);

text(axGlobal, 0.010, 1.055, 'a', 'Units', 'normalized', ...
    'FontName', 'Arial', 'FontSize', 9.2, 'FontWeight', 'bold', 'Color', C.ink);
text(axGlobal, 0.990, 1.045, '全局真尺度航迹  ◇ 投放  ● 起爆', ...
    'Units', 'normalized', 'HorizontalAlignment', 'right', ...
    'FontName', fontName, 'FontSize', 7.5, 'FontWeight', 'bold', ...
    'Color', C.ink, 'Interpreter', 'none');

xlim(axGlobal, [-0.5, 20.5]);
ylim(axGlobal, [-3.35, 2.45]);
axis(axGlobal, 'equal');
xlabel(axGlobal, 'x / km', 'FontName', fontName, 'FontSize', 8.2, 'Color', C.ink);
ylabel(axGlobal, 'y / km', 'FontName', fontName, 'FontSize', 8.2, 'Color', C.ink);
styleAxis(axGlobal, C, fontName, true);
hold(axGlobal, 'off');

for m = 1:3
    drawLocalMissile(axLocal(m), plans, shotIndex, sprintf('M%d', m), ...
        C, fontName, char('b' + m - 1));
end

annotation(fig, 'textbox', [0.075, 0.012, 0.895, 0.035], ...
    'String', '局部图按航程分段展开（横坐标非连续）；颜色/线型/中点符号=无人机，数字=同机弹序', ...
    'HorizontalAlignment', 'right', 'VerticalAlignment', 'middle', ...
    'FontName', fontName, 'FontSize', 7.0, 'Color', C.muted, ...
    'Interpreter', 'none', 'EdgeColor', 'none', 'FitBoxToText', 'off');

exportFigure(fig, outDir, 'q5_xy_strategy', C.paper);
close(fig);
end


function drawLocalMissile(ax, plans, shotIndex, missile, C, fontName, panelLetter)
hold(ax, 'on');

% The three physical x windows are ordered by flight progress (far to near)
% and explicitly labelled as a segmented, non-continuous coordinate.
windows = [16.0, 18.2; 8.7, 12.5; 2.8, 4.5];
windowNames = {'16.0–18.2', '8.7–12.5', '2.8–4.5'};
segmentColors = [ ...
    mixColor(C.primary, C.paper, 0.025); ...
    C.panel; ...
    mixColor(C.secondary, C.paper, 0.025)];
for w = 1:3
    patch(ax, [w-1, w, w, w-1], [-1.10, -1.10, 1.82, 1.82], ...
        segmentColors(w, :), 'EdgeColor', 'none');
    plot(ax, [w-1 + 0.06, w - 0.06], [1.59, 1.59], '-', ...
        'Color', mixColor(C.ink, segmentColors(w, :), 0.20), 'LineWidth', 1.05);
    text(ax, w - 0.5, 1.71, windowNames{w}, ...
        'HorizontalAlignment', 'center', 'FontName', fontName, ...
        'FontSize', 7.0, 'Color', C.muted, 'Interpreter', 'none');
end
plot(ax, [1, 1], [-1.08, 1.82], ':', 'Color', C.grid, 'LineWidth', 0.65);
plot(ax, [2, 2], [-1.08, 1.82], ':', 'Color', C.grid, 'LineWidth', 0.65);
plot(ax, [0, 3], [0, 0], '-', 'Color', C.grid, 'LineWidth', 0.65);

idx = find(strcmp({plans.missile_id}, missile));
[~, order] = sort([plans(idx).explosion_time]);
idx = idx(order);
if strcmp(missile, 'M1')
    labelDy = [0.16, -0.19, 0.18, 0.23, -0.24, -0.19, 0.17];
    labelDx = [-0.02, 0.02, 0.02, 0.04, -0.04, 0.04, -0.02];
elseif strcmp(missile, 'M2')
    labelDy = [0.23, -0.20, -0.24, 0.18];
    labelDx = [0.03, -0.03, -0.03, 0.03];
else
    labelDy = [-0.25, 0.24, 0.17, 0.18];
    labelDx = [-0.04, 0.04, 0.04, 0.02];
end
droneStyles = {'-', '--', '-.', ':', '-'};
droneMarkers = {'o', 's', '^', 'd', 'v'};

for p = 1:numel(idx)
    planIndex = idx(p);
    plan = plans(planIndex);
    droneNumber = sscanf(plan.drone_id, 'FY%d');
    color = C.drone(droneNumber, :);
    releaseKm = reshape(plan.release_position(1:2), 1, 2) / 1000;
    explosionKm = reshape(plan.explosion_position(1:2), 1, 2) / 1000;
    xr = segmentedX(releaseKm(1), windows);
    xe = segmentedX(explosionKm(1), windows);
    assert(isfinite(xr) && isfinite(xe), 'Q5 local x coordinate is outside the declared windows.');

    plot(ax, [xr, xe], [releaseKm(2), explosionKm(2)], droneStyles{droneNumber}, ...
        'Color', color, 'LineWidth', 1.15);
    plot(ax, mean([xr, xe]), mean([releaseKm(2), explosionKm(2)]), ...
        droneMarkers{droneNumber}, 'MarkerSize', 3.7, ...
        'MarkerFaceColor', C.paper, 'MarkerEdgeColor', color, 'LineWidth', 0.75);
    plot(ax, xr, releaseKm(2), 'd', 'MarkerSize', 5.0, ...
        'MarkerFaceColor', C.paper, 'MarkerEdgeColor', color, 'LineWidth', 0.9);
    plot(ax, xe, explosionKm(2), 'o', 'MarkerSize', 5.5, ...
        'MarkerFaceColor', color, 'MarkerEdgeColor', C.paper, 'LineWidth', 0.6);

    label = sprintf('%d', shotIndex(planIndex));
    dx = labelDx(min(p, numel(labelDx)));
    dy = labelDy(min(p, numel(labelDy)));
    if dx >= 0
        ha = 'left';
    else
        ha = 'right';
    end
    plot(ax, [xe, xe + 0.75 * dx], [explosionKm(2), explosionKm(2) + 0.75 * dy], ...
        '-', 'Color', C.guideDark, 'LineWidth', 0.55);
    text(ax, xe + dx, explosionKm(2) + dy, label, ...
        'HorizontalAlignment', ha, 'VerticalAlignment', 'middle', ...
        'FontName', fontName, 'FontSize', 7.0, 'FontWeight', 'bold', 'Color', C.ink, ...
        'BackgroundColor', C.paper, 'Margin', 0.4, 'Interpreter', 'none');
end

text(ax, 0.01, 1.055, panelLetter, 'Units', 'normalized', ...
    'FontName', 'Arial', 'FontSize', 9.0, 'FontWeight', 'bold', 'Color', C.ink);
text(ax, 0.99, 1.055, sprintf('%s · %d 个遮蔽事件', missile, numel(idx)), ...
    'Units', 'normalized', 'HorizontalAlignment', 'right', ...
    'FontName', fontName, 'FontSize', 7.4, 'FontWeight', 'bold', ...
    'Color', C.ink, 'Interpreter', 'none');

xlim(ax, [0, 3]);
ylim(ax, [-1.08, 1.82]);
set(ax, 'XTick', [0.5, 1.5, 2.5], 'XTickLabel', {'远', '中', '近'});
if strcmp(missile, 'M1')
    ylabel(ax, 'y / km', 'FontName', fontName, 'FontSize', 8.0, 'Color', C.ink);
else
    set(ax, 'YTickLabel', []);
end
styleAxis(ax, C, fontName, false);
hold(ax, 'off');
end


function xMapped = segmentedX(xKm, windows)
xMapped = NaN;
for w = 1:size(windows, 1)
    left = windows(w, 1);
    right = windows(w, 2);
    if xKm >= left - 1e-9 && xKm <= right + 1e-9
        xMapped = (w - 1) + 0.10 + 0.80 * (xKm - left) / (right - left);
        return;
    end
end
end


function renderCoverageEvents(q5, plans, shotIndex, outDir, C, fontName)
% Event arcs replace conventional Gantt bars.  Each panel discloses the
% exact entry/exit events and the coverage-count state they induce.
fig = figure('Visible', 'off', 'Color', C.paper, 'Renderer', 'painters', ...
    'Units', 'inches', 'Position', [0.5, 0.5, 6.20, 5.05], ...
    'PaperPositionMode', 'auto');
ax = [ ...
    axes(fig, 'Position', [0.105, 0.680, 0.855, 0.225]), ...
    axes(fig, 'Position', [0.105, 0.382, 0.855, 0.225]), ...
    axes(fig, 'Position', [0.105, 0.084, 0.855, 0.225])];

missiles = {'M1', 'M2', 'M3'};
xMin = 5.5;
xMax = 42.5;
for m = 1:3
    drawMissileEvents(ax(m), q5, plans, shotIndex, missiles{m}, ...
        xMin, xMax, C, fontName, char('a' + m - 1));
    if m < 3
        set(ax(m), 'XTickLabel', []);
    else
        xlabel(ax(m), '任务时刻 / s', 'FontName', fontName, ...
            'FontSize', 8.2, 'Color', C.ink);
    end
end

annotation(fig, 'textbox', [0.100, 0.942, 0.860, 0.035], ...
    'String', '▷ 进入    ◁ 退出    弧线型/顶点符号=无人机    蓝灰阶梯 n_j(t)    ↔ 最大空窗', ...
    'HorizontalAlignment', 'right', 'VerticalAlignment', 'middle', ...
    'FontName', fontName, 'FontSize', 7.0, 'Color', C.muted, ...
    'Interpreter', 'none', 'EdgeColor', 'none', 'FitBoxToText', 'off');

exportFigure(fig, outDir, 'q5_coverage_gantt', C.paper);
close(fig);
end


function drawMissileEvents(ax, q5, plans, shotIndex, missile, xMin, xMax, C, fontName, panelLetter)
hold(ax, 'on');
missileNumber = sscanf(missile, 'M%d');
missileColor = C.missile(missileNumber, :);
idx = find(strcmp({plans.missile_id}, missile));
[~, order] = sort([plans(idx).exact_centerline_duration]);
idx = idx(order);

allIntervals = zeros(numel(idx), 2);
for k = 1:numel(idx)
    interval = plans(idx(k)).exact_centerline_intervals;
    assert(size(interval, 1) == 1 && size(interval, 2) == 2, ...
        'Every Q5 selected bomb must have one centerline interval.');
    allIntervals(k, :) = interval(1, :);
end

% Quiet state bands expose the discrete count semantics without turning
% intervals into long filled bars.
stateBands = [ ...
    C.panel; ...
    mixColor(C.primary, C.paper, 0.025); ...
    mixColor(C.secondary, C.paper, 0.025)];
bandEdges = [0.11, 0.59, 1.09, 1.48];
for level = 1:3
    patch(ax, [xMin, xMax, xMax, xMin], ...
        [bandEdges(level), bandEdges(level), bandEdges(level + 1), bandEdges(level + 1)], ...
        stateBands(level, :), 'EdgeColor', 'none');
end

% Coverage-count staircase generated only by the discrete event list.
[stepX, stepN] = eventStep(allIntervals, xMin, xMax);
stepY = 0.34 + 0.50 * stepN;
plot(ax, stepX, stepY, '-', 'Color', C.primary, 'LineWidth', 1.70);
for level = 0:2
    plot(ax, [xMin, xMax], [0.34 + 0.50 * level, 0.34 + 0.50 * level], ...
        ':', 'Color', C.grid, 'LineWidth', 0.55);
end

% Entry/exit nodes share an event baseline; a shallow arc pairs them
% without encoding duration as a thick bar.
yBase = 1.55;
arcStyles = {'-', '--', '-.', ':', '-'};
arcMarkers = {'o', 's', '^', 'd', 'v'};
for k = 1:numel(idx)
    planIndex = idx(k);
    plan = plans(planIndex);
    interval = allIntervals(k, :);
    a = interval(1);
    b = interval(2);
    droneNumber = sscanf(plan.drone_id, 'FY%d');
    color = C.drone(droneNumber, :);
    % Two deliberately separated label levels keep adjacent FY1 and FY5/FY2
    % events readable after the figure is reduced to manuscript width.
    arcHeight = 0.15 + 0.14 * mod(k - 1, 2);
    u = linspace(0, 1, 80);
    xArc = a + (b - a) * u;
    yArc = yBase + 4 * arcHeight * u .* (1 - u);
    plot(ax, xArc, yArc, arcStyles{droneNumber}, ...
        'Color', color, 'LineWidth', 1.00);
    plot(ax, mean([a, b]), yBase + arcHeight, arcMarkers{droneNumber}, ...
        'MarkerSize', 3.8, 'MarkerFaceColor', C.paper, ...
        'MarkerEdgeColor', color, 'LineWidth', 0.75);
    plot(ax, a, yBase, '>', 'MarkerSize', 5.8, ...
        'MarkerFaceColor', C.paper, 'MarkerEdgeColor', C.ink, 'LineWidth', 0.85);
    plot(ax, b, yBase, '<', 'MarkerSize', 5.8, ...
        'MarkerFaceColor', C.ink, 'MarkerEdgeColor', C.paper, 'LineWidth', 0.65);
    label = sprintf('%s·%d', plan.drone_id, shotIndex(planIndex));
    text(ax, 0.5 * (a + b), yBase + arcHeight + 0.055, label, ...
        'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom', ...
        'FontName', fontName, 'FontSize', 7.0, 'Color', C.ink, ...
        'BackgroundColor', C.paper, 'Margin', 0.25, 'Interpreter', 'none');
end

% Maximum internal gap is computed from the verified interval union.
unionIntervals = q5.exact_centerline_union.(missile);
gaps = [unionIntervals(1:end-1, 2), unionIntervals(2:end, 1)];
if ~isempty(gaps)
    [gapLength, gapIndex] = max(gaps(:, 2) - gaps(:, 1));
    gap = gaps(gapIndex, :);
    yGap = 0.08;
    quiver(ax, gap(1), yGap, gap(2)-gap(1), 0, 0, ...
        'Color', C.warm, 'LineWidth', 0.90, 'MaxHeadSize', 0.035, ...
        'AutoScale', 'off');
    quiver(ax, gap(2), yGap, gap(1)-gap(2), 0, 0, ...
        'Color', C.warm, 'LineWidth', 0.90, 'MaxHeadSize', 0.035, ...
        'AutoScale', 'off');
    text(ax, mean(gap), -0.01, sprintf('最大空窗 %.2f s', gapLength), ...
        'HorizontalAlignment', 'center', 'VerticalAlignment', 'top', ...
        'FontName', fontName, 'FontSize', 7.0, 'FontWeight', 'bold', ...
        'Color', C.warm, 'BackgroundColor', C.paper, 'Margin', 0.3, ...
        'Interpreter', 'none');
end

duration = q5.exact_centerline_duration_by_missile.(missile);
text(ax, 0.008, 1.09, panelLetter, 'Units', 'normalized', ...
    'FontName', 'Arial', 'FontSize', 9.0, 'FontWeight', 'bold', 'Color', C.ink);
text(ax, 0.050, 1.09, sprintf('%s  ·  并集 %.3f s', missile, duration), 'Units', 'normalized', ...
    'FontName', fontName, 'FontSize', 7.8, 'FontWeight', 'bold', ...
    'Color', missileColor, 'Interpreter', 'none');

xlim(ax, [xMin, xMax]);
ylim(ax, [-0.10, 2.02]);
set(ax, 'YTick', [0.34, 0.84, 1.34], 'YTickLabel', {'0', '1', '2'}, ...
    'XTick', 5:5:45);
ylabel(ax, 'n_j(t)', 'FontName', fontName, 'FontSize', 8.0, ...
    'Color', C.ink, 'Interpreter', 'tex');
styleAxis(ax, C, fontName, true);
hold(ax, 'off');
end


function [x, n] = eventStep(intervals, xMin, xMax)
eventTimes = [intervals(:, 1); intervals(:, 2)];
deltas = [ones(size(intervals, 1), 1); -ones(size(intervals, 1), 1)];
[uniqueTimes, ~, groups] = unique(eventTimes);
groupDelta = accumarray(groups, deltas);

x = xMin;
n = 0;
current = 0;
for k = 1:numel(uniqueTimes)
    t = uniqueTimes(k);
    x = [x, t, t]; %#ok<AGROW>
    n = [n, current, current + groupDelta(k)]; %#ok<AGROW>
    current = current + groupDelta(k);
end
x = [x, xMax];
n = [n, current];
assert(abs(current) < 1e-12, 'Coverage-count event balance must end at zero.');
end


function renderPairedAudit(q5, fullAudit, outDir, C, fontName)
% Paired point-and-loss connections; no bars or filled rectangles.
fig = figure('Visible', 'off', 'Color', C.paper, 'Renderer', 'painters', ...
    'Units', 'inches', 'Position', [0.5, 0.5, 6.20, 2.75], ...
    'PaperPositionMode', 'auto');
axA = axes(fig, 'Position', [0.105, 0.205, 0.535, 0.690]);
axB = axes(fig, 'Position', [0.730, 0.205, 0.235, 0.690]);

missiles = {'M1', 'M2', 'M3'};
center = zeros(1, 3);
full = zeros(1, 3);
for k = 1:3
    center(k) = q5.exact_centerline_duration_by_missile.(missiles{k});
    full(k) = fullAudit.duration_by_missile.(missiles{k});
end

hold(axA, 'on');
missileStyles = {'-', '--', '-.'};
for k = 1:3
    y = 4 - k;
    plot(axA, [full(k), center(k)], [y, y], missileStyles{k}, ...
        'Color', C.muted, 'LineWidth', 1.25);
    plot(axA, center(k), y, 'o', 'MarkerSize', 7.3, ...
        'MarkerFaceColor', C.primary, 'MarkerEdgeColor', C.paper, 'LineWidth', 0.7);
    plot(axA, full(k), y, 's', 'MarkerSize', 6.8, ...
        'MarkerFaceColor', C.paper, 'MarkerEdgeColor', C.wine, 'LineWidth', 1.25);
    loss = center(k) - full(k);
    retention = 100 * full(k) / center(k);
    text(axA, 0.5 * (full(k) + center(k)), y + 0.22, ...
        sprintf('损失 %.2f s  ·  保留 %.1f%%', loss, retention), ...
        'HorizontalAlignment', 'center', 'FontName', fontName, ...
        'FontSize', 7.0, 'Color', C.muted, 'Interpreter', 'none');
end
text(axA, 0.01, 1.045, 'a', 'Units', 'normalized', ...
    'FontName', 'Arial', 'FontSize', 9.2, 'FontWeight', 'bold', 'Color', C.ink);
text(axA, 0.99, 1.045, '分导弹配对复算', 'Units', 'normalized', ...
    'HorizontalAlignment', 'right', 'FontName', fontName, ...
    'FontSize', 7.6, 'FontWeight', 'bold', 'Color', C.ink);
xlim(axA, [9.5, 24.8]);
ylim(axA, [0.5, 3.5]);
set(axA, 'YTick', [1, 2, 3], 'YTickLabel', {'M3', 'M2', 'M1'}, ...
    'XTick', 10:2:24);
xlabel(axA, '有效并集 / s', 'FontName', fontName, 'FontSize', 8.2, 'Color', C.ink);
styleAxis(axA, C, fontName, true);
hold(axA, 'off');

centerTotal = sum(center);
fullTotal = sum(full);
lossTotal = centerTotal - fullTotal;
retentionTotal = 100 * fullTotal / centerTotal;
hold(axB, 'on');
plot(axB, [fullTotal, centerTotal], [1, 1], '-', ...
    'Color', C.muted, 'LineWidth', 1.45);
plot(axB, centerTotal, 1, 'o', 'MarkerSize', 8.2, ...
    'MarkerFaceColor', C.primary, 'MarkerEdgeColor', C.paper, 'LineWidth', 0.7);
plot(axB, fullTotal, 1, 's', 'MarkerSize', 7.7, ...
    'MarkerFaceColor', C.paper, 'MarkerEdgeColor', C.wine, 'LineWidth', 1.35);
text(axB, centerTotal, 0.77, sprintf('%.2f', centerTotal), ...
    'HorizontalAlignment', 'center', 'FontName', fontName, ...
    'FontSize', 7.2, 'FontWeight', 'bold', 'Color', C.primary);
text(axB, fullTotal, 0.77, sprintf('%.2f', fullTotal), ...
    'HorizontalAlignment', 'center', 'FontName', fontName, ...
    'FontSize', 7.2, 'FontWeight', 'bold', 'Color', C.wine);
text(axB, mean([fullTotal, centerTotal]), 1.26, ...
    sprintf('总损失 %.2f s\n保留 %.1f%%', lossTotal, retentionTotal), ...
    'HorizontalAlignment', 'center', 'FontName', fontName, ...
    'FontSize', 7.2, 'FontWeight', 'bold', 'Color', C.ink, ...
    'BackgroundColor', C.paper, 'Margin', 0.7, 'Interpreter', 'none');
text(axB, 0.01, 1.045, 'b', 'Units', 'normalized', ...
    'FontName', 'Arial', 'FontSize', 9.2, 'FontWeight', 'bold', 'Color', C.ink);
text(axB, 0.99, 1.045, '三弹合计', 'Units', 'normalized', ...
    'HorizontalAlignment', 'right', 'FontName', fontName, ...
    'FontSize', 7.6, 'FontWeight', 'bold', 'Color', C.ink);
xlim(axB, [38, 56]);
ylim(axB, [0.50, 1.55]);
set(axB, 'YTick', [], 'XTick', 40:5:55);
xlabel(axB, '时长之和 / s', 'FontName', fontName, 'FontSize', 8.2, 'Color', C.ink);
styleAxis(axB, C, fontName, true);
hold(axB, 'off');

% Direct labels are more stable than a boxed legend at manuscript size.
annotation(fig, 'textbox', [0.105, 0.940, 0.175, 0.045], ...
    'String', '●  中心视线口径', 'FontName', fontName, ...
    'FontSize', 7.0, 'Color', C.primary, 'Interpreter', 'none', ...
    'EdgeColor', 'none', 'FitBoxToText', 'off', 'VerticalAlignment', 'middle');
annotation(fig, 'textbox', [0.285, 0.940, 0.240, 0.045], ...
    'String', '□  完整圆柱保守口径', 'FontName', fontName, ...
    'FontSize', 7.0, 'Color', C.wine, 'Interpreter', 'none', ...
    'EdgeColor', 'none', 'FitBoxToText', 'off', 'VerticalAlignment', 'middle');

exportFigure(fig, outDir, 'q5_per_missile_robustness', C.paper);
close(fig);
end


function shotIndex = computeShotIndex(plans)
shotIndex = zeros(numel(plans), 1);
droneNames = unique({plans.drone_id}, 'stable');
for d = 1:numel(droneNames)
    idx = find(strcmp({plans.drone_id}, droneNames{d}));
    [~, order] = sort([plans(idx).release_time]);
    shotIndex(idx(order)) = 1:numel(idx);
end
end


function C = editorialPalette()
C.paper = hexColor('#FCFBF7');
C.ink = hexColor('#25313A');
C.muted = hexColor('#66737C');
C.grid = hexColor('#DCE2E5');
C.primary = hexColor('#3E6F8F');
C.secondary = hexColor('#5F8375');
C.warm = hexColor('#C1844F');
C.wine = hexColor('#9B5B64');
C.panel = mixColor(C.grid, C.paper, 0.24);
C.blueDark = mixColor(C.ink, C.primary, 0.24);
C.blueSoft = mixColor(C.primary, C.muted, 0.62);
C.tealSoft = mixColor(C.secondary, C.muted, 0.66);
C.guide = C.grid;
C.guideDark = mixColor(C.muted, C.paper, 0.62);
C.drone = [C.primary; C.blueDark; C.blueSoft; C.secondary; C.tealSoft];
C.missile = repmat(C.muted, 3, 1);
end


function styleAxis(ax, C, fontName, verticalGrid)
set(ax, 'FontName', fontName, 'FontSize', 7.2, 'Color', C.paper, ...
    'XColor', C.muted, 'YColor', C.muted, 'TickDir', 'out', ...
    'TickLength', [0.010, 0.010], 'LineWidth', 0.65, 'Box', 'off', ...
    'Layer', 'top');
if verticalGrid
    grid(ax, 'on');
    ax.XGrid = 'on';
    ax.YGrid = 'off';
    ax.GridColor = C.grid;
    ax.GridAlpha = 0.38;
    ax.GridLineStyle = ':';
else
    grid(ax, 'off');
end
end


function rgb = hexColor(code)
code = char(erase(string(code), '#'));
rgb = [hex2dec(code(1:2)), hex2dec(code(3:4)), hex2dec(code(5:6))] / 255;
end


function color = mixColor(foreground, background, weight)
weight = max(0, min(1, weight));
color = weight * foreground + (1 - weight) * background;
end


function exportFigure(fig, outDir, stem, paperColor)
pngPath = fullfile(outDir, [stem, '.png']);
pdfPath = fullfile(outDir, [stem, '.pdf']);
svgPath = fullfile(outDir, [stem, '.svg']);
exportgraphics(fig, pngPath, 'Resolution', 360, 'BackgroundColor', paperColor);
exportgraphics(fig, pdfPath, 'ContentType', 'vector', 'BackgroundColor', paperColor);
try
    exportgraphics(fig, svgPath, 'ContentType', 'vector', 'BackgroundColor', paperColor);
catch
    print(fig, svgPath, '-dsvg', '-painters');
end
fprintf('  %s\n  %s\n  %s\n', pngPath, pdfPath, svgPath);
end


function fontName = chooseChineseFont()
preferred = {'Microsoft YaHei', 'Microsoft JhengHei UI', ...
    'Noto Sans CJK SC', 'SimHei', 'Arial Unicode MS', 'Arial'};
available = listfonts;
fontName = 'Arial';
for k = 1:numel(preferred)
    if any(strcmpi(available, preferred{k}))
        fontName = preferred{k};
        return;
    end
end
end
