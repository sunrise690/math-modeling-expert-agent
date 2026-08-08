function render_q3_event()
%RENDER_Q3_EVENT Draw the Q3 event hand-off evidence directly from validation data.
%
% The figure deliberately separates four layers of meaning:
%   1) release, detonation, coverage entry, and coverage exit events;
%   2) the two physical cloud hand-offs that close the coverage gaps;
%   3) the event-driven coverage-count staircase n(t);
%   4) exact overlap and union durations used by the paper.

scriptDir = fileparts(mfilename('fullpath'));
projectDir = fileparts(fileparts(scriptDir));
jsonPath = fullfile(projectDir, 'validation', 'q3_q5_independent.json');
outDir = fullfile(projectDir, 'figures');

assert(isfile(jsonPath), 'Validation data not found: %s', jsonPath);
if ~isfolder(outDir)
    mkdir(outDir);
end

payload = jsondecode(fileread(jsonPath));
q3 = payload.results.Q3;
plans = q3.plans;
assert(numel(plans) == 3, 'Q3 event figure expects exactly three selected smoke bombs.');

release = reshape([plans.release_time], [], 1);
detonate = reshape([plans.explosion_time], [], 1);
intervals = zeros(numel(plans), 2);
for k = 1:numel(plans)
    interval = plans(k).exact_centerline_intervals;
    assert(size(interval, 1) == 1 && size(interval, 2) == 2, ...
        'Each Q3 smoke bomb must have exactly one centerline interval.');
    intervals(k, :) = interval(1, :);
end

assert(all(release <= detonate + 1e-12), 'Release must precede detonation.');
assert(all(detonate <= intervals(:, 1) + 1e-12), ...
    'Detonation must not occur after coverage entry.');

unionInterval = q3.exact_centerline_union.M1;
assert(size(unionInterval, 1) == 1 && size(unionInterval, 2) == 2, ...
    'Q3 M1 union is expected to be one continuous interval.');
unionDuration = diff(unionInterval(1, :));

% Muted editorial palette: color is reserved for physical meaning.
C.paper = [0.992, 0.992, 0.986];
C.ink = [30, 42, 50] / 255;
C.muted = [108, 122, 132] / 255;
C.guide = [218, 225, 229] / 255;
C.blue = [62, 110, 147] / 255;
C.blueLight = [201, 216, 226] / 255;
C.orange = [190, 105, 61] / 255;
C.orangeLight = [232, 199, 175] / 255;
C.green = [92, 129, 115] / 255;

fontName = chooseChineseFont();
fig = figure('Visible', 'off', 'Color', C.paper, 'Renderer', 'painters', ...
    'Units', 'inches', 'Position', [0.5, 0.5, 6.20, 6.60], ...
    'PaperPositionMode', 'auto');

axMain = axes(fig, 'Position', [0.115, 0.675, 0.840, 0.255]);
axHand12 = axes(fig, 'Position', [0.080, 0.390, 0.410, 0.195]);
axHand23 = axes(fig, 'Position', [0.535, 0.390, 0.410, 0.195]);
axCount = axes(fig, 'Position', [0.115, 0.110, 0.840, 0.195]);

drawMainEventTrack(axMain, release, detonate, intervals, C, fontName);
drawHandoff(axHand12, plans, intervals, 1, 2, payload.model, C, fontName);
drawHandoff(axHand23, plans, intervals, 2, 3, payload.model, C, fontName);
drawCoverageCount(axCount, intervals, unionInterval(1, :), unionDuration, C, fontName);

pngPath = fullfile(outDir, 'q3_interval_union.png');
pdfPath = fullfile(outDir, 'q3_interval_union.pdf');
svgPath = fullfile(outDir, 'q3_interval_union.svg');
exportgraphics(fig, pngPath, 'Resolution', 360, 'BackgroundColor', C.paper);
exportgraphics(fig, pdfPath, 'ContentType', 'vector', 'BackgroundColor', C.paper);
try
    exportgraphics(fig, svgPath, 'ContentType', 'vector', 'BackgroundColor', C.paper);
catch
    print(fig, svgPath, '-dsvg', '-painters');
end
close(fig);

fprintf('Rendered Q3 event evidence:\n  %s\n  %s\n  %s\n', ...
    pngPath, pdfPath, svgPath);
end


function drawMainEventTrack(ax, release, detonate, intervals, C, fontName)
hold(ax, 'on');
rows = [3, 2, 1];
xlim(ax, [-1.05, 12.05]);
ylim(ax, [0.48, 3.64]);

