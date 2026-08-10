function render_q5_figures()
%RENDER_Q5_FIGURES Render the three Q5 evidence figures in MATLAB.
%
% The script reads the independently reproduced Q5 result directly from
% validation/q3_q5_independent.json.  The Q5 summary couples a fixed-order,
% seven-variable shot-role matrix with exact union segments and entry/exit
% markers.  No generic dashboard cards or decorative bars are used.

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
renderCoverageEvents(q5, fullAudit, plans, shotIndex, outDir, C, fontName);
renderPairedAudit(q5, fullAudit, outDir, C, fontName);

fprintf('Rendered Q5 MATLAB figures in %s\n', outDir);
end


function renderXYStrategy(plans, shotIndex, outDir, C, fontName)
% Global geometry on a true metric scale plus three compact event facets.
fig = figure('Visible', 'off', 'Color', C.paper, 'Renderer', 'painters', ...
    'Units', 'inches', 'Position', [0.5, 0.5, 6.30, 4.55], ...
    'PaperPositionMode', 'auto');

axGlobal = axes(fig, 'Position', [0.082, 0.525, 0.885, 0.385]);
axLocal = [ ...
    axes(fig, 'Position', [0.075, 0.112, 0.275, 0.250]), ...
    axes(fig, 'Position', [0.382, 0.112, 0.275, 0.250]), ...
    axes(fig, 'Position', [0.689, 0.112, 0.275, 0.250])];

droneNames = {'FY1', 'FY2', 'FY3', 'FY4', 'FY5'};
lineStyles = {'-', '--', '-.', ':', '-'};
startMarkers = {'o', 's', '^', 'd', 'v'};
missileStyles = {'--', '-.', ':'};
hold(axGlobal, 'on');

% Incoming missile directions from the official initial positions to the
% false target.  They are deliberately quiet context, not the focal layer.
missileStarts = [20.0, 0.0; 19.0, 0.6; 18.0, -0.6];
for k = 1:3
    plot(axGlobal, [missileStarts(k, 1), 0], [missileStarts(k, 2), 0], ...
        missileStyles{k}, 'Color', C.sightline, 'LineWidth', 0.70);
    plot(axGlobal, missileStarts(k, 1), missileStarts(k, 2), '<', ...
        'MarkerSize', 5.2, 'MarkerFaceColor', C.paper, ...
        'MarkerEdgeColor', C.guideDark, 'LineWidth', 0.85);
    missileLabelDy = [0.30, 0.30, -0.31];
    text(axGlobal, missileStarts(k, 1) - 0.10, ...
        missileStarts(k, 2) + missileLabelDy(k), ...
        sprintf('M%d', k), 'HorizontalAlignment', 'center', ...
        'FontName', fontName, 'FontSize', 7.2, 'FontWeight', 'bold', ...
        'Color', C.muted);
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

annotation(fig, 'textbox', [0.075, 0.395, 0.890, 0.045], ...
    'String', '局部航程分段（横轴不连续）：远 16.0–18.2 km  |  中 8.7–12.5 km  |  近 2.8–4.5 km', ...
    'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
    'FontName', fontName, 'FontSize', 7.0, 'Color', C.muted, ...
    'Interpreter', 'none', 'EdgeColor', 'none', 'FitBoxToText', 'off');
annotation(fig, 'textbox', [0.075, 0.025, 0.890, 0.038], ...
    'String', '远 → 中 → 近    ◇ 投放    ● 起爆    标注 FY·k = 无人机·同机弹序', ...
    'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
    'FontName', fontName, 'FontSize', 7.0, 'Color', C.muted, ...
    'Interpreter', 'none', 'EdgeColor', 'none', 'FitBoxToText', 'off');

exportFigure(fig, outDir, 'q5_xy_strategy', C.paper);
close(fig);
end


function drawLocalMissile(ax, plans, shotIndex, missile, C, fontName, panelLetter)
hold(ax, 'on');

