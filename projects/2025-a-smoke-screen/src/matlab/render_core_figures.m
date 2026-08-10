%% Publication figures rendered natively by MATLAB
% Reads the checked validation records, recomputes the geometric surfaces
% and discretisation audits in MATLAB, and exports six manuscript figures.

clearvars;
close all;
clc;

scriptPath = mfilename('fullpath');
projectRoot = fileparts(fileparts(fileparts(scriptPath)));
validationDir = fullfile(projectRoot, 'validation');
outputDir = fullfile(projectRoot, 'figures');

q12 = readJson(fullfile(validationDir, 'q1_q2_independent.json'));
q2Seeds = readJson(fullfile(validationDir, 'q2_multiseed.json'));
q34Seeds = readJson(fullfile(validationDir, 'q3_q4_multiseed.json'));

q1Fields = fieldnames(q12.q1);
q1Index = find(contains(q1Fields, '9_80'), 1, 'first');
assert(~isempty(q1Index), 'Q1 g = 9.80 m/s^2 record is missing.');
q1 = q12.q1.(q1Fields{q1Index});

% Restrained editorial palette. Neutral charcoal carries structure, denim
% blue carries the primary result, and clay is reserved for penalties.
palette = contest_palette();
palette.panel = palette.paper;
palette.primaryLight = blendColor(palette.primary, palette.paper, 0.10);
palette.secondaryLight = blendColor(palette.secondary, palette.paper, 0.09);
palette.accentLight = blendColor(palette.accent, palette.paper, 0.09);
palette.wineLight = blendColor(palette.wine, palette.paper, 0.09);
palette.grayLine = blendColor(palette.muted, palette.paper, 0.43);
palette.font = 'Microsoft YaHei';

fprintf('MATLAB core figure rendering started.\n');

renderFiniteSightline(q12, q1, outputDir, palette);
renderQ1RootEvents(q12, q1, outputDir, palette);
renderQ2Response(q12, outputDir, palette);
renderQ2Seeds(q2Seeds, outputDir, palette);
renderTimeStepAudit(q12, q1, outputDir, palette);
renderQ34Seeds(q34Seeds, outputDir, palette);

fprintf('MATLAB core figure rendering completed.\n');

