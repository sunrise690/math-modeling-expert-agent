function render_q3_event()
%RENDER_Q3_EVENT Render Q3 intervals, their union, and n(t) on one time axis.

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
assert(numel(plans) == 3, 'Q3 event figure expects exactly three smoke bombs.');

release = reshape([plans.release_time], [], 1);
detonate = reshape([plans.explosion_time], [], 1);
intervals = zeros(3, 2);
for k = 1:3
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
unionInterval = reshape(unionInterval, 1, 2);
unionDuration = diff(unionInterval);
overlaps = [intervals(1, 2) - intervals(2, 1), ...
    intervals(2, 2) - intervals(3, 1)];
assert(all(overlaps > 0), 'The three Q3 intervals must form two positive overlaps.');
assert(abs(sum(diff(intervals, 1, 2)) - sum(overlaps) - unionDuration) < 1e-8, ...
    'Q3 interval arithmetic is inconsistent with the verified union.');

% Preserve the physical hand-off checks without drawing redundant cloud circles.
validateHandoff(plans, intervals, 1, 2, payload.model);
validateHandoff(plans, intervals, 2, 3, payload.model);

C.paper = [1, 1, 1];
C.ink = hexColor('#25313A');
C.muted = hexColor('#6C787F');
C.guide = hexColor('#DDE3E3');
C.primary = hexColor('#3E6F8F');
C.secondary = hexColor('#5F8375');
C.warm = hexColor('#C1844F');
C.wine = hexColor('#9B5B64');
C.coolFill = tintColor(C.primary, C.paper, 0.075);
C.warmFill = tintColor(C.warm, C.paper, 0.105);

fontName = chooseChineseFont();
fig = figure('Visible', 'off', 'Color', C.paper, ...
    'Units', 'inches', 'Position', [0.5, 0.5, 6.20, 4.75], ...
    'PaperPositionMode', 'auto');

axEvents = axes(fig, 'Position', [0.105, 0.575, 0.855, 0.325]);
axCount = axes(fig, 'Position', [0.105, 0.125, 0.855, 0.315]);
xLimits = [-0.60, 12.05];

drawEventGrid(axEvents, release, detonate, intervals, xLimits, C, fontName);
drawCoverageCount(axCount, intervals, unionInterval, unionDuration, ...
    overlaps, xLimits, C, fontName);
linkaxes([axEvents, axCount], 'x');

pngPath = fullfile(outDir, 'q3_interval_union.png');
pdfPath = fullfile(outDir, 'q3_interval_union.pdf');
svgPath = fullfile(outDir, 'q3_interval_union.svg');
exportgraphics(fig, pngPath, 'Resolution', 420, 'BackgroundColor', C.paper);
exportgraphics(fig, pdfPath, 'ContentType', 'vector', 'BackgroundColor', C.paper);
try
    exportgraphics(fig, svgPath, 'ContentType', 'vector', 'BackgroundColor', C.paper);
catch
    print(fig, svgPath, '-dsvg', '-vector');
end
close(fig);

pngInfo = imfinfo(pngPath);
assert(pngInfo.Width >= 2200 && pngInfo.Height >= 1600, ...
    'Q3 PNG is smaller than the intended manuscript QA raster.');
assert(isfile(pdfPath) && isfile(svgPath), 'Q3 vector export failed.');

fprintf('Rendered Q3 shared-axis event figure:\n  %s\n  %s\n  %s\n', ...
    pngPath, pdfPath, svgPath);
fprintf('  union %.6f s | overlaps %.6f and %.6f s\n', ...
    unionDuration, overlaps(1), overlaps(2));
end


function drawEventGrid(ax, release, detonate, intervals, xLimits, C, fontName)
hold(ax, 'on');
rows = [3, 2, 1];
lineStyles = {'-', '--', '-.'};
rowColors = [C.primary; C.secondary; C.wine];