% The three physical x windows are ordered by flight progress (far to near)
% and share one explanation above all three facets.
windows = [16.0, 18.2; 8.7, 12.5; 2.8, 4.5];
plot(ax, [1, 1], [-1.05, 1.72], ':', 'Color', C.grid, 'LineWidth', 0.65);
plot(ax, [2, 2], [-1.05, 1.72], ':', 'Color', C.grid, 'LineWidth', 0.65);
plot(ax, [0, 3], [0, 0], '-', 'Color', C.grid, 'LineWidth', 0.65);

idx = find(strcmp({plans.missile_id}, missile));
[~, order] = sort([plans(idx).explosion_time]);
idx = idx(order);
if strcmp(missile, 'M1')
    labelX = [0.77, 0.47, 0.21, 1.73, 1.79, 1.25, 2.45];
    labelY = [0.92, 0.53, 0.18, 0.88, -0.53, 1.56, 0.63];
elseif strcmp(missile, 'M2')
    labelX = [1.82, 1.24, 1.64, 2.38];
    labelY = [0.92, 1.55, -0.02, 0.82];
else
    labelX = [1.82, 1.67, 1.22, 2.42];
    labelY = [-0.70, 0.33, 1.38, 0.62];
end
droneStyles = {'-', '--', '-.', ':', '-'};

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
        'Color', color, 'LineWidth', 1.25);
    plot(ax, xr, releaseKm(2), 'd', 'MarkerSize', 4.6, ...
        'MarkerFaceColor', C.paper, 'MarkerEdgeColor', color, 'LineWidth', 0.9);
    plot(ax, xe, explosionKm(2), 'o', 'MarkerSize', 5.0, ...
        'MarkerFaceColor', color, 'MarkerEdgeColor', C.paper, 'LineWidth', 0.6);

    % Each release-explosion pair receives exactly one complete FY·k label.
    label = sprintf('%s·%d', plan.drone_id, shotIndex(planIndex));
    lx = labelX(min(p, numel(labelX)));
    ly = labelY(min(p, numel(labelY)));
    text(ax, lx, ly, label, ...
        'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
        'FontName', fontName, 'FontSize', 7.0, 'FontWeight', 'bold', 'Color', C.ink, ...
        'BackgroundColor', C.paper, 'Margin', 0.25, 'Interpreter', 'none');
end

text(ax, 0.01, 1.055, panelLetter, 'Units', 'normalized', ...
    'FontName', 'Arial', 'FontSize', 9.0, 'FontWeight', 'bold', 'Color', C.ink);
text(ax, 0.99, 1.055, sprintf('%s  (%d)', missile, numel(idx)), ...
    'Units', 'normalized', 'HorizontalAlignment', 'right', ...
    'FontName', fontName, 'FontSize', 7.4, 'FontWeight', 'bold', ...
    'Color', C.ink, 'Interpreter', 'none');

xlim(ax, [0, 3]);
ylim(ax, [-1.05, 1.72]);
set(ax, 'XTick', [], 'YTick', [-1, 0, 1]);
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


function renderCoverageEvents(q5, fullAudit, plans, shotIndex, outDir, C, fontName)
% The left panel is a fixed-order, high-dimensional role matrix for all
% selected shots; the right panel is the verified union event strip.  The
% two panels connect decision roles to temporal consequences without
% treating the 15 jointly selected records as independent observations.
fig = figure('Visible', 'off', 'Color', C.paper, 'Renderer', 'painters', ...
    'Units', 'inches', 'Position', [0.5, 0.5, 6.20, 4.30], ...
    'PaperPositionMode', 'auto');
axMatrix = axes(fig, 'Position', [0.115, 0.170, 0.305, 0.700]);
axUnion = axes(fig, 'Position', [0.505, 0.155, 0.455, 0.720]);
drawMultivariateMatrix(axMatrix, q5, fullAudit, plans, shotIndex, C, fontName);
drawUnionEventStrips(axUnion, q5, plans, shotIndex, C, fontName);

exportFigure(fig, outDir, 'q5_coverage_gantt', C.paper);
close(fig);
end