%% Figure F2: finite sightline geometry
function renderFiniteSightline(q12, q1, outputDir, p)
    constants = q12.constants;
    strategy = q1.strategy;
    gravity = double(q1.gravity_mps2);
    time = 8.70;
    target = targetCenter(constants);
    missile = missilePosition(time, constants);
    cloud = smokeCenter(time, constants, strategy);
    sight = target - missile;
    lambda0 = dot(cloud - missile, sight) / dot(sight, sight);
    lambdaStar = min(1, max(0, lambda0));
    closest = missile + lambdaStar .* sight;
    distance = norm(cloud - closest);
    centerMargin = double(constants.smoke_radius_m) - distance;
    fullMargin = fullCylinderMargin(time, constants, strategy, 1440);

    assert(lambda0 > 0 && lambda0 < 1, 'The selected F2 state is not an interior projection.');
    assert(centerMargin > 0 && fullMargin > 0, 'The selected F2 state is not occluded.');

    fig = publicationFigure(6.20, 3.20, p.paper);

    % A: finite-segment projection with an intentional sightline break.
    ax = axes(fig, 'Position', [0.065, 0.17, 0.555, 0.75]);
    hold(ax, 'on');
    plot(ax, [0.08, 0.90], [0.24, 0.24], '-', 'Color', p.ink, 'LineWidth', 1.35);
    quiver(ax, 0.84, 0.24, 0.06, 0, 0, 'Color', p.ink, ...
        'LineWidth', 0.9, 'MaxHeadSize', 1.5);
    scatter(ax, 0.08, 0.24, 42, '>', 'filled', ...
        'MarkerFaceColor', p.ink, 'MarkerEdgeColor', p.paper, 'LineWidth', 0.5);
    rectangle(ax, 'Position', [0.88, 0.18, 0.035, 0.12], ...
        'FaceColor', p.ink, 'EdgeColor', p.ink, 'LineWidth', 0.45);

    projectionX = 0.28;
    cloudXY = [projectionX, 0.65];
    theta = linspace(0, 2*pi, 240);
    patch(ax, cloudXY(1) + 0.075*cos(theta), cloudXY(2) + 0.075*sin(theta), ...
        p.primaryLight, 'EdgeColor', p.primary, 'LineWidth', 1.0, 'FaceAlpha', 0.96);
    scatter(ax, cloudXY(1), cloudXY(2), 18, 'o', 'filled', ...
        'MarkerFaceColor', p.primary, 'MarkerEdgeColor', p.paper, 'LineWidth', 0.4);
    plot(ax, [projectionX, projectionX], [0.24, cloudXY(2)], '--', ...
        'Color', p.primary, 'LineWidth', 1.05);
    scatter(ax, projectionX, 0.24, 34, 'o', ...
        'MarkerFaceColor', p.paper, 'MarkerEdgeColor', p.primary, 'LineWidth', 1.1);
    quiver(ax, projectionX, 0.29, 0, 0.29, 0, 'Color', p.primary, ...
        'LineWidth', 0.85, 'MaxHeadSize', 0.22);
    quiver(ax, projectionX, 0.60, 0, -0.27, 0, 'Color', p.primary, ...
        'LineWidth', 0.85, 'MaxHeadSize', 0.22);

    text(ax, 0.08, 0.13, '导弹 M', 'Color', p.ink, ...
        'FontName', p.font, 'FontSize', 7.2, 'HorizontalAlignment', 'center');
    text(ax, 0.90, 0.13, '真目标 T', 'Color', p.muted, ...
        'FontName', p.font, 'FontSize', 7.2, 'HorizontalAlignment', 'center');
    text(ax, cloudXY(1) + 0.095, cloudXY(2) + 0.01, '烟幕截面', ...
        'Color', p.primary, 'FontName', p.font, 'FontSize', 7.2, 'FontWeight', 'bold');
    text(ax, projectionX + 0.025, 0.43, 'd(C_s, MT)', ...
        'Color', p.primary, 'FontName', p.font, 'FontSize', 7.0, ...
        'FontWeight', 'bold');
    text(ax, projectionX + 0.02, 0.285, ...
        sprintf('P*   λ* = %.4f', lambdaStar), ...
        'Color', p.ink, 'FontName', p.font, 'FontSize', 7.0);
    text(ax, 0.50, 0.90, '有限视线：先投影，再把 λ₀ 截断到 [0, 1]', ...
        'Color', p.ink, 'FontName', p.font, 'FontSize', 8.0, ...
        'FontWeight', 'bold', 'HorizontalAlignment', 'center');
    text(ax, 0.51, 0.06, ...
        'λ₀ < 0 → M        0 ≤ λ₀ ≤ 1 → P*        λ₀ > 1 → T', ...
        'Color', p.muted, 'FontName', p.font, 'FontSize', 7.0, ...
        'HorizontalAlignment', 'center');
    text(ax, 0.63, 0.255, '//', 'Color', p.muted, ...
        'FontName', p.font, 'FontSize', 8.5, 'FontWeight', 'bold', ...
        'HorizontalAlignment', 'center');
    text(ax, 0.50, 0.01, '示意图：视线近端局部放大，不按长度比例', ...
        'Color', p.muted, 'FontName', p.font, 'FontSize', 7.0, ...
        'HorizontalAlignment', 'center');
    xlim(ax, [0, 1]);
    ylim(ax, [-0.02, 1]);
    axis(ax, 'off');
    panelLabel(ax, 'a', p, [-0.03, 1.03]);

    % B: true-scale local cross-section.
    ax = axes(fig, 'Position', [0.695, 0.56, 0.265, 0.34]);
    hold(ax, 'on');
    radius = double(constants.smoke_radius_m);
    theta = linspace(0, 2*pi, 280);
    patch(ax, radius*cos(theta), distance + radius*sin(theta), ...
        p.primaryLight, 'EdgeColor', p.primary, 'LineWidth', 0.95, 'FaceAlpha', 0.96);
    plot(ax, [-11.5, 11.5], [0, 0], '-', 'Color', p.ink, 'LineWidth', 1.0);
    plot(ax, [0, 0], [0, distance], '--', 'Color', p.primary, 'LineWidth', 0.95);
    scatter(ax, 0, distance, 22, 'o', 'filled', 'MarkerFaceColor', p.primary, ...
        'MarkerEdgeColor', p.paper, 'LineWidth', 0.4);
    plot(ax, [0, radius], [distance, distance], '-', 'Color', p.primary, 'LineWidth', 0.85);
    scatter(ax, [0, radius], [distance, distance], 15, 'o', ...
        'MarkerFaceColor', p.paper, 'MarkerEdgeColor', p.primary, 'LineWidth', 0.75);
    text(ax, radius/2, distance + 1.1, 'R = 10 m', 'Color', p.primary, ...
        'FontName', p.font, 'FontSize', 7.0, 'HorizontalAlignment', 'center');
    text(ax, 0.8, distance/2, sprintf('d = %.2f m', distance), ...
        'Color', p.primary, 'FontName', p.font, 'FontSize', 7.0, ...
        'FontWeight', 'bold');
    xlabel(ax, '局部切向坐标 (m)', 'FontName', p.font, 'FontSize', 7.4);
    ylabel(ax, '距视线 (m)', 'FontName', p.font, 'FontSize', 7.4);
    xlim(ax, [-11.8, 11.8]);
    ylim(ax, [-3.4, distance + 11.2]);
    axis(ax, 'equal');
    styleAxes(ax, p, true);
    panelLabel(ax, 'b', p, [-0.15, 1.06]);

    % C: decision margins as points and thin stems, never as bars.
    ax = axes(fig, 'Position', [0.695, 0.16, 0.265, 0.25]);
    hold(ax, 'on');
    values = [centerMargin, fullMargin];
    colors = [p.primary; p.secondary];
    markers = {'o', 'd'};
    lineStyles = {'-', '--'};
    y = [2, 1];
    xline(ax, 0, '-', 'Color', p.ink, 'LineWidth', 0.75);
    for k = 1:2
        plot(ax, [0, values(k)], [y(k), y(k)], lineStyles{k}, ...
            'Color', colors(k, :), 'LineWidth', 1.0);
        scatter(ax, values(k), y(k), 42, markers{k}, 'filled', ...
            'MarkerFaceColor', colors(k, :), 'MarkerEdgeColor', p.paper, ...
            'LineWidth', 0.55);
        text(ax, values(k) + 0.08, y(k), sprintf('%+.2f m', values(k)), ...
            'Color', colors(k, :), 'FontName', p.font, 'FontSize', 7.2, ...
            'FontWeight', 'bold', 'VerticalAlignment', 'middle');
    end
    yticks(ax, [1, 2]);
    yticklabels(ax, {'完整圆柱', '中心视线'});
    xlabel(ax, '判据裕度 F(t) (m)', 'FontName', p.font, 'FontSize', 7.4);
    text(ax, 0.02, 0.96, 'F(t) ≥ 0：遮蔽成立', 'Units', 'normalized', ...
        'Color', p.ink, 'FontName', p.font, 'FontSize', 7.0, ...
        'VerticalAlignment', 'top');
    xlim(ax, [-0.35, max(values) + 0.95]);
    ylim(ax, [0.55, 2.45]);
    styleAxes(ax, p, true);
    ax.YGrid = 'off';
    panelLabel(ax, 'c', p, [-0.15, 1.08]);

    exportTriple(fig, outputDir, 'finite_sightline_geometry', p);
    fprintf('  F2 finite sightline: lambda %.6f, d %.6f m, margins %.6f / %.6f m.\n', ...
        lambdaStar, distance, centerMargin, fullMargin);
end

