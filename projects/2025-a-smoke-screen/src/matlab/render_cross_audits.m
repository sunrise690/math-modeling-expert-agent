function render_cross_audits()
%RENDER_CROSS_AUDITS MATLAB-only search and criterion audit figures.
% The layouts use event/state transitions and paired slopes instead of bars.

scriptDir = fileparts(mfilename('fullpath'));
projectDir = fileparts(fileparts(scriptDir));
outDir = fullfile(projectDir, 'figures');
q12 = jsondecode(fileread(fullfile(projectDir, 'validation', 'q1_q2_independent.json')));
q35 = jsondecode(fileread(fullfile(projectDir, 'validation', 'q3_q5_independent.json')));

C = palette();
fontName = chooseChineseFont();
renderSearchAudit(q35, outDir, C, fontName);
renderCriterionAudit(q12, q35, outDir, C, fontName);
fprintf('Rendered MATLAB cross-question audit figures.\n');
end


function renderSearchAudit(payload, outDir, C, fontName)
questions = {'Q3', 'Q4', 'Q5'};
baseline = zeros(1, 3);
coarse = zeros(1, 3);
exact = zeros(1, 3);
counts = zeros(3, 3);
for k = 1:3
    diagnostics = payload.results.(questions{k}).diagnostics;
    baseline(k) = diagnostics.fast_baseline_objective;
    coarse(k) = diagnostics.fast_final_objective;
    exact(k) = diagnostics.exact_objective;
    counts(k, :) = [diagnostics.candidates_generated, ...
        diagnostics.routes_evaluated, diagnostics.packages_retained];
end

fig = figure('Visible', 'off', 'Color', C.paper, 'Renderer', 'painters', ...
    'Units', 'inches', 'Position', [0.5, 0.5, 6.20, 3.70], ...
    'PaperPositionMode', 'auto');
layout = tiledlayout(fig, 2, 3, 'TileSpacing', 'compact', 'Padding', 'compact');
colors = [C.ink; C.muted; C.primary];
questionStyles = {'-', '--', '-.'};
questionMarkers = {'o', 's', '^'};

for k = 1:3
    ax = nexttile(layout, k);
    ratio = [100, coarse(k) / baseline(k) * 100, exact(k) / baseline(k) * 100];
    objectiveValues = [baseline(k), coarse(k), exact(k)];
    hold(ax, 'on');
    yPad = max(1.0, 0.09 * (max(ratio) - min(ratio)));
    yLimits = [min(ratio) - yPad, max(ratio) + 5.0 * yPad];
    plot(ax, 1:3, ratio, questionStyles{k}, ...
        'Color', colors(k, :), 'LineWidth', 1.55);
    scatter(ax, 1, ratio(1), 34, C.paper, 'o', 'MarkerEdgeColor', colors(k, :), 'LineWidth', 1.1);
    scatter(ax, 2, ratio(2), 34, C.paper, 'd', 'MarkerEdgeColor', colors(k, :), 'LineWidth', 1.1);
    scatter(ax, 3, ratio(3), 40, C.warm, questionMarkers{k}, ...
        'filled', 'MarkerEdgeColor', C.paper, 'LineWidth', 0.7);
    for j = 1:3
        horizontal = 'center';
        if j == 1
            horizontal = 'left';
        elseif j == 3
            horizontal = 'right';
        end
        % Q5's coarse and exact objectives are almost equal.  Keep their
        % labels on the outer sides of the two nodes so the values do not
        % collide at final column width.
        if k == 3 && j == 2
            horizontal = 'right';
        elseif k == 3 && j == 3
            horizontal = 'left';
        end
        text(ax, j, ratio(j), sprintf('%.3f s', objectiveValues(j)), ...
            'FontName', fontName, 'FontSize', 7.0, 'Color', C.ink, ...
            'HorizontalAlignment', horizontal, 'VerticalAlignment', 'bottom');
    end
    gain = ratio(3) - 100;
    text(ax, 0.02, 0.93, sprintf('%s  连续复算增益 %+0.1f%%', questions{k}, gain), ...
        'Units', 'normalized', 'FontName', fontName, 'FontSize', 7.2, ...
        'FontWeight', 'bold', 'Color', colors(k, :));
    ylim(ax, yLimits);
    xlim(ax, [0.75, 3.35]);
    set(ax, 'XTick', 1:3, 'XTickLabel', {'基线', '粗评', '连续复算'});
    ylabel(ax, '相对基线 / %', 'FontName', fontName);
    styleAxis(ax, C, fontName, true);
    panelLabel(ax, char('a' + k - 1), C, fontName);
    hold(ax, 'off');