function drawMultivariateMatrix(ax, q5, fullAudit, plans, shotIndex, C, fontName)
% Each row is one selected shot.  Rows remain in UAV/shot order because
% same-UAV route constraints mechanically induce similarity; clustering
% them would imply an unsupported population structure.
nPlans = numel(plans);
assert(nPlans == 15 && numel(fullAudit.individual_durations) == nPlans, ...
    'The multivariate panel requires 15 aligned centerline/full-cylinder records.');

droneNumber = zeros(nPlans, 1);
for i = 1:nPlans
    droneNumber(i) = sscanf(plans(i).drone_id, 'FY%d');
end
[~, order] = sortrows([droneNumber, shotIndex(:)], [1, 2]);

raw = zeros(nPlans, 7);
rowLabels = cell(nPlans, 1);
fullDurations = reshape(fullAudit.individual_durations, [], 1);
for row = 1:nPlans
    i = order(row);
    plan = plans(i);
    intervals = normaliseIntervals(plan.exact_centerline_intervals);
    lengths = intervals(:, 2) - intervals(:, 1);
    duration = sum(lengths);
    timeCentroid = sum(mean(intervals, 2) .* lengths) / duration;

    sameMissile = find(strcmp({plans.missile_id}, plan.missile_id));
    allIntervals = collectIntervals(plans, sameMissile);
    withoutIntervals = collectIntervals(plans, sameMissile(sameMissile ~= i));
    unionLength = intervalUnionLength(allIntervals);
    withoutLength = intervalUnionLength(withoutIntervals);
    referenceLength = q5.exact_centerline_duration_by_missile.(plan.missile_id);
    assert(abs(unionLength - referenceLength) < 5e-7, ...
        'Leave-one-out union is inconsistent with the verified Q5 duration.');
    uniqueRatio = (unionLength - withoutLength) / max(duration, eps);
    uniqueRatio = min(1, max(0, uniqueRatio));
    retentionRatio = fullDurations(i) / max(duration, eps);

    raw(row, :) = [plan.speed, plan.release_time, plan.fuse_delay, ...
        timeCentroid, duration, uniqueRatio, retentionRatio];
    rowLabels{row} = sprintf('%s-%d \\rightarrow %s', ...
        plan.drone_id, shotIndex(i), plan.missile_id);
end

columnMean = mean(raw, 1);
columnStd = std(raw, 0, 1);
assert(all(columnStd > 1e-12), 'Every displayed feature must vary across the 15 shots.');
z = (raw - columnMean) ./ columnStd;
displayLimit = 2.5;

imagesc(ax, max(-displayLimit, min(displayLimit, z)));
colormap(ax, interpolateSequential(C.sequentialAnchors, 256));
caxis(ax, [-displayLimit, displayLimit]);
hold(ax, 'on');
for boundary = [3.5, 6.5, 9.5, 12.5]
    plot(ax, [0.5, 7.5], [boundary, boundary], '-', ...
        'Color', C.paper, 'LineWidth', 1.15);
end
plot(ax, [5.5, 5.5], [0.5, 15.5], '-', ...
    'Color', C.paper, 'LineWidth', 1.20);

text(ax, -0.23, 1.075, 'a', 'Units', 'normalized', ...
    'FontName', 'Arial', 'FontSize', 9.2, 'FontWeight', 'bold', 'Color', C.ink);
text(ax, 0.50, 1.075, '逐弹七维角色矩阵', 'Units', 'normalized', ...
    'HorizontalAlignment', 'center', 'FontName', fontName, ...
    'FontSize', 8.5, 'FontWeight', 'bold', 'Color', C.ink, 'Interpreter', 'none');

xLabels = {'v', 't^r', '\tau', 't^c', 'd_i', 'u_i', 'r_i'};
set(ax, 'XTick', 1:7, 'XTickLabel', xLabels, ...
    'YTick', 1:nPlans, 'YTickLabel', rowLabels, ...
    'XAxisLocation', 'top', 'YDir', 'reverse', ...
    'TickLabelInterpreter', 'tex', 'FontName', fontName, 'FontSize', 6.4, ...
    'XColor', C.muted, 'YColor', C.muted, 'TickLength', [0, 0], ...
    'Color', C.paper, 'Box', 'off', 'Layer', 'top');
