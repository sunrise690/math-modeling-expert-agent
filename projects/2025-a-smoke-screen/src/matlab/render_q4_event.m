function render_q4_event()
%RENDER_Q4_EVENT Render the verified Q4 relay as event-specific evidence.
%
% The graphic avoids Gantt bars.  Three compact action cards show the
% release -> detonation -> entry -> exit chain of each UAV, while three
% short state panels preserve the true time scale inside each coverage
% window.  The two inactive gaps are shown explicitly between panels.

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
heading = reshape([plans.heading_deg], [], 1);
speed = reshape([plans.speed], [], 1);
intervals = zeros(3, 2);
for k = 1:3
    interval = plans(k).exact_centerline_intervals;
    assert(size(interval, 1) == 1 && size(interval, 2) == 2, ...
        'Each Q4 plan must have exactly one centreline interval.');
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

% Low-saturation, colour-blind-safe editorial palette.  Marker shape also
% carries event meaning, so the figure remains readable in grayscale.
C.paper = [0.992, 0.992, 0.986];
C.ink = [30, 42, 50] / 255;
C.muted = [104, 119, 128] / 255;
C.guide = [216, 224, 228] / 255;
C.card = [245, 247, 246] / 255;
C.blue = [62, 110, 147] / 255;
C.blueLight = [208, 220, 229] / 255;
C.orange = [184, 102, 61] / 255;
C.green = [84, 128, 111] / 255;

fontName = chooseChineseFont();
fig = figure('Visible', 'off', 'Color', C.paper, 'Renderer', 'painters', ...
    'Units', 'inches', 'Position', [0.5, 0.5, 6.20, 3.95], ...
    'PaperPositionMode', 'auto');

cardX = [0.045, 0.355, 0.665];
cardW = 0.290;
for k = 1:3
    ax = axes(fig, 'Position', [cardX(k), 0.485, cardW, 0.405]);
    drawEventCard(ax, plans(k).drone_id, release(k), detonate(k), ...
        intervals(k, :), durations(k), heading(k), speed(k), C, fontName);
end

figText(fig, 0.045, 0.942, 'a', 'Arial', 9.2, C.ink, 'bold', 'left');
figText(fig, 0.075, 0.942, '三机各一弹：动作链与有效遮蔽事件', ...
    fontName, 8.2, C.ink, 'bold', 'left');
figText(fig, 0.955, 0.942, '横向位置表示事件顺序；节点标注为绝对时刻 / s', ...
    fontName, 7.0, C.muted, 'normal', 'right');

figText(fig, 0.045, 0.408, 'b', 'Arial', 9.2, C.ink, 'bold', 'left');
figText(fig, 0.075, 0.408, '覆盖状态接力：两个退出—进入空窗', ...
    fontName, 8.2, C.ink, 'bold', 'left');
figText(fig, 0.955, 0.408, sprintf('并集  %.3f s', unionDuration), ...
    fontName, 7.5, C.blue, 'bold', 'right');
drawCoverageRelay(fig, intervals, durations, gaps, unionDuration, C, fontName);

pngPath = fullfile(outDir, 'q4_temporal_synergy.png');
pdfPath = fullfile(outDir, 'q4_temporal_synergy.pdf');
svgPath = fullfile(outDir, 'q4_temporal_synergy.svg');
exportgraphics(fig, pngPath, 'Resolution', 360, 'BackgroundColor', C.paper);
exportgraphics(fig, pdfPath, 'ContentType', 'vector', 'BackgroundColor', C.paper);
try
    exportgraphics(fig, svgPath, 'ContentType', 'vector', 'BackgroundColor', C.paper);
catch
    print(fig, svgPath, '-dsvg', '-painters');
end
close(fig);

fprintf('Rendered Q4 event evidence:\n  %s\n  %s\n  %s\n', ...
    pngPath, pdfPath, svgPath);
end