end

ax = nexttile(layout, 4, [1, 3]);
hold(ax, 'on');
stageLabels = {'生成候选', '评估航路', '保留包'};
logCounts = log10(max(counts, 1));
logRange = max(logCounts(:)) - min(logCounts(:));
if logRange < eps
    nodeSizes = 46 * ones(size(counts));
else
    nodeSizes = 34 + 30 * (logCounts - min(logCounts(:))) / logRange;
end
for row = 1:3
    y = 4 - row;
    u = linspace(0, 1, 60);
    plot(ax, 1 + u, y + 0.10 * sin(pi * u), questionStyles{row}, ...
        'Color', colors(row, :), 'LineWidth', 1.15);
    plot(ax, 2 + u, y - 0.10 * sin(pi * u), questionStyles{row}, ...
        'Color', colors(row, :), 'LineWidth', 1.15);
    text(ax, 0.64, y, questions{row}, 'HorizontalAlignment', 'right', ...
        'VerticalAlignment', 'middle', 'FontName', fontName, ...
        'FontSize', 7.4, 'FontWeight', 'bold', 'Color', colors(row, :));
    for col = 1:3
        scatter(ax, col, y, nodeSizes(row, col), colors(row, :), questionMarkers{row}, ...
            'filled', 'MarkerEdgeColor', C.paper, 'LineWidth', 0.7);
        text(ax, col, y - 0.24, sprintf('%d', round(counts(row, col))), ...
            'HorizontalAlignment', 'center', 'VerticalAlignment', 'top', ...
            'FontName', fontName, 'FontSize', 7.0, 'Color', C.ink);
    end
end
xlim(ax, [0.55, 3.45]);
ylim(ax, [0.42, 3.50]);
set(ax, 'XTick', 1:3, 'XTickLabel', stageLabels, 'YTick', []);
styleAxis(ax, C, fontName, false);
panelLabel(ax, 'd', C, fontName);
text(ax, 0.995, 1.03, '节点面积∝ log_{10}(计数)', 'Units', 'normalized', ...
    'HorizontalAlignment', 'right', 'VerticalAlignment', 'bottom', ...
    'FontName', fontName, 'FontSize', 7.0, 'Color', C.muted, ...
    'Interpreter', 'tex');
hold(ax, 'off');

exportFigure(fig, outDir, 'search_quality_diagnostics', C.paper);
end


function renderCriterionAudit(q12, q35, outDir, C, fontName)
q1Fields = fieldnames(q12.q1);
q1Index = find(contains(q1Fields, '9_80'), 1, 'first');
q1 = q12.q1.(q1Fields{q1Index});
center = [q1.centerline.duration_s, q12.q2.centerline.duration_s, ...
    q35.results.Q3.exact_centerline_objective, ...
    q35.results.Q4.exact_centerline_objective, ...
    q35.results.Q5.exact_centerline_objective];
full = [q1.full_cylinder.duration_s, ...
    q12.q2.full_cylinder_tau_0_boundary.duration_s, ...
    q35.full_cylinder_secondary_audit.Q3.objective, ...
    q35.full_cylinder_secondary_audit.Q4.objective, ...
    q35.full_cylinder_secondary_audit.Q5.objective];

fig = figure('Visible', 'off', 'Color', C.paper, 'Renderer', 'painters', ...
    'Units', 'inches', 'Position', [0.5, 0.5, 6.20, 3.55], ...
    'PaperPositionMode', 'auto');
questionColors = repmat(C.muted, 4, 1);
questionStyles = {'-', '--', '-.', ':'};