%% Figure F3: Q1 root events, without interval bars
function renderQ1RootEvents(q12, q1, outputDir, p)
    constants = q12.constants;
    strategy = q1.strategy;
    centerRoots = double(q1.centerline.intervals_s(1, :));
    fullRoots = double(q1.full_cylinder.intervals_s(1, :));
    time = linspace(7.88, 9.53, 420);
    centerMargin = centerlineMargin(time, constants, strategy);
    fullMargin = zeros(size(time));
    for k = 1:numel(time)
        fullMargin(k) = fullCylinderMargin(time(k), constants, strategy, 720);
    end

    fig = publicationFigure(6.20, 3.38, p.paper);

    % A: complete margin history.
    ax = axes(fig, 'Position', [0.075, 0.16, 0.585, 0.76]);
    hold(ax, 'on');
    positive = centerMargin >= 0;
    patches = contiguousRegions(time, positive);
    fullPositive = contiguousRegions(time, fullMargin >= 0);
    yl = [-4.3, 6.3];
    for k = 1:size(patches, 1)
        patch(ax, [patches(k,1), patches(k,2), patches(k,2), patches(k,1)], ...
            [0, 0, yl(2), yl(2)], p.primaryLight, ...
            'FaceAlpha', 0.70, 'EdgeColor', 'none');
    end
    for k = 1:size(fullPositive, 1)
        patch(ax, [fullPositive(k,1), fullPositive(k,2), ...
            fullPositive(k,2), fullPositive(k,1)], ...
            [yl(1), yl(1), 0, 0], p.secondaryLight, ...
            'FaceAlpha', 0.72, 'EdgeColor', 'none');
    end
    plot(ax, time, centerMargin, '-', 'Color', p.primary, 'LineWidth', 1.45);
    plot(ax, time, fullMargin, '--', 'Color', p.secondary, 'LineWidth', 1.30);
    yline(ax, 0, '-', 'Color', p.ink, 'LineWidth', 0.75);
    scatter(ax, centerRoots, [0, 0], 30, 'o', 'filled', ...
        'MarkerFaceColor', p.primary, 'MarkerEdgeColor', p.paper, 'LineWidth', 0.5);
    scatter(ax, fullRoots, [0, 0], 30, 'd', 'filled', ...
        'MarkerFaceColor', p.secondary, 'MarkerEdgeColor', p.paper, 'LineWidth', 0.5);
    for root = centerRoots
        xline(ax, root, ':', 'Color', p.primary, 'LineWidth', 0.75);
    end
    for root = fullRoots
        xline(ax, root, ':', 'Color', p.secondary, 'LineWidth', 0.75);
    end
    text(ax, 0.02, 0.08, '正裕度区域 = 中心视线遮蔽成立', ...
        'Units', 'normalized', 'Color', p.primary, 'FontName', p.font, ...
        'FontSize', 7.0, 'VerticalAlignment', 'bottom');
    text(ax, 9.30, -3.15, sprintf('中心视线持续 %.4f s', diff(centerRoots)), ...
        'Color', p.primary, 'FontName', p.font, 'FontSize', 7.0, ...
        'FontWeight', 'bold', 'HorizontalAlignment', 'center');
    plot(ax, [8.35, 8.47], [5.74, 5.74], '-', ...
        'Color', p.primary, 'LineWidth', 1.35);
    text(ax, 8.50, 5.74, '目标中心视线', 'Color', p.primary, ...
        'FontName', p.font, 'FontSize', 7.0, 'VerticalAlignment', 'middle');
    plot(ax, [8.35, 8.47], [5.26, 5.26], '--', ...
        'Color', p.secondary, 'LineWidth', 1.20);
    text(ax, 8.50, 5.26, '完整圆柱全遮蔽', 'Color', p.secondary, ...
        'FontName', p.font, 'FontSize', 7.0, 'VerticalAlignment', 'middle');
    xlabel(ax, '任务时刻 t (s)', 'FontName', p.font, 'FontSize', 7.5);
    ylabel(ax, '遮蔽裕度 F(t) (m)', 'FontName', p.font, 'FontSize', 7.5);
    xlim(ax, [time(1), time(end)]);
    ylim(ax, yl);
    styleAxes(ax, p, true);
    panelLabel(ax, 'a', p, [-0.10, 1.04]);

    % B: entry is a pair of distinct root events.
    ax = axes(fig, 'Position', [0.735, 0.57, 0.235, 0.32]);
    entryWindow = linspace(centerRoots(1) - 0.035, fullRoots(1) + 0.035, 140);
    entryCenter = centerlineMargin(entryWindow, constants, strategy);
    entryFull = zeros(size(entryWindow));
    for k = 1:numel(entryWindow)
        entryFull(k) = fullCylinderMargin(entryWindow(k), constants, strategy, 720);
    end
    hold(ax, 'on');
    plot(ax, entryWindow, entryCenter, '-', 'Color', p.primary, 'LineWidth', 1.35);
    plot(ax, entryWindow, entryFull, '--', 'Color', p.secondary, 'LineWidth', 1.20);
    yline(ax, 0, '-', 'Color', p.ink, 'LineWidth', 0.70);
    scatter(ax, centerRoots(1), 0, 32, 'o', 'filled', ...
        'MarkerFaceColor', p.primary, 'MarkerEdgeColor', p.paper, 'LineWidth', 0.5);
    scatter(ax, fullRoots(1), 0, 32, 'd', 'filled', ...
        'MarkerFaceColor', p.secondary, 'MarkerEdgeColor', p.paper, 'LineWidth', 0.5);
    bracketY = min([entryCenter, entryFull]) + 0.22;
    plot(ax, [centerRoots(1), fullRoots(1)], [bracketY, bracketY], '-', ...
        'Color', p.accent, 'LineWidth', 0.85);
    plot(ax, [centerRoots(1), centerRoots(1)], bracketY + [-0.08, 0.08], '-', ...
        'Color', p.accent, 'LineWidth', 0.75);
    plot(ax, [fullRoots(1), fullRoots(1)], bracketY + [-0.08, 0.08], '-', ...
        'Color', p.accent, 'LineWidth', 0.75);
    text(ax, mean([centerRoots(1), fullRoots(1)]), 0.30, ...
        sprintf('进入延后 %.4f s', fullRoots(1) - centerRoots(1)), ...
        'Color', p.accent, 'FontName', p.font, 'FontSize', 7.0, ...
        'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom');
    xlabel(ax, '进入事件 t (s)', 'FontName', p.font, 'FontSize', 7.2);
    ylabel(ax, 'F(t) (m)', 'FontName', p.font, 'FontSize', 7.2);
    xlim(ax, [entryWindow(1), entryWindow(end)]);
    styleAxes(ax, p, true);
    panelLabel(ax, 'b', p, [-0.18, 1.06]);

    % C: both criteria leave at the same missile-endpoint event.
    ax = axes(fig, 'Position', [0.735, 0.15, 0.235, 0.32]);
    exitWindow = linspace(centerRoots(2) - 0.030, centerRoots(2) + 0.025, 150);
    exitCenter = centerlineMargin(exitWindow, constants, strategy);
    exitFull = zeros(size(exitWindow));
    for k = 1:numel(exitWindow)
        exitFull(k) = fullCylinderMargin(exitWindow(k), constants, strategy, 720);
    end
    hold(ax, 'on');
    plot(ax, exitWindow, exitCenter, '-', 'Color', p.primary, 'LineWidth', 1.35);
    plot(ax, exitWindow, exitFull, '--', 'Color', p.secondary, 'LineWidth', 1.20);
    yline(ax, 0, '-', 'Color', p.ink, 'LineWidth', 0.70);
    scatter(ax, centerRoots(2), 0, 34, 'o', 'filled', ...
        'MarkerFaceColor', p.ink, 'MarkerEdgeColor', p.paper, 'LineWidth', 0.5);
    xline(ax, centerRoots(2), ':', 'Color', p.ink, 'LineWidth', 0.8);
    text(ax, 0.05, 0.13, sprintf('共同退出 %.4f s', centerRoots(2)), ...
        'Units', 'normalized', 'Color', p.ink, 'FontName', p.font, ...
        'FontSize', 7.0, 'FontWeight', 'bold');
    xlabel(ax, '退出事件 t (s)', 'FontName', p.font, 'FontSize', 7.2);
    ylabel(ax, 'F(t) (m)', 'FontName', p.font, 'FontSize', 7.2);
    xlim(ax, [exitWindow(1), exitWindow(end)]);
    styleAxes(ax, p, true);
    panelLabel(ax, 'c', p, [-0.18, 1.06]);

    exportTriple(fig, outputDir, 'q1_occlusion_intervals', p);
    fprintf('  F3 Q1 roots: center [%.9f, %.9f], full [%.9f, %.9f] s.\n', ...
        centerRoots(1), centerRoots(2), fullRoots(1), fullRoots(2));
