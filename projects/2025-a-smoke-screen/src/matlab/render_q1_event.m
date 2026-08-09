%% Q1 concrete-event storyboard (MATLAB, validated data only)
% The figure is intentionally composed at its final manuscript width.
% It reads the independent validation record, derives the endpoint-switch
% event from the finite sightline geometry, and exports raster + vector files.

clearvars;
close all;
clc;

scriptPath = mfilename('fullpath');
projectRoot = fileparts(fileparts(fileparts(scriptPath)));
dataPath = fullfile(projectRoot, 'validation', 'q1_q2_independent.json');
outputDir = fullfile(projectRoot, 'figures');
assert(isfile(dataPath), 'Validation record not found: %s', dataPath);
assert(isfolder(outputDir), 'Figure directory not found: %s', outputDir);

record = jsondecode(fileread(dataPath));
q1Fields = fieldnames(record.q1);
q1Index = find(contains(q1Fields, '9_80'), 1, 'first');
assert(~isempty(q1Index), 'The g = 9.80 m/s^2 Q1 record is missing.');
q1 = record.q1.(q1Fields{q1Index});
constants = record.constants;
strategy = q1.strategy;

releaseTime = double(strategy.release_time_s);
explosionTime = double(strategy.explosion_time_s);
centerInterval = double(q1.centerline.intervals_s(1, :));
entryTime = centerInterval(1);
exitTime = centerInterval(2);
lambdaFunction = @(time) sightlineLambda(time, constants, strategy);
switchTime = fzero(lambdaFunction, [entryTime, exitTime]);

entryState = localGeometry(entryTime, constants, strategy);
switchState = localGeometry(switchTime, constants, strategy);
exitState = localGeometry(exitTime, constants, strategy);
smokeRadius = double(constants.smoke_radius_m);

% The three critical states are strict geometry checks, not decorative poses.
assert(abs(entryState.distance - smokeRadius) < 1e-6, ...
    'Entry state is not tangent to the finite sightline.');
assert(abs(switchState.lambda0) < 1e-10, ...
    'Endpoint-switch state does not satisfy lambda_0 = 0.');
assert(abs(exitState.distance - smokeRadius) < 1e-6, ...
    'Exit state is not tangent to the missile endpoint.');

% Restrained editorial palette. Object identity is carried primarily by
% marker/line style; colour is limited to cool structure and warm emphasis.
paper = hexColor('#FFFFFF');
ink = hexColor('#1E2A32');
muted = hexColor('#647078');
gridColor = hexColor('#D6DEE1');
primary = hexColor('#2F6079');
  secondary = hexColor('#59636A');
warm = hexColor('#B5782F');
  wine = hexColor('#8B4E5A');

missileColor = ink;
droneColor = primary;
bombColor = muted;
  smoke = primary;
  smokeLight = tintColor(primary, paper, 0.16);
sightlineColor = muted;
  targetColor = ink;
fontName = 'Microsoft YaHei';

fig = figure( ...
    'Visible', 'off', ...
    'Color', paper, ...
    'Renderer', 'painters', ...
    'Units', 'inches', ...
    'Position', [0.7, 0.7, 6.20, 4.25], ...
    'PaperPositionMode', 'auto');

%% A. Main x-z trajectory: every marker is placed at its validated time.
axMain = axes(fig, 'Position', [0.075, 0.350, 0.555, 0.575]);
hold(axMain, 'on');

missileInitial = rowVector(constants.missile_initial_m);
missileVelocity = rowVector(constants.missile_velocity_mps);
droneInitial = rowVector(constants.fy1_initial_m);
heading = rowVector(strategy.heading_unit);
speed = double(strategy.speed_mps);
releasePosition = rowVector(strategy.release_position_m);
explosionPosition = rowVector(strategy.explosion_position_m);
target = rowVector(constants.target_bottom_center_m) + ...
    [0, 0, double(constants.target_height_m) / 2];

tMissile = linspace(0, exitTime, 240)';
missilePath = missileInitial + tMissile .* missileVelocity;
tDrone = linspace(0, exitTime, 180)';
dronePath = droneInitial + (speed .* tDrone) .* heading;
tBomb = linspace(releaseTime, explosionTime, 120)';
dtBomb = tBomb - releaseTime;
bombPath = releasePosition + (speed .* dtBomb) .* heading;
bombPath(:, 3) = bombPath(:, 3) - 0.5 * double(q1.gravity_mps2) .* dtBomb.^2;
tSmoke = linspace(explosionTime, ...
    explosionTime + double(constants.smoke_lifetime_s), 160)';
