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

% Restrained editorial palette. Shape, line style, and direct annotation
% carry event meaning; hue is reserved for structure and warm emphasis.
C.paper = hexColor('#FCFBF8');
C.ink = hexColor('#25313A');
C.muted = hexColor('#6C787F');
C.guide = hexColor('#DDE3E3');
C.panel = hexColor('#F4F5F3');
C.primary = hexColor('#3E6F8F');
C.secondary = hexColor('#5F8375');
C.warm = hexColor('#C1844F');
C.blue = C.primary;
C.teal = C.secondary;
C.coral = C.warm;
C.plum = C.warm;
C.violet = C.primary;
C.bomb = [C.primary; C.secondary; C.primary];

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
    entry = intervals(k, 1);
    exitTime = intervals(k, 2);
    duration = exitTime - entry;
    accent = C.bomb(k, :);
    eventY = [y + 0.09, y - 0.09, y + 0.09, y - 0.09];

    % A tapered coverage lens replaces the usual long Gantt bar. Its width
    % remains the exact interval, while the four nodes preserve causality.
    lensX = linspace(entry, exitTime, 100);
    lensCenter = linspace(eventY(3), eventY(4), numel(lensX));
    lensHalf = 0.105 * sin(pi * (lensX - entry) / duration);
    patch(ax, [lensX, fliplr(lensX)], ...
        [lensCenter + lensHalf, fliplr(lensCenter - lensHalf)], accent, ...
        'FaceAlpha', 0.13, 'EdgeColor', accent, 'LineWidth', 0.70);
    plot(ax, [-0.05, 11.82], [y, y], '-', 'Color', C.guide, 'LineWidth', 0.60);
    drawEventArrow(ax, release(k), eventY(1), detonate(k), eventY(2), C.violet);
    drawEventArrow(ax, detonate(k), eventY(2), entry, eventY(3), C.coral);
    drawEventArrow(ax, entry, eventY(3), exitTime, eventY(4), accent);

    plot(ax, release(k), eventY(1), 'd', 'MarkerSize', 5.4, ...
        'MarkerFaceColor', C.violet, 'MarkerEdgeColor', C.paper, 'LineWidth', 0.7);
    plot(ax, detonate(k), eventY(2), 'o', 'MarkerSize', 5.5, ...
        'MarkerFaceColor', C.coral, 'MarkerEdgeColor', C.paper, 'LineWidth', 0.7);
    plot(ax, entry, eventY(3), '^', 'MarkerSize', 5.9, ...
        'MarkerFaceColor', C.teal, 'MarkerEdgeColor', C.paper, 'LineWidth', 0.7);
    plot(ax, exitTime, eventY(4), 'v', 'MarkerSize', 5.9, ...
        'MarkerFaceColor', C.blue, 'MarkerEdgeColor', C.paper, 'LineWidth', 0.7);

    scatter(ax, -0.73, y, 68, accent, 'filled', ...
        'MarkerEdgeColor', C.paper, 'LineWidth', 0.7);
    text(ax, -0.73, y, sprintf('%d', k), ...
        'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
        'FontName', 'Arial', 'FontSize', 7.0, 'FontWeight', 'bold', ...
        'Color', C.paper, 'Interpreter', 'none');
    text(ax, -0.55, y, '烟幕', ...
        'HorizontalAlignment', 'left', 'VerticalAlignment', 'middle', ...
        'FontName', fontName, 'FontSize', 7.2, 'FontWeight', 'bold', ...
        'Color', C.ink, 'Interpreter', 'none');

    labelEvent(ax, release(k), eventY(1), sprintf('%.3f', release(k)), ...
        +1, C.violet, C.paper, fontName);
    labelEvent(ax, detonate(k), eventY(2), sprintf('%.3f', detonate(k)), ...
        -1, C.coral, C.paper, fontName);
    labelEvent(ax, entry, eventY(3), sprintf('%.3f', entry), ...
        +1, C.teal, C.paper, fontName);
    labelEvent(ax, exitTime, eventY(4), sprintf('%.3f', exitTime), ...
        -1, C.blue, C.paper, fontName);
    if exitTime > 10.8
        durationX = 2.15;
        durationAlign = 'center';
    else
        durationX = 11.76;
        durationAlign = 'right';
    end
    text(ax, durationX, y, sprintf('遮蔽 %.3f s', duration), ...
        'HorizontalAlignment', durationAlign, 'VerticalAlignment', 'middle', ...
        'FontName', fontName, 'FontSize', 7.0, 'FontWeight', 'bold', ...
        'Color', accent, 'Interpreter', 'none');