end

%% Figure F4: Q2 response surface recomputed in MATLAB
function renderQ2Response(q12, outputDir, p)
    constants = q12.constants;
    record = q12.q2.centerline;
    optimum = record.strategy;
    optimumHeading = double(optimum.heading_deg);
    optimumTime = double(optimum.explosion_time_s);
    optimumDuration = double(record.duration_s);
    gravity = 9.8;

    headings = linspace(1.0, 13.0, 37);
    explosionTimes = linspace(0.25, 1.25, 33);
    surface = zeros(numel(explosionTimes), numel(headings));
    for row = 1:numel(explosionTimes)
        for col = 1:numel(headings)
            strategy = makeBoundaryStrategy(headings(col), explosionTimes(row), gravity, constants);
            surface(row, col) = centerlineDuration(strategy, constants, 0.04);
        end
    end

    assert(abs(max(surface, [], 'all') - optimumDuration) < 0.30, ...
        'MATLAB response surface is inconsistent with the validated optimum.');

    % One hero evidence only: the surface, 95% boundary and optimum already
    % contain the two-dimensional sensitivity statement.  Separate one-factor
    % profiles merely repeat slices through this field and are intentionally
    % omitted from the manuscript figure.
    fig = publicationFigure(6.20, 3.75, p.paper);
    ax = axes(fig, 'Position', [0.090, 0.135, 0.795, 0.790]);
    levels = linspace(0, max(surface, [], 'all') + 0.01, 12);
    contourf(ax, headings, explosionTimes, surface, levels, 'LineStyle', 'none');
    colormap(ax, mutedDurationMap(192, p));
    hold(ax, 'on');
    [contours, contourHandle] = contour(ax, headings, explosionTimes, surface, ...
        [1, 2, 3, 4], 'Color', p.muted, 'LineWidth', 0.60);
    clabel(contours, contourHandle, 'FontName', p.font, 'FontSize', 7.0, ...
        'Color', p.muted, 'LabelSpacing', 220);
    plateau = 0.95 * optimumDuration;
    contour(ax, headings, explosionTimes, surface, [plateau, plateau], ...
        'Color', p.ink, 'LineWidth', 1.35);
    scatter(ax, optimumHeading, optimumTime, 62, 'p', ...
        'MarkerFaceColor', p.paper, 'MarkerEdgeColor', p.ink, 'LineWidth', 1.15);
    % Keep the numerical optimum off the dark contour field.  The opaque
    % paper-coloured note and leader preserve contrast in colour and grey.
    notePosition = [2.05, 1.18];
    plot(ax, [notePosition(1) + 1.05, optimumHeading], ...
        [notePosition(2) - 0.035, optimumTime], '-', ...
        'Color', p.ink, 'LineWidth', 0.75);
    text(ax, notePosition(1), notePosition(2), ...
        sprintf('T* = %.3f s   θ* = %.2f°   tᵉ* = %.3f s', ...
        optimumDuration, optimumHeading, optimumTime), ...
        'Color', p.ink, 'BackgroundColor', p.paper, ...
        'EdgeColor', 'none', 'Margin', 1.2, ...
        'FontName', p.font, 'FontSize', 7.2, 'FontWeight', 'bold', ...
        'VerticalAlignment', 'middle');
    text(ax, 0.955, 0.045, '实线闭合边界：T ≥ 0.95T*', ...
        'Units', 'normalized', 'Color', p.ink, 'FontName', p.font, ...
        'FontSize', 7.0, 'HorizontalAlignment', 'right', ...
        'BackgroundColor', p.paper, 'Margin', 1.2);
    text(ax, 0.015, 0.045, 'v = 140 m/s，tʳ = 0', ...
        'Units', 'normalized', 'Color', p.muted, ...
        'BackgroundColor', p.paper, 'Margin', 1.2, ...
        'FontName', p.font, 'FontSize', 7.0);
    xlabel(ax, '航向角 θ (°)', 'FontName', p.font, 'FontSize', 7.5);
    ylabel(ax, '起爆时刻 tᵉ (s)', 'FontName', p.font, 'FontSize', 7.5);
    styleAxes(ax, p, false);
    cb = colorbar(ax);
    cb.Position = [0.905, 0.175, 0.014, 0.700];
    cb.Color = p.muted;
    cb.FontName = p.font;
    cb.FontSize = 7.0;
    cb.LineWidth = 0.55;
    cb.Label.String = 'T (s)';
    cb.Label.Color = p.muted;
    cb.Label.FontName = p.font;
    cb.Label.FontSize = 7.0;

    % The manuscript-size export must remain readable without enlargement.
    fontObjects = findall(fig, '-property', 'FontSize');
    fontSizes = get(fontObjects, 'FontSize');
    if iscell(fontSizes)
        fontSizes = cell2mat(fontSizes);
    end
    assert(min(fontSizes) >= 7.0, ...
        'Q2 response-surface typography fell below the 7 pt floor.');

    exportTriple(fig, outputDir, 'q2_response_surface', p);
    fprintf('  F4 response surface: MATLAB max %.6f s, validated optimum %.6f s.\n', ...
        max(surface, [], 'all'), optimumDuration);