for k = 1:3
    y = rows(k);
    yRelease = y + 0.11;
    yDetonate = y - 0.11;
    yActive = y + 0.035;
    entry = intervals(k, 1);
    exitTime = intervals(k, 2);

    plot(ax, [0, 11.75], [y, y], '-', 'Color', C.guide, 'LineWidth', 0.65);
    drawArrow(ax, release(k), yRelease, detonate(k), yDetonate, C.muted, '--');
    drawArrow(ax, detonate(k), yDetonate, entry, yActive, C.muted, ':');
    patch(ax, [entry, exitTime, exitTime, entry], ...
        [yActive - 0.08, yActive - 0.08, yActive + 0.08, yActive + 0.08], ...
        tintColor(rowColors(k, :), C.paper, 0.10), 'EdgeColor', 'none');
    plot(ax, [entry, exitTime], [yActive, yActive], lineStyles{k}, ...
        'Color', rowColors(k, :), 'LineWidth', 2.25);

    plot(ax, release(k), yRelease, 'd', 'MarkerSize', 5.3, ...
        'MarkerFaceColor', C.paper, 'MarkerEdgeColor', C.ink, 'LineWidth', 1.0);
    plot(ax, detonate(k), yDetonate, 'o', 'MarkerSize', 5.2, ...
        'MarkerFaceColor', C.warm, 'MarkerEdgeColor', C.paper, 'LineWidth', 0.7);
    plot(ax, entry, yActive, '^', 'MarkerSize', 5.7, ...
        'MarkerFaceColor', C.secondary, 'MarkerEdgeColor', C.paper, 'LineWidth', 0.7);
    plot(ax, exitTime, yActive, 'v', 'MarkerSize', 5.7, ...
        'MarkerFaceColor', C.paper, 'MarkerEdgeColor', rowColors(k, :), 'LineWidth', 1.0);

    labelTime(ax, release(k), yRelease + 0.18, release(k), C.ink, fontName, 'bottom');
    labelTime(ax, detonate(k), yDetonate - 0.18, detonate(k), C.warm, fontName, 'top');
    labelTime(ax, entry, yActive + 0.19, entry, C.secondary, fontName, 'bottom');
    labelTime(ax, exitTime, yActive - 0.19, exitTime, rowColors(k, :), fontName, 'top');
end

text(ax, 0.00, 1.10, 'a', 'Units', 'normalized', ...
    'FontName', 'Arial', 'FontSize', 9.2, 'FontWeight', 'bold', 'Color', C.ink);
text(ax, 0.50, 1.10, '三枚烟幕弹的事件时刻与有效区间', ...
    'Units', 'normalized', 'HorizontalAlignment', 'center', ...
    'FontName', fontName, 'FontSize', 8.4, 'FontWeight', 'bold', ...
    'Color', C.ink, 'Interpreter', 'none');
text(ax, 0.995, 1.10, '◇ 投放   ● 起爆   ▲ 进入   ▽ 退出', ...
    'Units', 'normalized', 'HorizontalAlignment', 'right', ...
    'FontName', fontName, 'FontSize', 7.0, 'Color', C.muted, ...
    'Interpreter', 'none');

xlim(ax, xLimits);
ylim(ax, [0.45, 3.58]);
set(ax, 'XTick', 0:2:12, 'XTickLabel', [], ...
    'YTick', [1, 2, 3], 'YTickLabel', {'烟幕弹 3', '烟幕弹 2', '烟幕弹 1'}, ...
    'FontName', fontName, 'FontSize', 7.2, 'TickDir', 'out', ...
    'TickLength', [0.010, 0.010], 'XColor', C.muted, ...
    'YColor', C.muted, 'Color', C.paper, 'Box', 'off');
ax.LineWidth = 0.65;
ax.XGrid = 'on';
ax.GridColor = C.guide;
ax.GridAlpha = 0.50;
hold(ax, 'off');
end


function drawCoverageCount(ax, intervals, unionInterval, unionDuration, ...
        overlaps, xLimits, C, fontName)
hold(ax, 'on');
eventTimes = sort([intervals(:, 1); intervals(:, 2)]).';
breaks = [xLimits(1), eventTimes, xLimits(2)];
counts = zeros(size(breaks));
for k = 1:(numel(breaks) - 1)
    probe = 0.5 * (breaks(k) + breaks(k + 1));
    counts(k) = sum(intervals(:, 1) <= probe & probe < intervals(:, 2));
    if counts(k) > 0
        if counts(k) == 1
            fillColor = C.coolFill;
        else
            fillColor = C.warmFill;
        end
        patch(ax, [breaks(k), breaks(k + 1), breaks(k + 1), breaks(k)], ...
            [0, 0, counts(k), counts(k)], fillColor, 'EdgeColor', 'none');
    end
end
counts(end) = 0;

stairs(ax, breaks, counts, '-', 'Color', C.ink, 'LineWidth', 1.55);
for k = 1:(numel(breaks) - 1)
    if counts(k) == 2
        plot(ax, [breaks(k), breaks(k + 1)], [2, 2], '-', ...
            'Color', C.warm, 'LineWidth', 2.5);
    end
end