end

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


function drawEventArrow(ax, x0, y0, x1, y1, color)
dx = x1 - x0;
dy = y1 - y0;
span = hypot(dx, dy);
if span <= 1e-10
    return;
end
quiver(ax, x0, y0, dx, dy, 0, 'Color', color, 'LineStyle', '--', ...
    'LineWidth', 0.80, 'MaxHeadSize', min(0.18, 0.45 / max(span, 0.25)), ...
    'AutoScale', 'off');
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

cardTint = tintColor(mean(C.bomb([oldIndex, newIndex], :), 1), C.paper, 0.055);
rectangle(ax, 'Position', [0.015, 0.035, 0.970, 0.925], ...
    'Curvature', [0.035, 0.035], 'FaceColor', cardTint, ...
    'EdgeColor', C.guide, 'LineWidth', 0.65);

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
cloudColor = C.bomb(indices, :);

lineY = 0.31;
quiver(ax, 0.045, lineY, 0.91, 0, 0, 'Color', C.ink, ...
    'LineWidth', 0.85, 'MaxHeadSize', 0.045, 'AutoScale', 'off');

theta = linspace(0, 2 * pi, 160);
for j = 1:2
    yc = lineY + ry * dPerp(j) / radius;
    xCircle = xCenter(j) + rx * cos(theta);
    yCircle = yc + ry * sin(theta);
    fill(ax, xCircle, yCircle, tintColor(cloudColor(j, :), C.paper, 0.14), ...
        'FaceAlpha', 0.92, 'EdgeColor', cloudColor(j, :), 'LineWidth', 1.05);
    plot(ax, xCenter(j), yc, '.', 'Color', cloudColor(j, :), 'MarkerSize', 7.0);
    plot(ax, [xCenter(j), xCenter(j)], [lineY, yc], ':', ...
        'Color', cloudColor(j, :), 'LineWidth', 0.9);
    text(ax, xCenter(j), yc + 0.32 * ry, sprintf('d_\\perp=%.2f m', dPerp(j)), ...
        'HorizontalAlignment', 'center', 'FontName', 'Arial', 'FontSize', 7.0, ...
        'FontWeight', 'bold', 'Color', cloudColor(j, :), 'Interpreter', 'tex');
end

text(ax, xCenter(1), 0.79, '旧云未退出', ...
    'HorizontalAlignment', 'center', 'FontName', fontName, 'FontSize', 7.4, ...
    'FontWeight', 'bold', 'Color', cloudColor(1, :), 'Interpreter', 'none');
text(ax, xCenter(2), 0.79, '新云已进入', ...
    'HorizontalAlignment', 'center', 'FontName', fontName, 'FontSize', 7.4, ...
    'FontWeight', 'bold', 'Color', cloudColor(2, :), 'Interpreter', 'none');
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

% Shade event states rather than drawing a second set of interval bars.
% Single-cloud regions use cool tints; physical hand-offs use warm emphasis.
for k = 1:(numel(breaks) - 1)
    if counts(k) == 0
        continue;
    end
    probe = 0.5 * (breaks(k) + breaks(k + 1));
    active = find(intervals(:, 1) <= probe & probe < intervals(:, 2));
    if numel(active) == 1
        fillColor = tintColor(C.bomb(active, :), C.paper, 0.10);
    else
        fillColor = tintColor(C.warm, C.paper, 0.12);
    end
    patch(ax, [breaks(k), breaks(k + 1), breaks(k + 1), breaks(k)], ...
        [0, 0, counts(k), counts(k)], fillColor, ...
        'EdgeColor', 'none', 'FaceAlpha', 0.96);