smokePath = repmat(explosionPosition, numel(tSmoke), 1);
smokePath(:, 3) = smokePath(:, 3) - ...
    double(constants.smoke_sink_speed_mps) .* (tSmoke - explosionTime);

plot(axMain, missilePath(:, 1) / 1000, missilePath(:, 3) / 1000, ...
    '-.', 'Color', missileColor, 'LineWidth', 1.55);
plot(axMain, dronePath(:, 1) / 1000, dronePath(:, 3) / 1000, ...
    '-', 'Color', droneColor, 'LineWidth', 1.70);
plot(axMain, bombPath(:, 1) / 1000, bombPath(:, 3) / 1000, ...
    '--', 'Color', bombColor, 'LineWidth', 1.30);

% Three restrained cloud silhouettes indicate sinking without turning the
% trajectory panel into a storyboard.
cloudIndices = unique(round(linspace(1, size(smokePath, 1), 3)));
scatter(axMain, smokePath(cloudIndices, 1) / 1000, ...
    smokePath(cloudIndices, 3) / 1000, [90, 112, 90], 'o', 'filled', ...
    'MarkerFaceColor', smokeLight, 'MarkerEdgeColor', smoke, ...
    'MarkerFaceAlpha', 0.26, 'MarkerEdgeAlpha', 0.52, 'LineWidth', 0.55);
plot(axMain, smokePath(:, 1) / 1000, smokePath(:, 3) / 1000, ...
    '-', 'Color', smoke, 'LineWidth', 2.15);

% The entry/exit sightlines are clipped by the zoomed mission window.
for time = [entryTime, exitTime]
    missile = missilePosition(time, constants);
    plot(axMain, [missile(1), target(1)] / 1000, ...
        [missile(3), target(3)] / 1000, ':', ...
        'Color', sightlineColor, 'LineWidth', 1.05);
end

scatter(axMain, missileInitial(1) / 1000, missileInitial(3) / 1000, ...
    38, '>', 'filled', 'MarkerFaceColor', missileColor, 'MarkerEdgeColor', paper, ...
    'LineWidth', 0.5);
scatter(axMain, droneInitial(1) / 1000, droneInitial(3) / 1000, ...
    40, '^', 'filled', 'MarkerFaceColor', droneColor, 'MarkerEdgeColor', paper, ...
    'LineWidth', 0.5);
scatter(axMain, releasePosition(1) / 1000, releasePosition(3) / 1000, ...
    34, 'd', 'filled', 'MarkerFaceColor', primary, 'MarkerEdgeColor', paper, ...
    'LineWidth', 0.70);
scatter(axMain, explosionPosition(1) / 1000, explosionPosition(3) / 1000, ...
    54, 'o', 'filled', 'MarkerFaceColor', warm, 'MarkerEdgeColor', paper, ...
    'LineWidth', 0.55);

% Direct object labels replace a legend; exact event times are centralised
% in panel c instead of being repeated throughout the trajectory.
text(axMain, 19.82, 1.997, 'M1 导弹', 'Color', missileColor, ...
    'FontName', fontName, 'FontSize', 7.2, 'FontWeight', 'bold', ...
    'HorizontalAlignment', 'right');
text(axMain, 17.79, 1.817, 'FY1', 'Color', droneColor, ...
    'FontName', fontName, 'FontSize', 7.2, 'FontWeight', 'bold');
text(axMain, explosionPosition(1) / 1000 - 0.04, ...
    explosionPosition(3) / 1000 - 0.020, '起爆', ...
    'Color', warm, 'FontName', fontName, 'FontSize', 7.0, ...
    'HorizontalAlignment', 'center');
text(axMain, smokePath(round(end / 2), 1) / 1000 + 0.08, ...
    smokePath(round(end / 2), 3) / 1000, '烟幕中心', ...
    'Color', smoke, 'FontName', fontName, 'FontSize', 7.0, ...
    'FontWeight', 'bold', 'HorizontalAlignment', 'left');
