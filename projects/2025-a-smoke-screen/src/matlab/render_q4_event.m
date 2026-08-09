function render_q4_event()
%RENDER_Q4_EVENT Render Q4 action events and n(t) on a shared time axis.

% The figure is intentionally data-led: the upper panel is a three-row
% release/detonation/entry/exit event grid; the lower panel is the exact
% coverage-count staircase.  No cards, rounded nodes, or decorative bubbles
% are used, so every mark encodes a verified time or interval.

scriptDir = fileparts(mfilename('fullpath'));
projectDir = fileparts(fileparts(scriptDir));
jsonPath = fullfile(projectDir, 'validation', 'q3_q5_independent.json');
outDir = fullfile(projectDir, 'figures');

assert(isfile(jsonPath), 'Validation data not found: %s', jsonPath);
if ~isfolder(outDir)
    mkdir(outDir);
end

payload = jsondecode(fileread(jsonPath));
q4 = payload.results.Q4;
plans = q4.plans;
assert(numel(plans) == 3, 'Q4 event figure expects exactly three plans.');

release = reshape([plans.release_time], [], 1);
detonate = reshape([plans.explosion_time], [], 1);
intervals = zeros(3, 2);
for k = 1:3
    interval = plans(k).exact_centerline_intervals;
    assert(size(interval, 1) == 1 && size(interval, 2) == 2, ...
        'Each Q4 plan must have exactly one centerline interval.');
    intervals(k, :) = interval(1, :);
end

assert(all(release <= detonate + 1e-12), 'Release must precede detonation.');
assert(all(detonate <= intervals(:, 1) + 1e-12), ...
    'Detonation must not occur after coverage entry.');
assert(all(intervals(1:2, 2) < intervals(2:3, 1)), ...
    'The selected Q4 windows are expected to be disjoint.');

durations = intervals(:, 2) - intervals(:, 1);
gaps = intervals(2:3, 1) - intervals(1:2, 2);
unionDuration = sum(durations);
assert(abs(unionDuration - q4.exact_centerline_objective) < 1e-8, ...
    'Event-window sum does not match the verified Q4 objective.');

% A colourblind-aware editorial palette. Event type uses shape as well as
% colour, while UAV identity uses line style, so grayscale remains legible.
C.paper = hexColor('#FFFFFF');
C.ink = hexColor('#1E2A32');
C.muted = hexColor('#647078');
C.guide = hexColor('#D6DEE1');
C.primary = hexColor('#2F6079');
C.secondary = hexColor('#59636A');
C.warm = hexColor('#B5782F');
C.wine = hexColor('#8B4E5A');
C.activeFill = tintColor(C.primary, C.paper, 0.13);
C.gapFill = tintColor(C.warm, C.paper, 0.16);

fontName = chooseChineseFont();
fig = figure('Visible', 'off', 'Color', C.paper, ...
    'Units', 'inches', 'Position', [0.5, 0.5, 6.20, 4.85], ...
    'PaperPositionMode', 'auto');

axEvents = axes(fig, 'Position', [0.105, 0.575, 0.855, 0.325]);
axComposition = axes(fig, 'Position', [0.105, 0.125, 0.855, 0.315]);
xLimits = [-1.25, 47.0];

drawEventGrid(axEvents, release, detonate, intervals, durations, ...
    xLimits, C, fontName);
drawGapComposition(axComposition, intervals, gaps, unionDuration, ...
    xLimits, C, fontName);
linkaxes([axEvents, axComposition], 'x');

pngPath = fullfile(outDir, 'q4_temporal_synergy.png');
pdfPath = fullfile(outDir, 'q4_temporal_synergy.pdf');
svgPath = fullfile(outDir, 'q4_temporal_synergy.svg');
exportgraphics(fig, pngPath, 'Resolution', 420, 'BackgroundColor', C.paper);
exportgraphics(fig, pdfPath, 'ContentType', 'vector', 'BackgroundColor', C.paper);
try
    exportgraphics(fig, svgPath, 'ContentType', 'vector', 'BackgroundColor', C.paper);
catch
    print(fig, svgPath, '-dsvg', '-vector');
end

info = imfinfo(pngPath);
assert(info.Width >= 2000 && info.Height >= 1600, ...
    'Q4 PNG export is below the intended publication resolution.');
assert(isfile(pdfPath) && isfile(svgPath), 'Q4 vector export is incomplete.');
close(fig);

fprintf('Rendered Q4 shared-axis event evidence:\n  %s\n  %s\n  %s\n', ...
    pngPath, pdfPath, svgPath);
end


function drawEventGrid(ax, release, detonate, intervals, durations, ...
        xLimits, C, fontName)