for k = 1:3
    y = rows(k);
    yr = y + 0.10;
    yb = y - 0.10;
    entry = intervals(k, 1);
    exitTime = intervals(k, 2);

    plot(ax, [-0.15, 11.82], [y, y], '-', 'Color', C.guide, 'LineWidth', 0.70);
    plot(ax, [release(k), detonate(k)], [yr, yb], '--', ...
        'Color', C.muted, 'LineWidth', 1.0);
    plot(ax, [detonate(k), entry], [yb, y], '--', ...
        'Color', C.orange, 'LineWidth', 1.0);
    plot(ax, [entry, exitTime], [y, y], '-', ...
        'Color', C.blue, 'LineWidth', 4.1);

    plot(ax, release(k), yr, 'd', 'MarkerSize', 5.0, ...
        'MarkerFaceColor', C.paper, 'MarkerEdgeColor', C.ink, 'LineWidth', 1.0);
    plot(ax, detonate(k), yb, 'o', 'MarkerSize', 5.2, ...
        'MarkerFaceColor', C.orange, 'MarkerEdgeColor', C.paper, 'LineWidth', 0.7);
    plot(ax, entry, y, '>', 'MarkerSize', 5.7, ...
        'MarkerFaceColor', C.green, 'MarkerEdgeColor', C.paper, 'LineWidth', 0.7);
    plot(ax, exitTime, y, '<', 'MarkerSize', 5.7, ...
        'MarkerFaceColor', C.blue, 'MarkerEdgeColor', C.paper, 'LineWidth', 0.7);

    text(ax, -0.28, y, sprintf('烟幕弹 %d', k), ...
        'HorizontalAlignment', 'right', 'VerticalAlignment', 'middle', ...
        'FontName', fontName, 'FontSize', 7.8, 'FontWeight', 'bold', ...
        'Color', C.ink, 'Interpreter', 'none');

    if k ~= 1
        labelEvent(ax, release(k), yr, sprintf('%.3f', release(k)), ...
            +1, C.ink, C.paper, fontName);
        labelEvent(ax, detonate(k), yb, sprintf('%.3f', detonate(k)), ...
            -1, C.orange, C.paper, fontName);
    end
    labelEvent(ax, entry, y, sprintf('%.3f', entry), ...
        +1, C.green, C.paper, fontName);
    labelEvent(ax, exitTime, y, sprintf('%.3f', exitTime), ...
        -1, C.blue, C.paper, fontName);
end

% The first release/detonation pair and the third detonation/entry pair are
% almost simultaneous. Short leader lines disclose exact time without moving
% the event markers away from their true x coordinates.
plot(ax, [release(1), 0.58], [rows(1) + 0.10, 3.42], '-', ...
    'Color', C.guide, 'LineWidth', 0.7);
plot(ax, [detonate(1), 1.20], [rows(1) - 0.10, 2.67], '-', ...
    'Color', C.guide, 'LineWidth', 0.7);
text(ax, 0.61, 3.42, sprintf('%.3f', release(1)), ...
    'FontName', fontName, 'FontSize', 7.0, 'Color', C.ink, ...
    'VerticalAlignment', 'middle');
text(ax, 1.23, 2.67, sprintf('%.3f', detonate(1)), ...
    'FontName', fontName, 'FontSize', 7.0, 'Color', C.orange, ...
    'VerticalAlignment', 'middle');

text(ax, 0.01, 1.095, 'a', 'Units', 'normalized', ...
    'FontName', 'Arial', 'FontSize', 9.2, 'FontWeight', 'bold', 'Color', C.ink);
text(ax, 0.50, 1.095, '投放  →  起爆  →  进入  →  退出', ...
    'Units', 'normalized', 'HorizontalAlignment', 'center', ...
    'FontName', fontName, 'FontSize', 8.0, 'FontWeight', 'bold', ...
    'Color', C.ink, 'Interpreter', 'none');

xlabel(ax, '时间 / s', 'FontName', fontName, 'FontSize', 8.2, 'Color', C.ink);
set(ax, 'YTick', [], 'XTick', 0:2:12, 'FontName', fontName, ...
    'FontSize', 7.2, 'TickDir', 'out', 'TickLength', [0.010, 0.010], ...
    'XColor', C.muted, 'YColor', C.muted, 'Color', C.paper, 'Box', 'off');
ax.LineWidth = 0.65;
hold(ax, 'off');
end


function labelEvent(ax, x, y, label, direction, color, paper, fontName)
dy = 0.22 * direction;
text(ax, x, y + dy, label, 'HorizontalAlignment', 'center', ...
    'VerticalAlignment', 'middle', 'FontName', fontName, 'FontSize', 7.0, ...
    'Color', color, 'BackgroundColor', paper, 'Margin', 0.8, ...
    'Clipping', 'off');