function drawEventCard(ax, droneId, release, detonate, interval, duration, heading, speed, C, fontName)
hold(ax, 'on');
axis(ax, [0, 1, 0, 1]);
axis(ax, 'off');

rectangle(ax, 'Position', [0.015, 0.035, 0.970, 0.925], ...
    'Curvature', [0.055, 0.055], 'FaceColor', C.card, ...
    'EdgeColor', C.guide, 'LineWidth', 0.75);

text(ax, 0.055, 0.895, sprintf('%s  |  方位 %.1f° · 速度 %.0f m/s', ...
    droneId, heading, speed), 'FontName', fontName, 'FontSize', 7.3, ...
    'FontWeight', 'bold', 'Color', C.ink, 'Interpreter', 'none', ...
    'VerticalAlignment', 'middle');

x = [0.115, 0.365, 0.615, 0.865];
y = [0.610, 0.445, 0.610, 0.445];
for j = 1:3
    quiver(ax, x(j), y(j), x(j + 1) - x(j), y(j + 1) - y(j), 0, ...
        'Color', C.muted, 'LineWidth', 0.85, 'MaxHeadSize', 0.18, ...
        'AutoScale', 'off');
end

% A small smoke outline anchors the coverage events to their physical role.
theta = linspace(0, 2 * pi, 120);
fill(ax, 0.740 + 0.145 * cos(theta), 0.525 + 0.160 * sin(theta), ...
    C.blueLight, 'FaceAlpha', 0.28, 'EdgeColor', C.blue, 'LineWidth', 0.65);

plot(ax, x(1), y(1), 'd', 'MarkerSize', 5.2, ...
    'MarkerFaceColor', C.paper, 'MarkerEdgeColor', C.ink, 'LineWidth', 1.0);
plot(ax, x(2), y(2), 'o', 'MarkerSize', 5.4, ...
    'MarkerFaceColor', C.orange, 'MarkerEdgeColor', C.paper, 'LineWidth', 0.7);
plot(ax, x(3), y(3), '>', 'MarkerSize', 5.8, ...
    'MarkerFaceColor', C.green, 'MarkerEdgeColor', C.paper, 'LineWidth', 0.7);
plot(ax, x(4), y(4), '<', 'MarkerSize', 5.8, ...
    'MarkerFaceColor', C.blue, 'MarkerEdgeColor', C.paper, 'LineWidth', 0.7);

eventNames = {'投放', '起爆', '进入', '退出'};
eventTimes = [release, detonate, interval(1), interval(2)];
eventColors = [C.ink; C.orange; C.green; C.blue];
for j = 1:4
    if mod(j, 2) == 1
        labelY = y(j) + 0.125;
        valign = 'bottom';
    else
        labelY = y(j) - 0.125;
        valign = 'top';
    end
    text(ax, x(j), labelY, sprintf('%s\n%.3f', eventNames{j}, eventTimes(j)), ...
        'HorizontalAlignment', 'center', 'VerticalAlignment', valign, ...
        'FontName', fontName, 'FontSize', 7.0, 'FontWeight', 'bold', ...
        'Color', eventColors(j, :), 'Interpreter', 'none');
end

text(ax, 0.500, 0.115, sprintf('有效遮蔽  %.3f s', duration), ...
    'HorizontalAlignment', 'center', 'FontName', fontName, 'FontSize', 7.5, ...
    'FontWeight', 'bold', 'Color', C.blue, 'Interpreter', 'none');
hold(ax, 'off');
end


function drawCoverageRelay(fig, intervals, durations, gaps, unionDuration, C, fontName)
ax = axes(fig, 'Position', [0.060, 0.080, 0.880, 0.285]);
hold(ax, 'on');
axis(ax, [0, 1, 0, 1]);
axis(ax, 'off');

xCenter = [0.145, 0.500, 0.855];
yCenter = 0.545;
rx = 0.058;
ry = 0.285;
intervalNames = {'I₁', 'I₂', 'I₃'};
gapNames = {'g₁', 'g₂'};