hold(ax, 'on');
rows = [3, 2, 1];
lineStyles = {'-', '--', '-.'};
rowColors = repmat(C.primary, 3, 1);

for k = 1:3
    y = rows(k);
    yRelease = y + 0.10;
    yDetonate = y - 0.10;
    yActive = y + 0.02;
    entry = intervals(k, 1);
    exitTime = intervals(k, 2);

    plot(ax, [0, 46], [y, y], '-', 'Color', C.guide, 'LineWidth', 0.70);
    drawArrow(ax, release(k), yRelease, detonate(k), yDetonate, C.muted, '--');
    drawArrow(ax, detonate(k), yDetonate, entry, yActive, C.muted, ':');

    patch(ax, [entry, exitTime, exitTime, entry], ...
        [yActive - 0.085, yActive - 0.085, yActive + 0.085, yActive + 0.085], ...
        tintColor(rowColors(k, :), C.paper, 0.105), ...
        'EdgeColor', 'none');
    plot(ax, [entry, exitTime], [yActive, yActive], lineStyles{k}, ...
        'Color', rowColors(k, :), 'LineWidth', 2.35);

    plot(ax, release(k), yRelease, 'd', 'MarkerSize', 5.3, ...
        'MarkerFaceColor', C.paper, 'MarkerEdgeColor', C.ink, 'LineWidth', 1.0);
    plot(ax, detonate(k), yDetonate, 'o', 'MarkerSize', 5.2, ...
        'MarkerFaceColor', C.warm, 'MarkerEdgeColor', C.paper, 'LineWidth', 0.7);
    plot(ax, entry, yActive, '^', 'MarkerSize', 5.7, ...
        'MarkerFaceColor', C.primary, 'MarkerEdgeColor', C.paper, 'LineWidth', 0.7);
    plot(ax, exitTime, yActive, 'v', 'MarkerSize', 5.7, ...
        'MarkerFaceColor', C.paper, 'MarkerEdgeColor', C.ink, 'LineWidth', 1.0);

    labelTime(ax, release(k), yRelease + 0.26, release(k), C.ink, fontName, 'bottom');
    labelTime(ax, detonate(k), yDetonate - 0.18, detonate(k), C.warm, fontName, 'top');
    labelTime(ax, entry, yActive + 0.12, entry, C.primary, fontName, 'bottom');
    labelTime(ax, exitTime, yActive - 0.19, exitTime, C.ink, fontName, 'top');

    durationX = intervals(k, 1) + 0.70 * durations(k);
    text(ax, durationX, yActive + 0.30, ...
        sprintf('I_%d: %.3f s', k, durations(k)), ...
        'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom', ...
        'FontName', fontName, 'FontSize', 7.1, 'FontWeight', 'bold', ...
        'Color', rowColors(k, :), 'Interpreter', 'tex', 'Clipping', 'off');
end

text(ax, 0.00, 1.10, 'a', 'Units', 'normalized', ...
    'FontName', 'Arial', 'FontSize', 9.2, 'FontWeight', 'bold', 'Color', C.ink);
text(ax, 0.42, 1.10, '三机事件栅格：投放—起爆—进入—退出', ...
    'Units', 'normalized', 'HorizontalAlignment', 'center', ...
    'FontName', fontName, 'FontSize', 8.4, 'FontWeight', 'bold', ...
    'Color', C.ink, 'Interpreter', 'none');
text(ax, 0.995, 1.10, '◇ 投放   ● 起爆   ▲ 进入   ▽ 退出', ...
    'Units', 'normalized', 'HorizontalAlignment', 'right', ...
    'FontName', fontName, 'FontSize', 7.0, 'Color', C.muted, ...
    'Interpreter', 'none');

xlim(ax, xLimits);
ylim(ax, [0.43, 3.60]);
set(ax, 'XTick', 0:5:45, 'XTickLabel', [], ...
    'YTick', [1, 2, 3], 'YTickLabel', {'FY3', 'FY2', 'FY1'}, ...
    'FontName', fontName, 'FontSize', 7.2, 'TickDir', 'out', ...
    'TickLength', [0.010, 0.010], 'XColor', C.muted, ...
    'YColor', C.ink, 'Color', C.paper, 'Box', 'off');
ax.LineWidth = 0.65;
ax.XGrid = 'on';
ax.GridColor = C.guide;
ax.GridAlpha = 0.50;
hold(ax, 'off');
end


function drawGapComposition(ax, intervals, gaps, unionDuration, ...
        xLimits, C, fontName)
hold(ax, 'on');
rowColors = repmat(C.primary, 3, 1);
y = 0.62;

