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
colors = [C.blue; C.orange; C.green];

for k = 1:3
    ax = nexttile(layout, k);
    ratio = [100, coarse(k) / baseline(k) * 100, exact(k) / baseline(k) * 100];
    objectiveValues = [baseline(k), coarse(k), exact(k)];
    plot(ax, 1:3, ratio, '-', 'Color', colors(k, :), 'LineWidth', 1.45);
    hold(ax, 'on');
    scatter(ax, 1, ratio(1), 34, C.paper, 'o', 'MarkerEdgeColor', colors(k, :), 'LineWidth', 1.1);
    scatter(ax, 2, ratio(2), 34, C.paper, 'd', 'MarkerEdgeColor', colors(k, :), 'LineWidth', 1.1);
    scatter(ax, 3, ratio(3), 38, colors(k, :), 'o', 'MarkerEdgeColor', C.paper, 'LineWidth', 0.7);
    for j = 1:3
        horizontal = 'center';
        if j == 1
            horizontal = 'left';
        elseif j == 3
            horizontal = 'right';
        end
        text(ax, j, ratio(j), sprintf('%.3f s', objectiveValues(j)), ...
            'FontName', fontName, 'FontSize', 7.0, 'Color', C.ink, ...
            'HorizontalAlignment', horizontal, 'VerticalAlignment', 'bottom');
    end
    gain = ratio(3) - 100;
    text(ax, 0.02, 0.93, sprintf('%s  连续复算增益 %+0.1f%%', questions{k}, gain), ...
        'Units', 'normalized', 'FontName', fontName, 'FontSize', 7.2, ...
        'FontWeight', 'bold', 'Color', colors(k, :));
    yPad = max(1.0, 0.09 * (max(ratio) - min(ratio)));
    ylim(ax, [min(ratio) - yPad, max(ratio) + 5.0 * yPad]);
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
for row = 1:3
    y = 4 - row;
    plot(ax, [0.70, 3.30], [y, y], '-', 'Color', C.guide, 'LineWidth', 0.7);
    for col = 1:3
        scatter(ax, col, y, 42, colors(row, :), 'o', ...
            'MarkerEdgeColor', C.paper, 'LineWidth', 0.7);
        text(ax, col, y - 0.26, sprintf('%s\n%d', questions{row}, round(counts(row, col))), ...
            'HorizontalAlignment', 'center', 'VerticalAlignment', 'top', ...
            'FontName', fontName, 'FontSize', 7.0, 'Color', C.ink);
    end
end
xlim(ax, [0.55, 3.45]);
ylim(ax, [-0.10, 3.50]);
set(ax, 'XTick', 1:3, 'XTickLabel', stageLabels, 'YTick', []);
styleAxis(ax, C, fontName, false);
panelLabel(ax, 'd', C, fontName);
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
    'Units', 'inches', 'Position', [0.5, 0.5, 6.20, 3.00], ...
    'PaperPositionMode', 'auto');
layout = tiledlayout(fig, 1, 3, 'TileSpacing', 'compact', 'Padding', 'compact');
colors = [C.blue; C.green; C.orange; C.purple];

% A: same-strategy retention slopes. Q2 is excluded because it is re-optimized.
ax = nexttile(layout, 1);
hold(ax, 'on');
indices = [1, 3, 4, 5];
labels = {'Q1', 'Q3', 'Q4', 'Q5'};
for k = 1:4
    retention = 100 * full(indices(k)) / center(indices(k));
    plot(ax, [1, 2], [100, retention], '-', 'Color', colors(k, :), 'LineWidth', 1.35);
    scatter(ax, [1, 2], [100, retention], 30, colors(k, :), 'filled', ...
        'MarkerEdgeColor', C.paper, 'LineWidth', 0.55);
    text(ax, 2.05, retention, sprintf('%s  %.1f%%', labels{k}, retention), ...
        'FontName', fontName, 'FontSize', 7.0, 'Color', colors(k, :), ...
        'VerticalAlignment', 'middle');