end

%% Figure F5: Q2 multi-seed convergence
function renderQ2Seeds(record, outputDir, p)
    runs = record.runs;
    n = numel(runs);
    exact = zeros(1, n);
    maxGeneration = 0;
    for k = 1:n
        exact(k) = double(runs(k).exact_duration_s);
        maxGeneration = max(maxGeneration, double(runs(k).best_so_far_trace(end).generation));
    end
    target = median(exact);
    generation = 1:maxGeneration;
    gaps = zeros(n, maxGeneration);
    for k = 1:n
        trace = runs(k).best_so_far_trace;
        x = double([trace.generation]);
        y = double([trace.best_coarse_duration_s]);
        held = interp1(x, y, generation, 'previous', 'extrap');
        gaps(k, :) = max(abs(held - target), 1e-6);
    end
    medianGap = median(gaps, 1);
    q25 = quantile(gaps, 0.25, 1);
    q75 = quantile(gaps, 0.75, 1);
    terminalSpan = double(record.summary.maximum_s - record.summary.minimum_s);

    fig = publicationFigure(6.20, 2.85, p.paper);
    ax = axes(fig, 'Position', [0.08, 0.20, 0.89, 0.72]);
    hold(ax, 'on');
    ax.YScale = 'log';
    patch(ax, [generation(1), generation(end), generation(end), generation(1)], ...
        [1e-6, 1e-6, 1e-3, 1e-3], p.secondaryLight, ...
        'EdgeColor', 'none', 'FaceAlpha', 0.78);
    patch(ax, [generation, fliplr(generation)], ...
        [q25, fliplr(q75)], p.primaryLight, ...
        'EdgeColor', 'none', 'FaceAlpha', 0.82);
    seedStyles = {'-', '--', '-.', ':', '-'};
    for k = 1:n
        styleIndex = 1 + mod(k - 1, numel(seedStyles));
        stairs(ax, generation, gaps(k, :), seedStyles{styleIndex}, ...
            'Color', p.grayLine, 'LineWidth', 0.72);
    end
    stairs(ax, generation, medianGap, '-', 'Color', p.primary, 'LineWidth', 1.65);

    thresholds = [1e-1, 1e-2, 1e-3];
    labelOffsets = [1.55, 1.62, 1.72];
    thresholdMarkers = {'o', 'd', 's'};
    for k = 1:numel(thresholds)
        yline(ax, thresholds(k), ':', ...
            'Color', blendColor(p.muted, p.paper, 0.50), 'LineWidth', 0.55);
        idx = find(medianGap <= thresholds(k), 1, 'first');
        if ~isempty(idx)
            scatter(ax, generation(idx), medianGap(idx), 26, thresholdMarkers{k}, ...
                'MarkerFaceColor', p.paper, 'MarkerEdgeColor', p.secondary, ...
                'LineWidth', 0.90);
            text(ax, generation(idx) + 2.0, medianGap(idx) * labelOffsets(k), ...
                sprintf('第 %d 代进入 10^{%d} s', generation(idx), round(log10(thresholds(k)))), ...
                'Color', p.secondary, 'FontName', p.font, 'FontSize', 7.0);
        end
    end
    text(ax, 0.02, 0.94, '灰色细阶梯：单次运行    蓝灰阶梯 / 淡带：中位数 / IQR', ...
        'Units', 'normalized', 'Color', p.muted, 'FontName', p.font, ...
        'FontSize', 7.0, 'VerticalAlignment', 'top');
    text(ax, 0.98, 0.94, ...
        sprintf('%d/%d 可行  ·  约束违反 0  ·  终值极差 %.1e s', n, n, terminalSpan), ...
        'Units', 'normalized', 'Color', p.ink, 'FontName', p.font, ...
        'FontSize', 7.2, 'FontWeight', 'bold', ...
        'HorizontalAlignment', 'right', 'VerticalAlignment', 'top');
    text(ax, 0.98, 0.08, '阴影：误差进入 10^{-3} s', ...
        'Units', 'normalized', 'Color', p.secondary, 'FontName', p.font, ...
        'FontSize', 7.0, 'HorizontalAlignment', 'right');
    xlabel(ax, '差分进化代数', 'FontName', p.font, 'FontSize', 7.6);
    ylabel(ax, '相对连续终值的绝对差 (s)', 'FontName', p.font, 'FontSize', 7.6);
    xlim(ax, [1, maxGeneration]);
    ylim(ax, [5e-7, max(gaps, [], 'all') * 3.0]);
    styleAxes(ax, p, true);

    exportTriple(fig, outputDir, 'q2_multiseed_stability', p);
    fprintf('  F5 Q2 multiseed: %d runs, terminal exact span %.3e s.\n', n, terminalSpan);
end