xlim(ax, [0.5, 7.5]);
ylim(ax, [0.5, nPlans + 0.5]);

matrixPosition = ax.Position;
cb = colorbar(ax, 'southoutside');
ax.Position = matrixPosition;
cb.Position = [0.145, 0.095, 0.245, 0.018];
cb.Ticks = [-2, 0, 2];
cb.TickLabels = {'-2', '0', '2'};
cb.FontName = fontName;
cb.FontSize = 6.4;
cb.Color = C.muted;
cb.Box = 'off';
cb.Label.String = '列内 z 分数';
cb.Label.FontName = fontName;
cb.Label.FontSize = 6.8;
cb.Label.Color = C.muted;
hold(ax, 'off');
end


function intervals = normaliseIntervals(intervals)
if isempty(intervals)
    intervals = zeros(0, 2);
elseif isvector(intervals)
    assert(numel(intervals) == 2, 'An interval vector must have exactly two endpoints.');
    intervals = reshape(intervals, 1, 2);
else
    assert(size(intervals, 2) == 2, 'Intervals must be an n-by-2 matrix.');
end
end


function intervals = collectIntervals(plans, indices)
intervals = zeros(0, 2);
for index = reshape(indices, 1, [])
    intervals = [intervals; normaliseIntervals(plans(index).exact_centerline_intervals)]; %#ok<AGROW>
end
end


function total = intervalUnionLength(intervals)
intervals = normaliseIntervals(intervals);
if isempty(intervals)
    total = 0;
    return;
end
intervals = sortrows(intervals, [1, 2]);
current = intervals(1, :);
total = 0;
for i = 2:size(intervals, 1)
    candidate = intervals(i, :);
    if candidate(1) <= current(2) + 1e-10
        current(2) = max(current(2), candidate(2));
    else
        total = total + current(2) - current(1);
        current = candidate;
    end
end
total = total + current(2) - current(1);
end


function cmap = interpolateSequential(anchors, count)
anchorX = linspace(0, 1, size(anchors, 1));
queryX = linspace(0, 1, count);
cmap = zeros(count, 3);
for channel = 1:3
    cmap(:, channel) = interp1(anchorX, anchors(:, channel), queryX, 'pchip');
end
cmap = max(0, min(1, cmap));
end


function drawUnionEventStrips(ax, q5, plans, shotIndex, C, fontName)
hold(ax, 'on');
missiles = {'M1', 'M2', 'M3'};
rowY = [3, 2, 1];
    rowColors = repmat(C.primary, 3, 1);
xMin = 5.5;
xMax = 42.5;
for m = 1:3
    y = rowY(m);
    missile = missiles{m};
    plot(ax, [xMin, xMax], [y, y], '-', 'Color', C.guide, 'LineWidth', 0.8);
    unionIntervals = q5.exact_centerline_union.(missile);
    for k = 1:size(unionIntervals, 1)
        interval = unionIntervals(k, :);
        plot(ax, interval, [y, y], '-', 'Color', rowColors(m, :), 'LineWidth', 5.0);
        plot(ax, interval(1), y, '>', 'MarkerSize', 5.2, ...
            'MarkerFaceColor', C.paper, 'MarkerEdgeColor', rowColors(m, :), 'LineWidth', 0.9);
        plot(ax, interval(2), y, '<', 'MarkerSize', 5.2, ...
            'MarkerFaceColor', rowColors(m, :), 'MarkerEdgeColor', C.paper, 'LineWidth', 0.6);
    end

    idx = find(strcmp({plans.missile_id}, missile));
    for k = 1:numel(idx)
        interval = plans(idx(k)).exact_centerline_intervals(1, :);
        xMid = mean(interval);
        plot(ax, [xMid, xMid], [y - 0.16, y + 0.16], '-', ...
            'Color', C.ink, 'LineWidth', 1.1);
        text(ax, xMid, y + 0.20, sprintf('%d', shotIndex(idx(k))), ...
            'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom', ...
            'FontName', fontName, 'FontSize', 6.8, 'FontWeight', 'bold', ...
            'Color', C.ink, 'Interpreter', 'none');
    end

    if size(unionIntervals, 1) > 1
        gaps = [unionIntervals(1:end-1, 2), unionIntervals(2:end, 1)];
        [gapLength, gapIndex] = max(gaps(:, 2) - gaps(:, 1));
        gap = gaps(gapIndex, :);
        plot(ax, gap, [y - 0.28, y - 0.28], '--', 'Color', C.warm, 'LineWidth', 1.1);
        text(ax, mean(gap), y - 0.34, sprintf('%.2f s', gapLength), ...
            'HorizontalAlignment', 'center', 'VerticalAlignment', 'top', ...
            'FontName', fontName, 'FontSize', 6.9, 'FontWeight', 'bold', ...
            'Color', C.warm, 'Interpreter', 'none');
    end
    duration = q5.exact_centerline_duration_by_missile.(missile);
    text(ax, xMax + 0.35, y, sprintf('%.3f s', duration), ...
        'HorizontalAlignment', 'left', 'VerticalAlignment', 'middle', ...
        'FontName', fontName, 'FontSize', 7.2, 'FontWeight', 'bold', ...
        'Color', rowColors(m, :), 'Interpreter', 'none');