% A is the hero evidence: the same submitted strategies lose very different
% fractions under the conservative cylinder criterion.  B and C are compact
% supporting audits, not three dashboard-style panels of equal weight.
ax = axes(fig, 'Position', [0.075, 0.145, 0.535, 0.78]);
hold(ax, 'on');
indices = [1, 3, 4, 5];
labels = {'问题一', '问题三', '问题四', '问题五'};
retentions = 100 * full(indices) ./ center(indices);
yLimits = [min(retentions) - 5, 104];
for k = 1:4
    retention = retentions(k);
    plot(ax, [1, 2], [100, retention], questionStyles{k}, ...
        'Color', questionColors(k, :), 'LineWidth', 1.35);
    scatter(ax, 1, 100, 31, C.primary, 'o', 'filled', ...
        'MarkerEdgeColor', C.paper, 'LineWidth', 0.55);
    scatter(ax, 2, retention, 33, C.paper, 's', ...
        'MarkerEdgeColor', C.wine, 'LineWidth', 1.05);
    text(ax, 2.05, retention, sprintf('%s  %.1f%%', labels{k}, retention), ...
        'FontName', fontName, 'FontSize', 7.0, 'Color', questionColors(k, :), ...
        'VerticalAlignment', 'middle');
end
xlim(ax, [0.82, 2.90]);
ylim(ax, yLimits);
set(ax, 'XTick', [1, 2], 'XTickLabel', {'中心判据', '圆柱判据'});
ylabel(ax, '同方案时长保留率 / %', 'FontName', fontName);
styleAxis(ax, C, fontName, true);
panelLabel(ax, 'a', C, fontName);
hold(ax, 'off');

% B: Q5 per-missile paired audit.
ax = axes(fig, 'Position', [0.705, 0.585, 0.265, 0.33]);
hold(ax, 'on');
missiles = {'M1', 'M2', 'M3'};
missileColors = repmat(C.muted, 3, 1);
missileStyles = {'-', '--', '-.'};
allValues = [];
for k = 1:3
    centerValue = q35.results.Q5.exact_centerline_duration_by_missile.(missiles{k});
    fullValue = q35.full_cylinder_secondary_audit.Q5.duration_by_missile.(missiles{k});
    allValues = [allValues, centerValue, fullValue]; %#ok<AGROW>
end
yLimits = [min(allValues) - 1.2, max(allValues) + 1.2];
for k = 1:3
    centerValue = q35.results.Q5.exact_centerline_duration_by_missile.(missiles{k});
    fullValue = q35.full_cylinder_secondary_audit.Q5.duration_by_missile.(missiles{k});
    plot(ax, [1, 2], [centerValue, fullValue], missileStyles{k}, ...
        'Color', missileColors(k, :), 'LineWidth', 1.35);
    scatter(ax, 1, centerValue, 33, C.primary, 'o', 'filled', ...
        'MarkerEdgeColor', C.paper, 'LineWidth', 0.55);
    scatter(ax, 2, fullValue, 35, C.paper, 's', ...
        'MarkerEdgeColor', C.wine, 'LineWidth', 1.05);
    text(ax, 2.05, fullValue, sprintf('%s  -%.1f%%', missiles{k}, ...
        100 * (centerValue - fullValue) / centerValue), ...
        'FontName', fontName, 'FontSize', 7.0, 'Color', missileColors(k, :), ...
        'VerticalAlignment', 'middle');
end
xlim(ax, [0.82, 2.82]);
ylim(ax, yLimits);
set(ax, 'XTick', [1, 2], 'XTickLabel', {'中心判据', '圆柱判据'});
ylabel(ax, '问题五分导弹并集 / s', 'FontName', fontName);
styleAxis(ax, C, fontName, true);
panelLabel(ax, 'b', C, fontName);
hold(ax, 'off');

% C: Q2 uses two independent optimizations and must not be connected.
ax = axes(fig, 'Position', [0.705, 0.145, 0.265, 0.30]);
hold(ax, 'on');
q2Values = [center(2), full(2)];
yLimits = [min(q2Values) - 0.18, max(q2Values) + 0.18];
scatter(ax, 1, q2Values(1), 46, C.primary, 'o', 'filled', ...
    'MarkerEdgeColor', C.paper, 'LineWidth', 0.6);
scatter(ax, 2, q2Values(2), 48, C.paper, 's', ...
    'MarkerEdgeColor', C.wine, 'LineWidth', 1.15);