text(axMain, 0.02, 0.97, '主 x-z 轨迹', 'Units', 'normalized', ...
    'Color', ink, 'FontName', fontName, 'FontSize', 7.8, ...
    'FontWeight', 'bold', 'VerticalAlignment', 'top');

xlim(axMain, [16.55, 20.08]);
ylim(axMain, [1.655, 2.035]);
xlabel(axMain, 'x (km)', 'FontName', fontName, 'FontSize', 7.6);
ylabel(axMain, 'z (km)', 'FontName', fontName, 'FontSize', 7.6);
styleAxes(axMain, fontName, ink, gridColor, paper, true);
panelLabel(axMain, 'A', fontName, ink, [-0.085, 1.035]);

%% B. One finite-sightline geometry panel at the decisive endpoint switch.
axGeometry = axes(fig, 'Position', [0.690, 0.380, 0.275, 0.515]);
drawFiniteGeometry(axGeometry, switchState, smokeRadius, switchTime, ...
    fontName, paper, ink, muted, smoke, smokeLight, warm, targetColor);
panelLabel(axGeometry, 'B', fontName, ink, [-0.10, 1.03]);

%% C. Shared five-event time axis; every exact time appears only here.
axTime = axes(fig, 'Position', [0.075, 0.085, 0.895, 0.185]);
hold(axTime, 'on');
xMin = releaseTime - 0.70;
xMax = exitTime + 0.70;
plot(axTime, [xMin, xMax], [0, 0], '-', 'Color', gridColor, ...
    'LineWidth', 2.0);
patch(axTime, [entryTime, exitTime, exitTime, entryTime], ...
      [-0.13, -0.13, 0.13, 0.13], tintColor(primary, paper, 0.12), ...
      'EdgeColor', primary, 'LineStyle', '--', 'LineWidth', 0.75, ...
    'FaceAlpha', 0.96);

eventTimes = [releaseTime, explosionTime, entryTime, switchTime, exitTime];
eventNames = {'投放', '起爆', '进入', '端点切换', '退出'};
  eventColors = [ink; warm; primary; muted; ink];
eventMarkers = {'d', 'o', '^', 's', 'v'};
eventSizes = [36, 46, 42, 34, 42];
labelX = [releaseTime + 0.24, explosionTime, entryTime - 0.18, ...
    switchTime - 0.50, exitTime + 0.08];
labelY = [-0.50, 0.50, -0.50, 0.50, -0.50];

for k = 1:numel(eventTimes)
    scatter(axTime, eventTimes(k), 0, eventSizes(k), ...
        eventMarkers{k}, 'filled', 'MarkerFaceColor', eventColors(k, :), ...
        'MarkerEdgeColor', paper, 'LineWidth', 0.55);
    leaderEndY = labelY(k) - 0.12 * sign(labelY(k));
    plot(axTime, [eventTimes(k), eventTimes(k), labelX(k)], ...
        [0.13 * sign(labelY(k)), leaderEndY, leaderEndY], '-', ...
        'Color', eventColors(k, :), 'LineWidth', 0.75);
    text(axTime, labelX(k), labelY(k), ...
        sprintf('%s\n%.4f s', eventNames{k}, eventTimes(k)), ...
        'Color', eventColors(k, :), 'FontName', fontName, ...
        'FontSize', 7.0, 'FontWeight', 'bold', ...
        'HorizontalAlignment', 'center', ...
        'VerticalAlignment', 'middle');
end

text(axTime, (entryTime + exitTime) / 2, 0, ...
    sprintf('%.4f s', exitTime - entryTime), ...
      'Color', primary, 'BackgroundColor', paper, 'Margin', 0.8, ...
    'FontName', fontName, 'FontSize', 7.0, ...
    'FontWeight', 'bold', 'HorizontalAlignment', 'center', ...
    'VerticalAlignment', 'middle');

xlim(axTime, [xMin, xMax]);
ylim(axTime, [-0.82, 0.82]);
yticks(axTime, []);
xticks(axTime, [2, 4, 6, 8, 9]);
xlabel(axTime, '任务时刻 t (s)', 'FontName', fontName, 'FontSize', 7.6);
styleAxes(axTime, fontName, ink, gridColor, paper, false);
axTime.XGrid = 'off';
text(axTime, 0.02, 0.98, '共享时间轴事件序列', 'Units', 'normalized', ...
    'Color', ink, 'FontName', fontName, 'FontSize', 7.6, ...
    'FontWeight', 'bold', 'VerticalAlignment', 'top');