%% Figure F13: time-step convergence audit
function renderTimeStepAudit(q12, q1, outputDir, p)
    constants = q12.constants;
    q2 = q12.q2.centerline;
    steps = [0.50, 0.25, 0.10, 0.05, 0.02, 0.01, 0.005];
    strategies = {q1.strategy, q2.strategy};
    exact = [double(q1.centerline.duration_s), double(q2.duration_s)];
    errors = zeros(2, numel(steps));
    for row = 1:2
        for col = 1:numel(steps)
            sampled = sampledIndicatorDuration(strategies{row}, constants, steps(col));
            errors(row, col) = max(abs(sampled - exact(row)), 1e-8);
        end
    end

    fig = publicationFigure(6.20, 2.80, p.paper);
    ax = axes(fig, 'Position', [0.08, 0.20, 0.89, 0.72]);
    hold(ax, 'on');
    ax.XScale = 'log';
    ax.YScale = 'log';
    patch(ax, [min(steps), max(steps), max(steps), min(steps)], ...
        [5e-5, 5e-5, 1e-2, 1e-2], p.secondaryLight, ...
        'FaceAlpha', 0.80, 'EdgeColor', 'none');
    loglog(ax, steps, errors(1, :), '-o', 'Color', p.primary, ...
        'LineWidth', 1.35, 'MarkerSize', 4.2, 'MarkerFaceColor', p.primary, ...
        'MarkerEdgeColor', p.paper);
    loglog(ax, steps, errors(2, :), '--s', 'Color', p.secondary, ...
        'LineWidth', 1.35, 'MarkerSize', 4.2, 'MarkerFaceColor', p.secondary, ...
        'MarkerEdgeColor', p.paper);
    reference = 0.18 .* steps;
    loglog(ax, steps, reference, '-.', ...
        'Color', p.grayLine, 'LineWidth', 0.90);
    text(ax, 0.40, 0.75, 'O(Δt) 参考', 'Units', 'normalized', ...
        'Color', p.muted, 'FontName', p.font, 'FontSize', 7.0, ...
        'Rotation', 21);
    text(ax, 0.985, 0.08, '浅色区：误差 ≤ 0.01 s', ...
        'Units', 'normalized', 'Color', p.secondary, 'FontName', p.font, ...
        'FontSize', 7.0, 'HorizontalAlignment', 'right');
    text(ax, 0.985, 0.94, '网格加密  →', ...
        'Units', 'normalized', 'Color', p.muted, 'FontName', p.font, ...
        'FontSize', 7.0, 'HorizontalAlignment', 'right');
    text(ax, 0.02, 0.94, '●  问题一给定策略', 'Units', 'normalized', ...
        'Color', p.primary, 'FontName', p.font, 'FontSize', 7.0, ...
        'FontWeight', 'bold', 'VerticalAlignment', 'top');
    text(ax, 0.23, 0.94, '■  问题二优化策略', 'Units', 'normalized', ...
        'Color', p.secondary, 'FontName', p.font, 'FontSize', 7.0, ...
        'FontWeight', 'bold', 'VerticalAlignment', 'top');
    text(ax, 0.46, 0.94, '– –  O(Δt) 参考', 'Units', 'normalized', ...
        'Color', p.muted, 'FontName', p.font, 'FontSize', 7.0, ...
        'VerticalAlignment', 'top');
    xlabel(ax, '均匀采样步长 Δt (s)', 'FontName', p.font, 'FontSize', 7.6);
    ylabel(ax, '相对连续验根结果的绝对误差 (s)', ...
        'FontName', p.font, 'FontSize', 7.6);
    ax.XDir = 'reverse';
    xticks(ax, fliplr(steps));
    xticklabels(ax, compose('%g', fliplr(steps)));
    ylim(ax, [5e-5, 0.8]);
    styleAxes(ax, p, true);

    exportTriple(fig, outputDir, 'time_step_convergence', p);
    fprintf('  F13 time-step errors Q1/Q2 at dt=0.005: %.6g / %.6g s.\n', ...
        errors(1, end), errors(2, end));
end

%% Figure F14: Q3/Q4 multi-seed evidence
function renderQ34Seeds(record, outputDir, p)
    q3 = record.problems.Q3;
    q4 = record.problems.Q4;
    q3Runs = q3.runs;
    n3 = numel(q3Runs);
    maxIteration = 0;
    for k = 1:n3
        maxIteration = max(maxIteration, double(q3Runs(k).best_so_far_trace(end).iteration));
    end
    iteration = 0:maxIteration;
    q3Matrix = zeros(n3, numel(iteration));
    for k = 1:n3
        trace = q3Runs(k).best_so_far_trace;
        x = double([trace.iteration]);
        y = double([trace.best_fast_objective_s]);
        q3Matrix(k, :) = interp1(x, y, iteration, 'previous', 'extrap');
    end
    q3Median = median(q3Matrix, 1);
    q3Q25 = quantile(q3Matrix, 0.25, 1);
    q3Q75 = quantile(q3Matrix, 0.75, 1);

    fig = publicationFigure(6.20, 3.55, p.paper);
    ax = axes(fig, 'Position', [0.075, 0.15, 0.575, 0.78]);
    hold(ax, 'on');
    patch(ax, [iteration, fliplr(iteration)], [q3Q25, fliplr(q3Q75)], ...
        p.primaryLight, 'EdgeColor', 'none', 'FaceAlpha', 0.82);
    seedStyles = {'-', '--', '-.', ':', '-'};
    for k = 1:n3
        styleIndex = 1 + mod(k - 1, numel(seedStyles));
        stairs(ax, iteration, q3Matrix(k, :), seedStyles{styleIndex}, ...
            'Color', p.grayLine, 'LineWidth', 0.78);
    end
    stairs(ax, iteration, q3Median, '-', 'Color', p.primary, 'LineWidth', 1.65);
    accepted = false(size(iteration));
    for k = 1:n3
        trace = q3Runs(k).best_so_far_trace;
        accepted(double([trace([trace.accepted_improvement]).iteration]) + 1) = true;
    end
    eventIdx = find(accepted) - 1;
    eventIdx = eventIdx(eventIdx >= 0);
    if ~isempty(eventIdx)
        selected = eventIdx(round(linspace(1, numel(eventIdx), min(7, numel(eventIdx)))));
        scatter(ax, selected, q3Median(selected + 1), 22, '^', ...
            'MarkerFaceColor', p.paper, 'MarkerEdgeColor', p.secondary, 'LineWidth', 0.9);
    end
    text(ax, 0.02, 0.96, '中位数迄今最优轨迹', ...
        'Units', 'normalized', 'Color', p.primary, 'FontName', p.font, ...
        'FontSize', 7.2, 'FontWeight', 'bold', 'VerticalAlignment', 'top');
    text(ax, 0.02, 0.90, '灰色细阶梯：单种子    淡蓝灰带：四分位距    灰色空心三角：接受改进事件', ...
        'Units', 'normalized', 'Color', p.muted, 'FontName', p.font, ...
        'FontSize', 7.0, 'VerticalAlignment', 'top');
    xlabel(ax, '局部随机精化迭代', 'FontName', p.font, 'FontSize', 7.6);
    ylabel(ax, '问题三迄今最优粗评分 (s)', 'FontName', p.font, 'FontSize', 7.6);
    xlim(ax, [0, maxIteration]);
    ylim(ax, [min(q3Matrix, [], 'all') - 0.03, ...
        max(q3Matrix, [], 'all') + 0.32]);
    styleAxes(ax, p, true);
    panelLabel(ax, 'a', p, [-0.10, 1.04]);

    ax = axes(fig, 'Position', [0.735, 0.58, 0.235, 0.32]);
    endpointDots(ax, q3, false, p, '问题三', p.primary);
    xlabel(ax, '并集时长 (s)', 'FontName', p.font, 'FontSize', 7.2);
    panelLabel(ax, 'b', p, [-0.18, 1.06]);

    ax = axes(fig, 'Position', [0.735, 0.15, 0.235, 0.32]);
    endpointDots(ax, q4, true, p, '问题四', p.secondary);
    xlabel(ax, '相对中位数偏差 (ms)', 'FontName', p.font, 'FontSize', 7.2);
    panelLabel(ax, 'c', p, [-0.18, 1.06]);

    exportTriple(fig, outputDir, 'q3_q4_multiseed_stability', p);
    fprintf('  F14 Q3/Q4 spans: %.6f s / %.3f ms.\n', ...
        double(q3.summary.maximum_s - q3.summary.minimum_s), ...
        1000 * double(q4.summary.maximum_s - q4.summary.minimum_s));