end

text(ax, -0.06, 1.07, 'b', 'Units', 'normalized', ...
    'FontName', 'Arial', 'FontSize', 9.2, 'FontWeight', 'bold', 'Color', C.ink);
text(ax, 0.50, 1.07, '各导弹的区间并集与进出事件', 'Units', 'normalized', ...
    'HorizontalAlignment', 'center', 'FontName', fontName, ...
    'FontSize', 8.5, 'FontWeight', 'bold', 'Color', C.ink, 'Interpreter', 'none');
xlim(ax, [xMin, xMax + 2.8]);
ylim(ax, [0.45, 3.55]);
xlabel(ax, '任务时刻 / s', 'FontName', fontName, 'FontSize', 8.2, 'Color', C.ink);
set(ax, 'XTick', 5:5:45, 'YTick', [1, 2, 3], 'YTickLabel', {'M3', 'M2', 'M1'}, ...
    'FontName', fontName, 'FontSize', 7.4, 'TickDir', 'out', ...
    'TickLength', [0.010, 0.010], 'XColor', C.muted, ...
    'YColor', C.muted, 'Color', C.paper, 'Box', 'off');
ax.XGrid = 'on';
ax.GridColor = C.grid;
ax.GridAlpha = 0.42;
ax.LineWidth = 0.65;
hold(ax, 'off');
end


function drawMissileEvents(ax, q5, plans, shotIndex, missile, xMin, xMax, C, fontName, panelLetter)
hold(ax, 'on');
missileNumber = sscanf(missile, 'M%d');
missileColor = C.missile(missileNumber, :);
idx = find(strcmp({plans.missile_id}, missile));
rawIntervals = zeros(numel(idx), 2);
for k = 1:numel(idx)
    interval = plans(idx(k)).exact_centerline_intervals;
    assert(size(interval, 1) == 1 && size(interval, 2) == 2, ...
        'Every Q5 selected bomb must have one centerline interval.');
    rawIntervals(k, :) = interval(1, :);
end
[~, order] = sort(rawIntervals(:, 1));
idx = idx(order);
allIntervals = rawIntervals(order, :);

% Coverage-count staircase generated only by the discrete event list.
[stepX, stepN] = eventStep(allIntervals, xMin, xMax);
stepY = 0.27 + 0.36 * stepN;
plot(ax, stepX, stepY, '-', 'Color', C.primary, 'LineWidth', 1.90);
for level = 0:2
    plot(ax, [xMin, xMax], [0.27 + 0.36 * level, 0.27 + 0.36 * level], ...
        ':', 'Color', C.grid, 'LineWidth', 0.55);
end