panelLabel(axTime, 'C', fontName, ink, [-0.045, 1.06]);

% Enforce readable final-size typography across every graphical object.
allText = findall(fig, '-property', 'FontName');
set(allText, 'FontName', fontName);
fontObjects = findall(fig, '-property', 'FontSize');
fontSizes = get(fontObjects, 'FontSize');
if iscell(fontSizes)
    fontSizes = cell2mat(fontSizes);
end
assert(min(fontSizes) >= 7.0, ...
    'Q1 event figure typography fell below the 7 pt floor.');

pngPath = fullfile(outputDir, 'modeling_workflow.png');
pdfPath = fullfile(outputDir, 'modeling_workflow.pdf');
svgPath = fullfile(outputDir, 'modeling_workflow.svg');
print(fig, pngPath, '-dpng', '-r360');
exportgraphics(fig, pdfPath, 'ContentType', 'vector', 'BackgroundColor', paper);
exportgraphics(fig, svgPath, 'ContentType', 'vector', 'BackgroundColor', paper);

pngInfo = imfinfo(pngPath);
assert(pngInfo.Width >= 2200 && pngInfo.Height >= 1500, ...
    'PNG export is smaller than the intended final-size QA raster.');
assert(isfile(pdfPath) && isfile(svgPath), 'Vector export failed.');

fprintf('Q1 MATLAB event storyboard exported.\n');
fprintf('  release %.6f | explosion %.6f | entry %.6f | switch %.6f | exit %.6f s\n', ...
    releaseTime, explosionTime, entryTime, switchTime, exitTime);
fprintf('  switch-to-exit gap %.6f s | centerline duration %.6f s\n', ...
    exitTime - switchTime, exitTime - entryTime);
fprintf('  PNG %d x %d px\n', pngInfo.Width, pngInfo.Height);

%% Local helper functions
function vector = rowVector(value)
    vector = reshape(double(value), 1, []);
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

function lambda0 = sightlineLambda(time, constants, strategy)
    missile = missilePosition(time, constants);
    center = smokeCenter(time, constants, strategy);
    target = rowVector(constants.target_bottom_center_m) + ...
        [0, 0, double(constants.target_height_m) / 2];
    sightline = target - missile;
    lambda0 = dot(center - missile, sightline) / dot(sightline, sightline);
end

function state = localGeometry(time, constants, strategy)
    missile = missilePosition(time, constants);
    center = smokeCenter(time, constants, strategy);
    target = rowVector(constants.target_bottom_center_m) + ...
        [0, 0, double(constants.target_height_m) / 2];
    sightline = target - missile;
    sightlineNorm = norm(sightline);
    sightlineUnit = sightline / sightlineNorm;
    relative = center - missile;
    along = dot(relative, sightlineUnit);
    normal = sqrt(max(0, dot(relative, relative) - along^2));
    lambda0 = along / sightlineNorm;
    lambdaStar = min(1, max(0, lambda0));
    closest = missile + lambdaStar .* sightline;
    state.time = double(time);
    state.missile = missile;
    state.cloud = center;
    state.along = along;
    state.normal = normal;
    state.lambda0 = lambda0;
    state.lambdaStar = lambdaStar;
    state.distance = norm(center - closest);
end