end

%% Shared plotting and geometry helpers
function endpointDots(ax, record, centreMilliseconds, p, label, color)
    hold(ax, 'on');
    runs = record.runs;
    n = numel(runs);
    values = zeros(1, n);
    seeds = zeros(1, n);
    for k = 1:n
        values(k) = double(runs(k).final_exact_objective_s);
        seeds(k) = double(runs(k).seed);
    end
    centre = median(values);
    if centreMilliseconds
        plotted = (values - centre) * 1000;
        lineAt = 0;
        span = 1000 * double(record.summary.maximum_s - record.summary.minimum_s);
        spanText = sprintf('终值极差 %.0f ms', span);
    else
        plotted = values;
        lineAt = centre;
        span = double(record.summary.maximum_s - record.summary.minimum_s);
        spanText = sprintf('终值极差 %.3f s', span);
    end
    y = [0.74, 0.30, 0.58, 0.18, 0.45];
    marker = 'o';
    if centreMilliseconds
        marker = 'd';
    end
    xline(ax, lineAt, '--', 'Color', p.muted, 'LineWidth', 0.80);
    scatter(ax, plotted, y, 44, marker, 'filled', ...
        'MarkerFaceColor', color, 'MarkerEdgeColor', p.paper, 'LineWidth', 0.55);
    [~, order] = sort(plotted);
    labelIndices = unique([order(1), order(end)]);
    for idx = labelIndices
        text(ax, plotted(idx), y(idx) + 0.11, sprintf('%02d', mod(seeds(idx), 100)), ...
            'Color', p.muted, 'FontName', p.font, 'FontSize', 7.0, ...
            'HorizontalAlignment', 'center');
    end
    labelX = 0.03;
    labelY = 0.94;
    if centreMilliseconds
        labelX = 0.23;
        labelY = 0.80;
    end
    text(ax, labelX, labelY, label, 'Units', 'normalized', ...
        'Color', p.ink, 'FontName', p.font, 'FontSize', 7.5, ...
        'FontWeight', 'bold', 'VerticalAlignment', 'top');
    text(ax, 0.97, 0.94, spanText, 'Units', 'normalized', ...
        'Color', color, 'FontName', p.font, 'FontSize', 7.0, ...
        'FontWeight', 'bold', 'HorizontalAlignment', 'right', ...
        'VerticalAlignment', 'top');
    if centreMilliseconds
        improvements = false(1, n);
        for k = 1:n
            trace = runs(k).best_so_far_trace;
            improvements(k) = double(trace(end).best_fast_objective_s) > ...
                double(trace(1).best_fast_objective_s) + 1e-12;
        end
        text(ax, 0.03, 0.10, sprintf('粗评轨迹：%d/%d 个种子发生改进', ...
            sum(improvements), n), 'Units', 'normalized', ...
            'Color', p.muted, 'FontName', p.font, 'FontSize', 7.0);
    end
    yticks(ax, []);
    ylim(ax, [0.02, 0.98]);
    spread = max(plotted) - min(plotted);
    if spread < 1e-12
        spread = 1;
    end
    xlim(ax, [min(plotted) - 0.10*spread - eps, max(plotted) + 0.10*spread + eps]);
    styleAxes(ax, p, true);
    ax.YGrid = 'off';
end

function strategy = makeBoundaryStrategy(headingDeg, explosionTime, gravity, constants)
    heading = deg2rad(double(headingDeg));
    speed = 140.0;
    strategy.heading_deg = double(headingDeg);
    strategy.heading_rad = heading;
    strategy.heading_unit = [cos(heading), sin(heading), 0];
    strategy.speed_mps = speed;
    strategy.release_time_s = 0.0;
    strategy.fuse_delay_s = double(explosionTime);
    strategy.explosion_time_s = double(explosionTime);
    fy1 = rowVector(constants.fy1_initial_m);
    position = fy1 + speed * double(explosionTime) .* strategy.heading_unit;
    position(3) = position(3) - 0.5 * double(gravity) * double(explosionTime)^2;
    strategy.explosion_position_m = position;
end

function duration = centerlineDuration(strategy, constants, maxStep)
    startTime = double(strategy.explosion_time_s);
    endTime = min(startTime + double(constants.smoke_lifetime_s), ...
        double(constants.missile_impact_time_s));
    n = max(3, ceil((endTime - startTime) / maxStep) + 1);
    time = linspace(startTime, endTime, n);
    margin = centerlineMargin(time, constants, strategy);
    roots = [];
    for k = 1:numel(time)-1
        if margin(k) == 0
            roots(end+1) = time(k); %#ok<AGROW>
        elseif margin(k) * margin(k+1) < 0
            root = fzero(@(t) centerlineMargin(t, constants, strategy), ...
                [time(k), time(k+1)]);
            roots(end+1) = root; %#ok<AGROW>
        end
    end
    boundaries = unique([startTime, roots, endTime]);
    duration = 0;
    for k = 1:numel(boundaries)-1
        mid = 0.5 * (boundaries(k) + boundaries(k+1));
        if centerlineMargin(mid, constants, strategy) >= 0
            duration = duration + boundaries(k+1) - boundaries(k);
        end
    end
end

function sampled = sampledIndicatorDuration(strategy, constants, step)
    startTime = double(strategy.explosion_time_s);
    endTime = min(startTime + double(constants.smoke_lifetime_s), ...
        double(constants.missile_impact_time_s));
    count = max(1, ceil((endTime - startTime) / step));
    time = linspace(startTime, endTime, count + 1);
    active = centerlineMargin(time, constants, strategy) >= 0;
    sampled = trapz(time, double(active));
end

function margin = centerlineMargin(time, constants, strategy)
    time = double(time(:));
    missile = rowVector(constants.missile_initial_m) + ...
        time .* rowVector(constants.missile_velocity_mps);
    cloud = repmat(rowVector(strategy.explosion_position_m), numel(time), 1);
    cloud(:, 3) = cloud(:, 3) - double(constants.smoke_sink_speed_mps) .* ...
        (time - double(strategy.explosion_time_s));
    target = targetCenter(constants);
    segment = target - missile;
    relative = cloud - missile;
    lambda = sum(relative .* segment, 2) ./ sum(segment .* segment, 2);
    lambda = min(1, max(0, lambda));
    closest = missile + lambda .* segment;
    margin = double(constants.smoke_radius_m) - ...
        sqrt(sum((cloud - closest).^2, 2));
    margin = reshape(margin, 1, []);