% Entry/exit nodes share an event baseline; a shallow arc pairs them
% without encoding duration as a thick bar.  This band is intentionally
% narrow so the coverage staircase remains the dominant temporal signal.
yBase = 1.25;
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
    arcColor = mixColor(color, C.paper, 0.82);
    arcHeight = 0.065 + 0.050 * mod(k - 1, 2);
    u = linspace(0, 1, 80);
    xArc = a + (b - a) * u;
    yArc = yBase + 4 * arcHeight * u .* (1 - u);
    plot(ax, xArc, yArc, arcStyles{droneNumber}, ...
        'Color', arcColor, 'LineWidth', 0.85);
    plot(ax, mean([a, b]), yBase + arcHeight, arcMarkers{droneNumber}, ...
        'MarkerSize', 3.5, 'MarkerFaceColor', C.paper, ...
        'MarkerEdgeColor', arcColor, 'LineWidth', 0.70);
    plot(ax, a, yBase, '>', 'MarkerSize', 4.8, ...
        'MarkerFaceColor', C.paper, 'MarkerEdgeColor', C.muted, 'LineWidth', 0.80);
    plot(ax, b, yBase, '<', 'MarkerSize', 4.8, ...
        'MarkerFaceColor', C.muted, 'MarkerEdgeColor', C.paper, 'LineWidth', 0.60);
    label = sprintf('%d', shotIndex(planIndex));
    text(ax, 0.5 * (a + b), yBase + arcHeight + 0.025, label, ...
        'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom', ...
        'FontName', fontName, 'FontSize', 7.0, 'FontWeight', 'bold', ...
        'Color', C.muted, 'BackgroundColor', C.paper, 'Margin', 0.15, ...
        'Interpreter', 'none');
end

% Maximum internal gap is computed from the verified interval union.
unionIntervals = q5.exact_centerline_union.(missile);
gaps = [unionIntervals(1:end-1, 2), unionIntervals(2:end, 1)];
if ~isempty(gaps)
    [gapLength, gapIndex] = max(gaps(:, 2) - gaps(:, 1));
    gap = gaps(gapIndex, :);
    yGap = 0.035;
    quiver(ax, gap(1), yGap, gap(2)-gap(1), 0, 0, ...
        'Color', C.warm, 'LineWidth', 0.90, 'MaxHeadSize', 0.035, ...
        'AutoScale', 'off');
    quiver(ax, gap(2), yGap, gap(1)-gap(2), 0, 0, ...
        'Color', C.warm, 'LineWidth', 0.90, 'MaxHeadSize', 0.035, ...
        'AutoScale', 'off');
    text(ax, mean(gap), -0.015, sprintf('最大空窗 %.2f s', gapLength), ...
        'HorizontalAlignment', 'center', 'VerticalAlignment', 'top', ...
        'FontName', fontName, 'FontSize', 7.4, 'FontWeight', 'bold', ...
        'Color', C.warm, 'BackgroundColor', C.paper, 'Margin', 0.3, ...
        'Interpreter', 'none');
end

duration = q5.exact_centerline_duration_by_missile.(missile);
text(ax, 0.008, 1.09, panelLetter, 'Units', 'normalized', ...
    'FontName', 'Arial', 'FontSize', 9.0, 'FontWeight', 'bold', 'Color', C.ink);
text(ax, 0.050, 1.09, sprintf('%s   覆盖并集 %.3f s', missile, duration), 'Units', 'normalized', ...
    'FontName', fontName, 'FontSize', 8.5, 'FontWeight', 'bold', ...
    'Color', C.ink, 'Interpreter', 'none');