end
xlim(ax, [0.82, 2.58]);
ylim(ax, [min(100 * full(indices) ./ center(indices)) - 5, 104]);
set(ax, 'XTick', [1, 2], 'XTickLabel', {'中心口径', '圆柱复算'});
ylabel(ax, '同策略保留率 / %', 'FontName', fontName);
styleAxis(ax, C, fontName, true);
panelLabel(ax, 'a', C, fontName);
hold(ax, 'off');

% B: Q5 per-missile paired audit.
ax = nexttile(layout, 2);
hold(ax, 'on');
missiles = {'M1', 'M2', 'M3'};
missileColors = [C.blue; C.orange; C.green];
allValues = [];
for k = 1:3
    centerValue = q35.results.Q5.exact_centerline_duration_by_missile.(missiles{k});
    fullValue = q35.full_cylinder_secondary_audit.Q5.duration_by_missile.(missiles{k});
    allValues = [allValues, centerValue, fullValue]; %#ok<AGROW>
    plot(ax, [1, 2], [centerValue, fullValue], '-', ...
        'Color', missileColors(k, :), 'LineWidth', 1.35);
    scatter(ax, [1, 2], [centerValue, fullValue], 31, missileColors(k, :), ...
        'filled', 'MarkerEdgeColor', C.paper, 'LineWidth', 0.55);
    text(ax, 2.05, fullValue, sprintf('%s  -%.1f%%', missiles{k}, ...
        100 * (centerValue - fullValue) / centerValue), ...
        'FontName', fontName, 'FontSize', 7.0, 'Color', missileColors(k, :), ...
        'VerticalAlignment', 'middle');
end
xlim(ax, [0.82, 2.70]);
ylim(ax, [min(allValues) - 1.2, max(allValues) + 1.2]);
set(ax, 'XTick', [1, 2], 'XTickLabel', {'中心口径', '圆柱复算'});
ylabel(ax, 'Q5 分导弹并集 / s', 'FontName', fontName);
styleAxis(ax, C, fontName, true);
panelLabel(ax, 'b', C, fontName);
hold(ax, 'off');

% C: Q2 uses two independent optimizations and must not be connected.
ax = nexttile(layout, 3);
hold(ax, 'on');
q2Values = [center(2), full(2)];
scatter(ax, [1, 1], q2Values, 42, [C.blue; C.orange], 'filled', ...
    'MarkerEdgeColor', C.paper, 'LineWidth', 0.6);
text(ax, 1.08, q2Values(1), sprintf('中心独立最优\n%.4f s', q2Values(1)), ...
    'FontName', fontName, 'FontSize', 7.0, 'Color', C.blue, 'VerticalAlignment', 'middle');
text(ax, 1.08, q2Values(2), sprintf('圆柱独立最优\n%.4f s', q2Values(2)), ...
    'FontName', fontName, 'FontSize', 7.0, 'Color', C.orange, 'VerticalAlignment', 'middle');
xlim(ax, [0.72, 1.92]);
ylim(ax, [min(q2Values) - 0.18, max(q2Values) + 0.18]);
set(ax, 'XTick', 1, 'XTickLabel', {'Q2'}, 'YTick', []);
text(ax, 0.50, 0.05, '两点不连线：不是同一策略前后变化', ...
    'Units', 'normalized', 'HorizontalAlignment', 'center', ...
    'FontName', fontName, 'FontSize', 7.0, 'Color', C.darkRed);
styleAxis(ax, C, fontName, false);
panelLabel(ax, 'c', C, fontName);
hold(ax, 'off');

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
if useGrid
    ax.YGrid = 'on';
    ax.GridColor = C.guide;
    ax.GridAlpha = 0.62;
end
end


function panelLabel(ax, label, C, fontName)
text(ax, -0.10, 1.03, label, 'Units', 'normalized', ...
    'FontName', fontName, 'FontSize', 9.2, 'FontWeight', 'bold', ...
    'Color', C.ink, 'VerticalAlignment', 'bottom');
end


function C = palette()
C.paper = hexColor('#FBFBFA');
C.ink = hexColor('#23323B');
C.muted = hexColor('#71808A');
C.guide = hexColor('#DDE3E6');
C.blue = hexColor('#3E6E93');
C.orange = hexColor('#C66F3D');
C.green = hexColor('#5C8173');
C.purple = hexColor('#7B6A82');
C.darkRed = hexColor('#A95C57');
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