function drawFiniteGeometry(ax, state, smokeRadius, switchTime, ...
        fontName, paper, ink, muted, smoke, smokeLight, accent, targetColor)
    hold(ax, 'on');
    % Normalise by R so that the finite-segment endpoint switch is visible
    % at manuscript scale while all printed metrics remain dimensional.
    radius = 1;
    center = [0, state.distance / smokeRadius];
    missile = [0, 0];
    target = [3.0, 0];
    theta = linspace(0, 2 * pi, 240);
    patch(ax, center(1) + radius * cos(theta), ...
        center(2) + radius * sin(theta), smokeLight, ...
        'EdgeColor', smoke, 'LineWidth', 1.15, 'FaceAlpha', 0.82);
    plot(ax, [missile(1), target(1)], [0, 0], '-', ...
        'Color', ink, 'LineWidth', 1.25);
    quiver(ax, 2.48, 0, 0.42, 0, 0, ...
        'Color', targetColor, 'LineWidth', 0.85, 'MaxHeadSize', 0.80);
    plot(ax, [center(1), missile(1)], [center(2), missile(2)], '--', ...
        'Color', accent, 'LineWidth', 1.0);
    scatter(ax, center(1), center(2), 20, 'o', 'filled', ...
        'MarkerFaceColor', smoke, 'MarkerEdgeColor', paper, 'LineWidth', 0.45);
    scatter(ax, missile(1), missile(2), 28, 'o', ...
        'MarkerFaceColor', paper, 'MarkerEdgeColor', accent, 'LineWidth', 1.0);
    scatter(ax, target(1), target(2), 28, 's', 'filled', ...
        'MarkerFaceColor', ink, 'MarkerEdgeColor', paper, 'LineWidth', 0.45);

    text(ax, center(1) + 0.08, center(2) + 0.22, 'C(t)', ...
        'Color', smoke, 'FontName', fontName, 'FontSize', 7.0, ...
        'FontWeight', 'bold', 'HorizontalAlignment', 'left');
    text(ax, missile(1) + 0.10, missile(2) - 0.15, 'M = P*', ...
        'Color', accent, 'FontName', fontName, 'FontSize', 7.0, ...
        'HorizontalAlignment', 'left');
    text(ax, target(1), target(2) - 0.15, 'T', ...
        'Color', targetColor, 'FontName', fontName, 'FontSize', 7.0, ...
        'HorizontalAlignment', 'center');
    text(ax, center(1) + 0.10, center(2) / 2, ...
        sprintf('d = %.3f m', state.distance), ...
        'Color', accent, 'FontName', fontName, 'FontSize', 7.0, ...
        'FontWeight', 'bold', 'HorizontalAlignment', 'left');
    text(ax, 0.02, 0.98, '有限视线端点切换', 'Units', 'normalized', ...
        'Color', ink, 'FontName', fontName, 'FontSize', 7.8, ...
        'FontWeight', 'bold', 'VerticalAlignment', 'top');
    text(ax, -1.05, -0.72, ...
        sprintf('t = %.4f s   ·   λ₀ = 0', switchTime), ...
        'Color', ink, 'FontName', fontName, 'FontSize', 7.0, ...
        'VerticalAlignment', 'middle');
    text(ax, -1.05, -0.94, ...
        sprintf('P* = M   ·   d = %.3f m   ·   R = %.0f m', ...
        state.distance, smokeRadius), ...
        'Color', muted, 'FontName', fontName, 'FontSize', 7.0, ...
        'VerticalAlignment', 'middle');

    xlim(ax, [-1.15, 3.30]);
    ylim(ax, [-1.08, 1.65]);
    axis(ax, 'equal');
    axis(ax, 'off');
end

function styleAxes(ax, fontName, ink, gridColor, paper, useGrid)
    ax.FontName = fontName;
    ax.FontSize = 7.0;
    ax.LineWidth = 0.65;
    ax.XColor = ink;
    ax.YColor = ink;
    ax.Color = paper;
    ax.Box = 'off';
    ax.TickDir = 'out';
    ax.TickLength = [0.015, 0.015];
    ax.Layer = 'top';
    if useGrid
        ax.XGrid = 'on';
        ax.YGrid = 'on';
        ax.GridColor = gridColor;
        ax.GridAlpha = 0.65;
        ax.MinorGridAlpha = 0;
    end
end

function panelLabel(ax, label, fontName, ink, location)
    text(ax, location(1), location(2), lower(label), ...
        'Units', 'normalized', 'Color', ink, 'FontName', fontName, ...
        'FontSize', 9.2, 'FontWeight', 'bold', ...
        'HorizontalAlignment', 'left', 'VerticalAlignment', 'top');
end

function color = tintColor(base, paper, strength)
    color = (1 - strength) .* paper + strength .* base;
end

function rgb = hexColor(code)
    code = char(erase(string(code), '#'));
    rgb = [hex2dec(code(1:2)), hex2dec(code(3:4)), hex2dec(code(5:6))] / 255;
end