for k = 1:3
    plot(ax, [intervals(k, 1), intervals(k, 1)], [0, 2.08], ':', ...
        'Color', tintColor(C.secondary, C.paper, 0.42), 'LineWidth', 0.65);
    plot(ax, intervals(k, 1), 0, '^', 'MarkerSize', 5.2, ...
        'MarkerFaceColor', C.secondary, 'MarkerEdgeColor', C.paper, 'LineWidth', 0.6);
    plot(ax, intervals(k, 2), 0, 'v', 'MarkerSize', 5.2, ...
        'MarkerFaceColor', C.paper, 'MarkerEdgeColor', C.primary, 'LineWidth', 0.9);
end

unionY = -0.24;
plot(ax, unionInterval, [unionY, unionY], '-', 'Color', C.primary, 'LineWidth', 2.2);
plot(ax, unionInterval, [unionY, unionY], 'o', 'Color', C.primary, ...
    'MarkerFaceColor', C.paper, 'MarkerSize', 3.8);
text(ax, mean(unionInterval), unionY - 0.13, ...
    sprintf('去重并集  [%.3f, %.3f] s，D_1 = %.3f s', ...
    unionInterval(1), unionInterval(2), unionDuration), ...
    'HorizontalAlignment', 'center', 'VerticalAlignment', 'top', ...
    'FontName', fontName, 'FontSize', 7.2, 'FontWeight', 'bold', ...
    'Color', C.primary, 'Interpreter', 'tex');

% One compact overlap note replaces the two repeated circular hand-off panels.
text(ax, 0.020, 0.91, sprintf('局部交叠：I_1\\cap I_2=%.3f s；I_2\\cap I_3=%.3f s', ...
    overlaps(1), overlaps(2)), 'Units', 'normalized', ...
    'HorizontalAlignment', 'left', 'VerticalAlignment', 'top', ...
    'FontName', fontName, 'FontSize', 7.0, 'Color', C.warm, ...
    'Interpreter', 'tex');

text(ax, 0.00, 1.10, 'b', 'Units', 'normalized', ...
    'FontName', 'Arial', 'FontSize', 9.2, 'FontWeight', 'bold', 'Color', C.ink);
text(ax, 0.50, 1.10, '共享时间轴上的区间并集与覆盖重数', ...
    'Units', 'normalized', 'HorizontalAlignment', 'center', ...
    'FontName', fontName, 'FontSize', 8.4, 'FontWeight', 'bold', ...
    'Color', C.ink, 'Interpreter', 'none');

xlim(ax, xLimits);
ylim(ax, [-0.62, 2.38]);
xlabel(ax, '任务时刻  t / s', 'FontName', fontName, 'FontSize', 8.0, 'Color', C.ink);
ylabel(ax, '覆盖重数  n(t)', 'FontName', fontName, 'FontSize', 8.0, 'Color', C.ink);
set(ax, 'XTick', 0:2:12, 'YTick', [0, 1, 2], ...
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
    'MaxHeadSize', min(0.18, 0.42 / max(span, 0.25)), 'AutoScale', 'off');
end


function labelTime(ax, x, y, value, color, fontName, verticalAlignment)
text(ax, x, y, sprintf('%.3f', value), ...
    'HorizontalAlignment', 'center', 'VerticalAlignment', verticalAlignment, ...
    'FontName', fontName, 'FontSize', 7.0, 'Color', color, ...
    'BackgroundColor', [1, 1, 1], 'Margin', 0.5, 'Interpreter', 'none', ...
    'Clipping', 'off');
end


function validateHandoff(plans, intervals, oldIndex, newIndex, model)
tEnter = intervals(newIndex, 1);
tExit = intervals(oldIndex, 2);
assert(tExit > tEnter, 'The selected Q3 clouds must overlap at each hand-off.');
tMid = 0.5 * (tEnter + tExit);

m0 = [20000, 0, 2000];
missile = m0 - 300 * m0 / norm(m0) * tMid;
target = reshape(model.target_centerline_point, 1, 3);
sightline = target - missile;
radius = model.smoke_radius_m;

for index = [oldIndex, newIndex]
    plan = plans(index);
    cloud = reshape(plan.explosion_position, 1, 3);
    cloud(3) = cloud(3) - model.smoke_sink_speed_m_s * ...
        (tMid - plan.explosion_time);
    lambda = max(0, min(1, dot(cloud - missile, sightline) / dot(sightline, sightline)));
    foot = missile + lambda * sightline;
    assert(norm(cloud - foot) <= radius + 1e-6, ...
        'Both Q3 clouds must intersect the finite sightline at hand-off.');
end
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