end
stairs(ax, breaks, counts, '-', 'Color', C.ink, 'LineWidth', 1.65);

% Entry/exit glyphs make the staircase explicitly event-driven.
for k = 1:3
    plot(ax, [intervals(k, 1), intervals(k, 1)], [0, 2.08], ':', ...
        'Color', tintColor(C.teal, C.paper, 0.40), 'LineWidth', 0.65);
    plot(ax, intervals(k, 1), 0, '^', 'MarkerSize', 5.2, ...
        'MarkerFaceColor', C.teal, 'MarkerEdgeColor', C.paper, 'LineWidth', 0.6);
    plot(ax, intervals(k, 2), 0, 'v', 'MarkerSize', 5.2, ...
        'MarkerFaceColor', C.blue, 'MarkerEdgeColor', C.paper, 'LineWidth', 0.6);
end

% Emphasize true double-coverage states as short event segments, not bars.
for k = 1:(numel(breaks) - 1)
    if counts(k) == 2
        plot(ax, [breaks(k), breaks(k + 1)], [2, 2], '-', ...
            'Color', C.plum, 'LineWidth', 3.0);
        plot(ax, [breaks(k), breaks(k + 1)], [2, 2], 'o', ...
            'Color', C.plum, 'MarkerFaceColor', C.paper, 'MarkerSize', 3.3);
    end
end

% Exact union and overlap brackets make the event arithmetic inspectable.
plot(ax, unionInterval, [-0.24, -0.24], '-', 'Color', C.teal, 'LineWidth', 2.4);
plot(ax, unionInterval, [-0.24, -0.24], 'o', 'Color', C.teal, ...
    'MarkerFaceColor', C.paper, 'MarkerSize', 3.5);
text(ax, mean(unionInterval), -0.08, sprintf('D_1 = %.3f s', unionDuration), ...
    'HorizontalAlignment', 'center', 'FontName', 'Arial', 'FontSize', 7.0, ...
    'FontWeight', 'bold', 'Color', C.teal, 'Interpreter', 'tex');

for k = 1:2
    left = intervals(k + 1, 1);
    right = intervals(k, 2);
    y = -0.62;
    overlapColor = C.bomb(k + 1, :);
    plot(ax, [left, right], [y, y], '-', 'Color', overlapColor, 'LineWidth', 1.05);
    plot(ax, [left, left], [y - 0.05, y + 0.05], '-', 'Color', overlapColor, 'LineWidth', 0.9);
    plot(ax, [right, right], [y - 0.05, y + 0.05], '-', 'Color', overlapColor, 'LineWidth', 0.9);
    text(ax, mean([left, right]), y - 0.09, ...
        sprintf('I%d∩I%d = %.3f s', k, k + 1, right - left), ...
        'HorizontalAlignment', 'center', 'VerticalAlignment', 'top', ...
        'FontName', fontName, 'FontSize', 7.0, 'Color', overlapColor, ...
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
    'Color', C.plum, 'Interpreter', 'none');

xlim(ax, [xMin, xMax]);
ylim(ax, [-1.02, 2.45]);
xlabel(ax, '时间 / s', 'FontName', fontName, 'FontSize', 8.2, 'Color', C.ink);
ylabel(ax, '覆盖数  n(t)', 'FontName', fontName, 'FontSize', 8.2, 'Color', C.ink);
set(ax, 'XTick', 5:1:11, 'YTick', [0, 1, 2], 'FontName', fontName, ...
    'FontSize', 7.2, 'TickDir', 'out', 'TickLength', [0.010, 0.010], ...
    'XColor', C.muted, 'YColor', C.muted, 'Color', C.panel, 'Box', 'off');
ax.LineWidth = 0.65;
ax.YGrid = 'on';
ax.GridColor = C.guide;
ax.GridAlpha = 0.55;
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


function color = tintColor(base, paper, strength)
color = (1 - strength) .* paper + strength .* base;
end


function rgb = hexColor(code)
code = char(erase(string(code), '#'));
rgb = [hex2dec(code(1:2)), hex2dec(code(3:4)), hex2dec(code(5:6))] / 255;
end