end


function drawHandoff(ax, plans, intervals, oldIndex, newIndex, model, C, fontName)
hold(ax, 'on');
axis(ax, [0, 1, 0, 1]);
axis(ax, 'off');

tEnter = intervals(newIndex, 1);
tExit = intervals(oldIndex, 2);
overlap = tExit - tEnter;
assert(overlap > 0, 'The selected Q3 clouds must overlap at each hand-off.');
tMid = 0.5 * (tEnter + tExit);

% Official M1 trajectory: (20000,0,2000) toward the false target (0,0,0)
% at 300 m/s. The target point is read from the validation payload.
m0 = [20000, 0, 2000];
missile = m0 - 300 * m0 / norm(m0) * tMid;
target = reshape(model.target_centerline_point, 1, 3);
u = target - missile;
u2 = dot(u, u);
radius = model.smoke_radius_m;

indices = [oldIndex, newIndex];
dPerp = zeros(1, 2);
for j = 1:2
    plan = plans(indices(j));
    cloud = reshape(plan.explosion_position, 1, 3);
    cloud(3) = cloud(3) - model.smoke_sink_speed_m_s * (tMid - plan.explosion_time);
    lambda = max(0, min(1, dot(cloud - missile, u) / u2));
    foot = missile + lambda * u;
    dPerp(j) = norm(cloud - foot);
end
assert(all(dPerp <= radius + 1e-6), ...
    'Both clouds must intersect the finite sightline at the hand-off midpoint.');

rx = 0.110;
fig = ancestor(ax, 'figure');
axPos = get(ax, 'Position');
figPos = get(fig, 'Position');
displayAspect = (axPos(3) * figPos(3)) / (axPos(4) * figPos(4));
ry = rx * displayAspect;
xCenter = [0.25, 0.75];
cloudColor = [C.blue; C.orange];

lineY = 0.31;
quiver(ax, 0.045, lineY, 0.91, 0, 0, 'Color', C.ink, ...
    'LineWidth', 0.85, 'MaxHeadSize', 0.045, 'AutoScale', 'off');

theta = linspace(0, 2 * pi, 160);
for j = 1:2
    yc = lineY + ry * dPerp(j) / radius;
    xCircle = xCenter(j) + rx * cos(theta);
    yCircle = yc + ry * sin(theta);
    fill(ax, xCircle, yCircle, cloudColor(j, :), ...
        'FaceAlpha', 0.20, 'EdgeColor', cloudColor(j, :), 'LineWidth', 1.0);
    plot(ax, xCenter(j), yc, '.', 'Color', cloudColor(j, :), 'MarkerSize', 7.0);
    plot(ax, [xCenter(j), xCenter(j)], [lineY, yc], ':', ...
        'Color', cloudColor(j, :), 'LineWidth', 0.9);
    text(ax, xCenter(j), yc + 0.32 * ry, sprintf('d_\\perp=%.2f m', dPerp(j)), ...
        'HorizontalAlignment', 'center', 'FontName', 'Arial', 'FontSize', 7.0, ...
        'FontWeight', 'bold', 'Color', cloudColor(j, :), 'Interpreter', 'tex');
end

text(ax, xCenter(1), 0.79, '旧云未退出', ...
    'HorizontalAlignment', 'center', 'FontName', fontName, 'FontSize', 7.4, ...
    'FontWeight', 'bold', 'Color', C.blue, 'Interpreter', 'none');
text(ax, xCenter(2), 0.79, '新云已进入', ...
    'HorizontalAlignment', 'center', 'FontName', fontName, 'FontSize', 7.4, ...
    'FontWeight', 'bold', 'Color', C.orange, 'Interpreter', 'none');
text(ax, 0.50, 0.975, sprintf('接续 I%d→I%d：[%.3f, %.3f] s，双覆盖 %.3f s', ...
    oldIndex, newIndex, tEnter, tExit, overlap), ...
    'HorizontalAlignment', 'center', 'VerticalAlignment', 'top', ...
    'FontName', fontName, 'FontSize', 7.1, 'Color', C.ink, 'Interpreter', 'none');
text(ax, 0.50, 0.055, sprintf('法向按 R=%.0f m 比例；沿程折叠', radius), ...
    'HorizontalAlignment', 'center', 'FontName', fontName, 'FontSize', 7.0, ...
    'Color', C.muted, 'Interpreter', 'none');

panelLetter = char('a' + oldIndex);
text(ax, 0.00, 1.03, panelLetter, 'FontName', 'Arial', 'FontSize', 9.2, ...
    'FontWeight', 'bold', 'Color', C.ink, 'Clipping', 'off');