for k = 1:3
    rectangle(ax, 'Position', [xCenter(k) - rx, yCenter - ry, 2 * rx, 2 * ry], ...
        'Curvature', [1, 1], 'FaceColor', C.card, ...
        'EdgeColor', C.blue, 'LineWidth', 1.10);
    plot(ax, xCenter(k) - rx, yCenter, '>', 'MarkerSize', 5.4, ...
        'MarkerFaceColor', C.green, 'MarkerEdgeColor', C.paper, 'LineWidth', 0.7);
    plot(ax, xCenter(k) + rx, yCenter, '<', 'MarkerSize', 5.4, ...
        'MarkerFaceColor', C.blue, 'MarkerEdgeColor', C.paper, 'LineWidth', 0.7);
    text(ax, xCenter(k), yCenter + 0.145, intervalNames{k}, ...
        'HorizontalAlignment', 'center', 'FontName', fontName, 'FontSize', 7.6, ...
        'FontWeight', 'bold', 'Color', C.blue, 'Interpreter', 'none');
    text(ax, xCenter(k), yCenter + 0.005, 'n(t)=1', ...
        'HorizontalAlignment', 'center', 'FontName', 'Arial', 'FontSize', 7.2, ...
        'FontWeight', 'bold', 'Color', C.ink, 'Interpreter', 'none');
    text(ax, xCenter(k), yCenter - 0.145, sprintf('%.3f s', durations(k)), ...
        'HorizontalAlignment', 'center', 'FontName', fontName, 'FontSize', 7.2, ...
        'FontWeight', 'bold', 'Color', C.blue, 'Interpreter', 'none');
    text(ax, xCenter(k), 0.105, sprintf('[%.3f, %.3f] s', intervals(k, 1), intervals(k, 2)), ...
        'HorizontalAlignment', 'center', 'FontName', fontName, 'FontSize', 6.9, ...
        'Color', C.muted, 'Interpreter', 'none');
end

for k = 1:2
    xLeft = xCenter(k) + rx + 0.018;
    xRight = xCenter(k + 1) - rx - 0.018;
    quiver(ax, xLeft, yCenter, xRight - xLeft, 0, 0, ...
        'Color', C.orange, 'LineStyle', ':', 'LineWidth', 1.0, ...
        'MaxHeadSize', 0.11, 'AutoScale', 'off');
    quiver(ax, xRight, yCenter, xLeft - xRight, 0, 0, ...
        'Color', C.orange, 'LineStyle', ':', 'LineWidth', 1.0, ...
        'MaxHeadSize', 0.11, 'AutoScale', 'off');
    text(ax, mean([xLeft, xRight]), yCenter + 0.160, ...
        sprintf('空窗 %s = %.3f s', gapNames{k}, gaps(k)), ...
        'HorizontalAlignment', 'center', 'FontName', fontName, 'FontSize', 7.0, ...
        'FontWeight', 'bold', 'Color', C.orange, 'Interpreter', 'none');
    text(ax, mean([xLeft, xRight]), yCenter - 0.145, 'n(t)=0', ...
        'HorizontalAlignment', 'center', 'FontName', 'Arial', 'FontSize', 6.9, ...
        'Color', C.muted, 'Interpreter', 'none');
end

hold(ax, 'off');
end


function figText(fig, x, y, label, fontName, fontSize, color, weight, alignment)
annotation(fig, 'textbox', [x, y, 0.001, 0.001], 'String', label, ...
    'FitBoxToText', 'on', 'EdgeColor', 'none', 'Margin', 0, ...
    'HorizontalAlignment', alignment, 'VerticalAlignment', 'middle', ...
    'FontName', fontName, 'FontSize', fontSize, 'FontWeight', weight, ...
    'Color', color, 'Interpreter', 'none');
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