plot(ax, [0, 46], [y, y], '-', 'Color', C.guide, 'LineWidth', 0.85);
for k = 1:3
    entry = intervals(k, 1);
    exitTime = intervals(k, 2);
    plot(ax, [entry, exitTime], [y, y], '-', ...
        'Color', rowColors(k, :), 'LineWidth', 5.4);
    plot(ax, entry, y, '>', 'MarkerSize', 5.5, ...
        'MarkerFaceColor', C.paper, 'MarkerEdgeColor', rowColors(k, :), ...
        'LineWidth', 0.95);
    plot(ax, exitTime, y, '<', 'MarkerSize', 5.5, ...
        'MarkerFaceColor', rowColors(k, :), 'MarkerEdgeColor', C.paper, ...
        'LineWidth', 0.65);
    text(ax, mean(intervals(k, :)), y + 0.26, ...
        sprintf('I_%d  %.3f s', k, diff(intervals(k, :))), ...
        'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom', ...
        'FontName', fontName, 'FontSize', 7.3, 'FontWeight', 'bold', ...
        'Color', rowColors(k, :), 'Interpreter', 'tex');
end

for k = 1:2
    xLeft = intervals(k, 2);
    xRight = intervals(k + 1, 1);
    plot(ax, [xLeft, xRight], [y, y], '--', ...
        'Color', C.warm, 'LineWidth', 1.35);
    drawDoubleArrow(ax, xLeft, xRight, y - 0.28, C.warm);
    text(ax, mean([xLeft, xRight]), y - 0.39, ...
        sprintf('g_%d = %.3f s', k, gaps(k)), ...
        'HorizontalAlignment', 'center', 'VerticalAlignment', 'top', ...
        'FontName', fontName, 'FontSize', 7.2, 'FontWeight', 'bold', ...
        'Color', C.warm, 'Interpreter', 'tex');
end

text(ax, 0.00, 1.10, 'b', 'Units', 'normalized', ...
    'FontName', 'Arial', 'FontSize', 9.2, 'FontWeight', 'bold', 'Color', C.ink);
text(ax, 0.50, 1.10, '时间组成带：有效窗口与内部空窗分解', ...
    'Units', 'normalized', 'HorizontalAlignment', 'center', ...
    'FontName', fontName, 'FontSize', 8.4, 'FontWeight', 'bold', ...
    'Color', C.ink, 'Interpreter', 'none');
text(ax, 0.995, 1.10, ...
    sprintf('D_1 = |I_1| + |I_2| + |I_3| = %.3f s', unionDuration), ...
    'Units', 'normalized', 'HorizontalAlignment', 'right', ...
    'FontName', fontName, 'FontSize', 7.2, 'FontWeight', 'bold', ...
    'Color', C.primary, 'Interpreter', 'tex');

xlim(ax, xLimits);
ylim(ax, [-0.05, 1.12]);
xlabel(ax, '任务时刻  t / s', 'FontName', fontName, 'FontSize', 8.0, 'Color', C.ink);
set(ax, 'XTick', 0:5:45, 'YTick', [], ...
    'FontName', fontName, 'FontSize', 7.2, 'TickDir', 'out', ...
    'TickLength', [0.010, 0.010], 'XColor', C.muted, ...
    'YColor', C.muted, 'Color', C.paper, 'Box', 'off');
ax.LineWidth = 0.65;
ax.XGrid = 'on';
ax.GridColor = C.guide;
ax.GridAlpha = 0.50;
hold(ax, 'off');
end


function drawCoverageCount(ax, intervals, gaps, unionDuration, ...
        xLimits, C, fontName)
hold(ax, 'on');

for k = 1:3
    patch(ax, [intervals(k, 1), intervals(k, 2), intervals(k, 2), intervals(k, 1)], ...
        [0, 0, 1, 1], C.activeFill, 'EdgeColor', 'none');
end
for k = 1:2
    patch(ax, [intervals(k, 2), intervals(k + 1, 1), ...
        intervals(k + 1, 1), intervals(k, 2)], ...
        [-0.54, -0.54, -0.19, -0.19], C.gapFill, 'EdgeColor', 'none');
end