text(ax, 1, q2Values(1) + 0.045, sprintf('%.4f s', q2Values(1)), ...
    'HorizontalAlignment', 'center', 'FontName', fontName, ...
    'FontSize', 7.0, 'Color', C.primary, 'FontWeight', 'bold');
text(ax, 2, q2Values(2) - 0.045, sprintf('%.4f s', q2Values(2)), ...
    'HorizontalAlignment', 'center', 'VerticalAlignment', 'top', ...
    'FontName', fontName, 'FontSize', 7.0, 'Color', C.wine, 'FontWeight', 'bold');
text(ax, 1.5, mean(q2Values), '⋯  独立优化，不连线  ⋯', ...
    'HorizontalAlignment', 'center', 'FontName', fontName, ...
    'FontSize', 7.0, 'Color', C.muted, 'BackgroundColor', C.paper, 'Margin', 0.4);
xlim(ax, [0.55, 2.45]);
ylim(ax, yLimits);
set(ax, 'XTick', [1, 2], 'XTickLabel', {'中心独立最优', '圆柱独立最优'});
ylabel(ax, '问题二独立优化时长 / s', 'FontName', fontName);
styleAxis(ax, C, fontName, true);
panelLabel(ax, 'c', C, fontName);
hold(ax, 'off');

annotation(fig, 'textbox', [0.105, 0.947, 0.245, 0.038], ...
    'String', '● 中心判据    □ 圆柱判据', 'FontName', fontName, ...
    'FontSize', 7.0, 'Color', C.ink, 'Interpreter', 'none', ...
    'EdgeColor', 'none', 'FitBoxToText', 'off');

exportFigure(fig, outDir, 'criterion_sensitivity', C.paper);
end


function exportFigure(fig, outDir, stem, background)
exportgraphics(fig, fullfile(outDir, [stem, '.png']), ...
    'Resolution', 360, 'BackgroundColor', background);
exportgraphics(fig, fullfile(outDir, [stem, '.pdf']), ...
    'ContentType', 'vector', 'BackgroundColor', background);
try
    exportgraphics(fig, fullfile(outDir, [stem, '.svg']), ...
        'ContentType', 'vector', 'BackgroundColor', background);
catch
    print(fig, fullfile(outDir, [stem, '.svg']), '-dsvg', '-painters');
end
close(fig);
end


function styleAxis(ax, C, fontName, useGrid)
ax.FontName = fontName;
ax.FontSize = 7.0;
ax.LineWidth = 0.65;
ax.XColor = C.muted;
ax.YColor = C.muted;
ax.Color = C.paper;
ax.Box = 'off';
ax.TickDir = 'out';
ax.TickLength = [0.012, 0.012];
ax.Layer = 'top';
if useGrid
    ax.YGrid = 'on';
    ax.XGrid = 'off';
    ax.GridColor = C.grid;
    ax.GridAlpha = 0.50;
    ax.GridLineStyle = ':';
else
    grid(ax, 'off');
end
end


function panelLabel(ax, label, C, fontName)
text(ax, -0.10, 1.03, label, 'Units', 'normalized', ...
    'FontName', fontName, 'FontSize', 9.2, 'FontWeight', 'bold', ...
    'Color', C.ink, 'VerticalAlignment', 'bottom');
end


function C = palette()
C.paper = hexColor('#FFFFFF');
C.ink = hexColor('#1E2A32');
C.muted = hexColor('#647078');
C.grid = hexColor('#D6DEE1');
C.primary = hexColor('#2F6079');
C.secondary = hexColor('#59636A');
C.warm = hexColor('#B5782F');
C.wine = hexColor('#8B4E5A');
C.panel = C.paper;
C.blueDark = mixColor(C.ink, C.primary, 0.24);
C.blueSoft = mixColor(C.primary, C.muted, 0.62);
C.guide = C.grid;
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


function rgb = hexColor(code)
code = char(erase(string(code), '#'));
rgb = [hex2dec(code(1:2)), hex2dec(code(3:4)), hex2dec(code(5:6))] / 255;
end


function color = mixColor(foreground, background, weight)
weight = max(0, min(1, weight));
color = weight * foreground + (1 - weight) * background;
end