xlim(ax, [xMin, xMax]);
ylim(ax, [-0.12, 1.48]);
set(ax, 'YTick', [0.27, 0.63, 0.99], 'YTickLabel', {'0', '1', '2'}, ...
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
% Compact paired point audit; the aggregate remains a subtitle, not a card.
fig = figure('Visible', 'off', 'Color', C.paper, 'Renderer', 'painters', ...
    'Units', 'inches', 'Position', [0.5, 0.5, 6.20, 2.90], ...
    'PaperPositionMode', 'auto');
ax = axes(fig, 'Position', [0.115, 0.205, 0.835, 0.675]);

missiles = {'M1', 'M2', 'M3'};
center = zeros(1, 3);
full = zeros(1, 3);
for k = 1:3
    center(k) = q5.exact_centerline_duration_by_missile.(missiles{k});
    full(k) = fullAudit.duration_by_missile.(missiles{k});
end

hold(ax, 'on');
missileStyles = {'-', '--', '-.'};
for k = 1:3
    y = 4 - k;
    plot(ax, [full(k), center(k)], [y, y], missileStyles{k}, ...
        'Color', C.guideDark, 'LineWidth', 1.35);
    plot(ax, center(k), y, 'o', 'MarkerSize', 7.2, ...
        'MarkerFaceColor', C.primary, 'MarkerEdgeColor', C.paper, 'LineWidth', 0.7);
    plot(ax, full(k), y, 's', 'MarkerSize', 6.8, ...
        'MarkerFaceColor', C.paper, 'MarkerEdgeColor', C.wine, 'LineWidth', 1.25);
    loss = center(k) - full(k);
    retention = 100 * full(k) / center(k);
    text(ax, full(k), y - 0.18, sprintf('%.2f', full(k)), ...
        'HorizontalAlignment', 'center', 'VerticalAlignment', 'top', ...
        'FontName', fontName, 'FontSize', 7.0, 'Color', C.wine);
    text(ax, center(k), y - 0.18, sprintf('%.2f', center(k)), ...
        'HorizontalAlignment', 'center', 'VerticalAlignment', 'top', ...
        'FontName', fontName, 'FontSize', 7.0, 'Color', C.primary);
    text(ax, 0.5 * (full(k) + center(k)), y + 0.22, ...
        sprintf('−%.2f s  ·  %.1f%%', loss, retention), ...
        'HorizontalAlignment', 'center', 'FontName', fontName, ...
        'FontSize', 7.0, 'FontWeight', 'bold', 'Color', C.muted, ...
        'Interpreter', 'none');
end
centerTotal = sum(center);
fullTotal = sum(full);
retentionTotal = 100 * fullTotal / centerTotal;

xlim(ax, [9.5, 24.8]);
ylim(ax, [0.38, 3.45]);
set(ax, 'YTick', [1, 2, 3], 'YTickLabel', {'M3', 'M2', 'M1'}, ...
    'XTick', 10:2:24);
xlabel(ax, '单枚导弹有效并集 / s', 'FontName', fontName, 'FontSize', 8.2, 'Color', C.ink);
styleAxis(ax, C, fontName, true);
hold(ax, 'off');

annotation(fig, 'textbox', [0.115, 0.905, 0.350, 0.050], ...
    'String', '● 中心视线判据    □ 圆柱整体判据', ...
    'FontName', fontName, 'FontSize', 7.2, 'Color', C.muted, ...
    'Interpreter', 'none', 'EdgeColor', 'none', 'FitBoxToText', 'off', ...
    'VerticalAlignment', 'middle');
annotation(fig, 'textbox', [0.475, 0.905, 0.475, 0.050], ...
    'String', sprintf('三弹合计  %.2f → %.2f s  ·  保留 %.1f%%', ...
        centerTotal, fullTotal, retentionTotal), ...
    'HorizontalAlignment', 'right', 'VerticalAlignment', 'middle', ...
    'FontName', fontName, 'FontSize', 7.8, 'FontWeight', 'bold', ...
    'Color', C.ink, 'Interpreter', 'none', 'EdgeColor', 'none', ...
    'FitBoxToText', 'off');

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
C = contest_palette();
C.panel = C.paper;
C.blueDark = mixColor(C.ink, C.primary, 0.24);
C.blueSoft = mixColor(C.primary, C.muted, 0.62);
C.tealSoft = mixColor(C.secondary, C.muted, 0.66);
C.guide = C.grid;
C.guideDark = mixColor(C.muted, C.paper, 0.62);
C.sightline = mixColor(C.muted, C.paper, 0.20);
% Equal-status UAVs share one editorial blue. Identity is carried by line
% style, marker shape and direct labels rather than unequal lightness.
C.drone = repmat(C.primary, 5, 1);
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