breaks = [xLimits(1), reshape(intervals.', 1, []), xLimits(2)];
counts = zeros(size(breaks));
for k = 1:(numel(breaks) - 1)
    probe = 0.5 * (breaks(k) + breaks(k + 1));
    counts(k) = sum(intervals(:, 1) <= probe & probe < intervals(:, 2));
end
counts(end) = 0;
stairs(ax, breaks, counts, '-', 'Color', C.ink, 'LineWidth', 1.65);

for k = 1:3
    plot(ax, [intervals(k, 1), intervals(k, 1)], [0, 1.08], ':', ...
        'Color', tintColor(C.secondary, C.paper, 0.50), 'LineWidth', 0.65);
    plot(ax, intervals(k, 1), 0, '^', 'MarkerSize', 5.3, ...
        'MarkerFaceColor', C.secondary, 'MarkerEdgeColor', C.paper, 'LineWidth', 0.6);
    plot(ax, intervals(k, 2), 0, 'v', 'MarkerSize', 5.3, ...
        'MarkerFaceColor', C.paper, 'MarkerEdgeColor', C.primary, 'LineWidth', 0.9);
    text(ax, mean(intervals(k, :)), 0.53, sprintf('I_%d', k), ...
        'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
        'FontName', 'Arial', 'FontSize', 7.2, 'FontWeight', 'bold', ...
        'Color', C.primary, 'Interpreter', 'tex');
end

for k = 1:2
    xLeft = intervals(k, 2);
    xRight = intervals(k + 1, 1);
    drawDoubleArrow(ax, xLeft, xRight, -0.37, C.warm);
    text(ax, mean([xLeft, xRight]), -0.29, ...
        sprintf('g_%d = %.3f s', k, gaps(k)), ...
        'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom', ...
        'FontName', fontName, 'FontSize', 7.1, 'FontWeight', 'bold', ...
        'Color', C.warm, 'Interpreter', 'tex');
end

text(ax, 0.00, 1.10, 'b', 'Units', 'normalized', ...
    'FontName', 'Arial', 'FontSize', 9.2, 'FontWeight', 'bold', 'Color', C.ink);
text(ax, 0.50, 1.10, '共享时间轴上的覆盖阶梯与内部空窗', ...
    'Units', 'normalized', 'HorizontalAlignment', 'center', ...
    'FontName', fontName, 'FontSize', 8.4, 'FontWeight', 'bold', ...
    'Color', C.ink, 'Interpreter', 'none');
text(ax, 0.995, 1.10, ...
    sprintf('D_1 = |I_1| + |I_2| + |I_3| = %.3f s', unionDuration), ...
    'Units', 'normalized', 'HorizontalAlignment', 'right', ...
    'FontName', fontName, 'FontSize', 7.2, 'FontWeight', 'bold', ...
    'Color', C.primary, 'Interpreter', 'tex');

xlim(ax, xLimits);
ylim(ax, [-0.64, 1.40]);
xlabel(ax, '任务时刻  t / s', 'FontName', fontName, 'FontSize', 8.0, 'Color', C.ink);
ylabel(ax, '覆盖重数  n(t)', 'FontName', fontName, 'FontSize', 8.0, 'Color', C.ink);
set(ax, 'XTick', 0:5:45, 'YTick', [0, 1], ...
    'FontName', fontName, 'FontSize', 7.2, 'TickDir', 'out', ...
    'TickLength', [0.010, 0.010], 'XColor', C.muted, ...
    'YColor', C.muted, 'Color', C.paper, 'Box', 'off');
ax.LineWidth = 0.65;
ax.XGrid = 'on';
ax.YGrid = 'on';
ax.GridColor = C.guide;
ax.GridAlpha = 0.50;
hold(ax, 'off');
end


function drawArrow(ax, x0, y0, x1, y1, color, lineStyle)
dx = x1 - x0;
dy = y1 - y0;
span = hypot(dx, dy);
if span <= 1e-12
    return;
end
quiver(ax, x0, y0, dx, dy, 0, 'Color', color, ...
    'LineStyle', lineStyle, 'LineWidth', 0.80, ...
    'MaxHeadSize', min(0.16, 0.70 / max(span, 0.25)), 'AutoScale', 'off');
end


function drawDoubleArrow(ax, xLeft, xRight, y, color)
span = xRight - xLeft;
if span <= 1e-12
    return;
end
quiver(ax, xLeft, y, span, 0, 0, 'Color', color, ...
    'LineStyle', '-', 'LineWidth', 0.85, ...
    'MaxHeadSize', min(0.12, 0.80 / span), 'AutoScale', 'off');
quiver(ax, xRight, y, -span, 0, 0, 'Color', color, ...
    'LineStyle', '-', 'LineWidth', 0.85, ...
    'MaxHeadSize', min(0.12, 0.80 / span), 'AutoScale', 'off');
end


function labelTime(ax, x, y, value, color, fontName, verticalAlignment)
text(ax, x, y, sprintf('%.3f', value), ...
    'HorizontalAlignment', 'center', 'VerticalAlignment', verticalAlignment, ...
    'FontName', fontName, 'FontSize', 7.0, 'Color', color, ...
    'BackgroundColor', [1, 1, 1], 'Margin', 0.5, 'Interpreter', 'none', ...
    'Clipping', 'off');
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