hold(ax, 'off');
end


function drawCoverageCount(ax, intervals, unionInterval, unionDuration, C, fontName)
hold(ax, 'on');
xMin = 4.55;
xMax = 11.70;
eventTimes = sort([intervals(:, 1); intervals(:, 2)]).';
breaks = [xMin, eventTimes, xMax];
counts = zeros(size(breaks));
for k = 1:(numel(breaks) - 1)
    probe = 0.5 * (breaks(k) + breaks(k + 1));
    counts(k) = sum(intervals(:, 1) <= probe & probe < intervals(:, 2));
end
counts(end) = 0;

stairs(ax, breaks, counts, '-', 'Color', C.ink, 'LineWidth', 1.65);

% Emphasize true double-coverage states as short event segments, not bars.
for k = 1:(numel(breaks) - 1)
    if counts(k) == 2
        plot(ax, [breaks(k), breaks(k + 1)], [2, 2], '-', ...
            'Color', C.orange, 'LineWidth', 3.2);
        plot(ax, [breaks(k), breaks(k + 1)], [2, 2], 'o', ...
            'Color', C.orange, 'MarkerFaceColor', C.paper, 'MarkerSize', 3.3);
    end
end

% Exact union and overlap brackets make the event arithmetic inspectable.
plot(ax, unionInterval, [-0.24, -0.24], '-', 'Color', C.blue, 'LineWidth', 2.4);
plot(ax, unionInterval, [-0.24, -0.24], 'o', 'Color', C.blue, ...
    'MarkerFaceColor', C.paper, 'MarkerSize', 3.5);
text(ax, mean(unionInterval), -0.08, sprintf('D_1 = %.3f s', unionDuration), ...
    'HorizontalAlignment', 'center', 'FontName', 'Arial', 'FontSize', 7.0, ...
    'FontWeight', 'bold', 'Color', C.blue, 'Interpreter', 'tex');

for k = 1:2
    left = intervals(k + 1, 1);
    right = intervals(k, 2);
    y = -0.62;
    plot(ax, [left, right], [y, y], '-', 'Color', C.orange, 'LineWidth', 1.05);
    plot(ax, [left, left], [y - 0.05, y + 0.05], '-', 'Color', C.orange, 'LineWidth', 0.9);
    plot(ax, [right, right], [y - 0.05, y + 0.05], '-', 'Color', C.orange, 'LineWidth', 0.9);
    text(ax, mean([left, right]), y - 0.09, ...
        sprintf('I%d∩I%d = %.3f s', k, k + 1, right - left), ...
        'HorizontalAlignment', 'center', 'VerticalAlignment', 'top', ...
        'FontName', fontName, 'FontSize', 7.0, 'Color', C.orange, ...
        'Interpreter', 'none');
end

text(ax, 0.01, 1.08, 'd', 'Units', 'normalized', ...
    'FontName', 'Arial', 'FontSize', 9.2, 'FontWeight', 'bold', 'Color', C.ink);
text(ax, 0.50, 1.08, '事件扫描得到的覆盖数阶梯', ...
    'Units', 'normalized', 'HorizontalAlignment', 'center', ...
    'FontName', fontName, 'FontSize', 8.2, 'FontWeight', 'bold', ...
    'Color', C.ink, 'Interpreter', 'none');
text(ax, 10.25, 2.18, 'n(t)=2：物理接续', ...
    'HorizontalAlignment', 'center', 'FontName', fontName, 'FontSize', 7.0, ...
    'Color', C.orange, 'Interpreter', 'none');

xlim(ax, [xMin, xMax]);
ylim(ax, [-1.02, 2.45]);
xlabel(ax, '时间 / s', 'FontName', fontName, 'FontSize', 8.2, 'Color', C.ink);
ylabel(ax, '覆盖数  n(t)', 'FontName', fontName, 'FontSize', 8.2, 'Color', C.ink);
set(ax, 'XTick', 5:1:11, 'YTick', [0, 1, 2], 'FontName', fontName, ...
    'FontSize', 7.2, 'TickDir', 'out', 'TickLength', [0.010, 0.010], ...
    'XColor', C.muted, 'YColor', C.muted, 'Color', C.paper, 'Box', 'off');
ax.LineWidth = 0.65;
hold(ax, 'off');
end


function fontName = chooseChineseFont()
preferred = {'Microsoft YaHei', 'SimHei', 'Arial Unicode MS'};
available = listfonts;
fontName = 'Arial';
for k = 1:numel(preferred)
    if any(strcmpi(available, preferred{k}))
        fontName = preferred{k};
        return;
    end
end
end