end

function margin = fullCylinderMargin(time, constants, strategy, nAzimuth)
    missile = missilePosition(time, constants);
    cloud = smokeCenter(time, constants, strategy);
    relative = cloud - missile;
    rho = norm(relative);
    radius = double(constants.smoke_radius_m);
    if rho <= radius
        margin = radius - rho;
        return;
    end
    axisVector = relative / rho;
    phi = linspace(0, 2*pi, nAzimuth + 1)';
    phi(end) = [];
    bottomCenter = rowVector(constants.target_bottom_center_m);
    targetRadius = double(constants.target_radius_m);
    targetHeight = double(constants.target_height_m);
    rim = [ ...
        bottomCenter(1) + targetRadius*cos(phi), ...
        bottomCenter(2) + targetRadius*sin(phi), ...
        zeros(size(phi)) + bottomCenter(3); ...
        bottomCenter(1) + targetRadius*cos(phi), ...
        bottomCenter(2) + targetRadius*sin(phi), ...
        zeros(size(phi)) + bottomCenter(3) + targetHeight ...
    ];
    sight = rim - missile;
    cosine = (sight * axisVector') ./ sqrt(sum(sight.^2, 2));
    minCosine = min(cosine);
    if minCosine <= 0
        required = rho;
    else
        required = rho * sqrt(max(0, 1 - minCosine^2));
    end
    horizontal = norm(missile(1:2) - bottomCenter(1:2));
    horizontalGap = max(0, horizontal - targetRadius);
    if missile(3) < bottomCenter(3)
        verticalGap = bottomCenter(3) - missile(3);
    elseif missile(3) > bottomCenter(3) + targetHeight
        verticalGap = missile(3) - bottomCenter(3) - targetHeight;
    else
        verticalGap = 0;
    end
    targetRange = hypot(horizontalGap, verticalGap);
    rangeMargin = targetRange - (rho + radius);
    margin = min(radius - required, rangeMargin);
end

function position = missilePosition(time, constants)
    position = rowVector(constants.missile_initial_m) + ...
        double(time) .* rowVector(constants.missile_velocity_mps);
end

function center = smokeCenter(time, constants, strategy)
    center = rowVector(strategy.explosion_position_m);
    center(3) = center(3) - double(constants.smoke_sink_speed_mps) .* ...
        (double(time) - double(strategy.explosion_time_s));
end

function target = targetCenter(constants)
    target = rowVector(constants.target_bottom_center_m) + ...
        [0, 0, double(constants.target_height_m)/2];
end

function regions = contiguousRegions(x, mask)
    changes = diff([false, mask, false]);
    starts = find(changes == 1);
    stops = find(changes == -1) - 1;
    regions = [x(starts)', x(stops)'];
end

function fig = publicationFigure(width, height, background)
    fig = figure('Visible', 'off', 'Color', background, 'Units', 'inches', ...
        'Position', [0.7, 0.7, width, height], ...
        'PaperPositionMode', 'auto', 'Renderer', 'painters');
end

function styleAxes(ax, p, useGrid)
    ax.FontName = p.font;
    ax.FontSize = 7.0;
    ax.LineWidth = 0.65;
    ax.XColor = p.muted;
    ax.YColor = p.muted;
    ax.Color = p.panel;
    ax.Box = 'off';
    ax.TickDir = 'out';
    ax.TickLength = [0.014, 0.014];
    ax.Layer = 'top';
    if useGrid
        ax.XGrid = 'on';
        ax.YGrid = 'on';
        ax.GridColor = p.grid;
        ax.GridAlpha = 0.70;
        ax.MinorGridAlpha = 0;
    end
end

function panelLabel(ax, label, p, location)
    text(ax, location(1), location(2), lower(label), ...
        'Units', 'normalized', 'Color', p.ink, 'FontName', p.font, ...
        'FontSize', 9.2, 'FontWeight', 'bold', ...
        'HorizontalAlignment', 'left', 'VerticalAlignment', 'top', ...
        'Clipping', 'off');
end

function exportTriple(fig, outputDir, stem, p)
    allText = findall(fig, '-property', 'FontName');
    set(allText, 'FontName', p.font);
    pngPath = fullfile(outputDir, [stem, '.png']);
    pdfPath = fullfile(outputDir, [stem, '.pdf']);
    svgPath = fullfile(outputDir, [stem, '.svg']);
    set(fig, 'InvertHardcopy', 'off');
    print(fig, pngPath, '-dpng', '-r360');
    exportgraphics(fig, pdfPath, 'ContentType', 'vector', 'BackgroundColor', p.paper);
    exportgraphics(fig, svgPath, 'ContentType', 'vector', 'BackgroundColor', p.paper);
    info = imfinfo(pngPath);
    assert(info.Width >= 2200, '%s PNG width is below the 6.2-inch QA target.', stem);
    assert(isfile(pdfPath) && isfile(svgPath), '%s vector export failed.', stem);
    fprintf('  exported %-30s %d x %d px\n', stem, info.Width, info.Height);
    close(fig);
end

function map = mutedDurationMap(count, p)
    % A monotone paper-to-denim map keeps the response surface ordered and
    % removes the muddy blue-green cast. Clay remains reserved for the
    % optimum marker and therefore never enters the continuous scale.
    anchors = p.sequentialAnchors;
    anchorX = linspace(0, 1, size(anchors, 1));
    sampleX = linspace(0, 1, count);
    map = interp1(anchorX, anchors, sampleX, 'pchip');
    map = min(1, max(0, map));
end

function color = blendColor(foreground, background, foregroundWeight)
    color = foregroundWeight .* foreground + ...
        (1 - foregroundWeight) .* background;
end

function value = readJson(path)
    assert(isfile(path), 'Validation record not found: %s', path);
    value = jsondecode(fileread(path));
end

function vector = rowVector(value)
    vector = reshape(double(value), 1, []);
end

function rgb = hexColor(code)
    code = char(erase(string(code), '#'));
    rgb = [hex2dec(code(1:2)), hex2dec(code(3:4)), hex2dec(code(5:6))] / 255;
end
