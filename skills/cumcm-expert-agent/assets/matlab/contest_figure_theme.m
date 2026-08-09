function T = contest_figure_theme()
%CONTEST_FIGURE_THEME Paper-first semantic theme with a hard colour budget.
% Use neutrals, one primary hue and at most one chosen accent hue.  Visual
% hierarchy comes from position, value, line style, markers and labels.

T.paper = hexrgb('#FAFAF7');
T.ink = hexrgb('#1E2A32');
T.muted = hexrgb('#647078');
T.grid = hexrgb('#D6DEE1');
T.panel = T.paper;
T.referenceBand = tint(T.muted, T.paper, 0.90);

T.primary = hexrgb('#2F6079');
T.accentWarm = hexrgb('#B5782F');
T.accentRisk = hexrgb('#8B4E5A');

% Compatibility aliases expose semantic colours, not an entity palette.
T.blue = T.primary;
T.amber = T.accentWarm;
T.coral = T.accentRisk;

T.colorBudget.neutralColors = [T.paper; T.ink; T.muted; T.grid; T.referenceBand];
T.colorBudget.primaryHue = T.primary;
T.colorBudget.accentChoices = [T.accentWarm; T.accentRisk];
T.colorBudget.maxChromaticHuesPerFigure = 2;
T.colorBudget.maxChromaticHuesPerPanel = 2;
T.colorBudget.maxChromaticHuesWithWaiver = 5;
T.colorBudget.maxAccentHues = 1;
T.colorBudget.thirdHueRequiresWaiver = true;
T.colorBudget.readyMadeEntityPalette = false;
T.assertColorBudget = @(chromaticHueCount, accentHueCount, hasWaiver) ...
    assertColorBudget(chromaticHueCount, accentHueCount, hasWaiver, ...
    T.colorBudget.maxChromaticHuesPerFigure, ...
    T.colorBudget.maxChromaticHuesWithWaiver, ...
    T.colorBudget.maxAccentHues);

T.grayscaleGate.required = true;
T.grayscaleGate.requireFinalPdfReview = true;
T.grayscaleGate.requireRedundantEncoding = true;
T.assertGrayscaleEncoding = @(lineStyles, markers, directLabels) ...
    assertGrayscaleEncoding(lineStyles, markers, directLabels);

% Entity identity is deliberately neutral.  Do not assign a pastel colour
% to each drone, missile, random seed or algorithm merely for variety.
T.entityNeutral = repmat(T.muted, 7, 1);
T.entityLineStyle = {'-', '--', '-.', ':', '-', '--', '-.'};
T.entityMarker = {'o', 's', '^', 'd', 'v', '>', '<'};

T.drone = T.entityNeutral(1:5, :);
T.droneLineStyle = T.entityLineStyle(1:5);
T.droneMarker = T.entityMarker(1:5);
T.missile = T.entityNeutral(1:3, :);
T.missileLineStyle = T.entityLineStyle(1:3);
T.missileMarker = T.entityMarker(1:3);
T.series = [T.primary; T.muted];
T.criterion = [T.primary; T.accentRisk];

% Stable event mappings use at most two chromatic hues in one figure.
T.event.release.color = T.ink;
T.event.release.marker = 'd';
T.event.detonation.color = T.accentWarm;
T.event.detonation.marker = 'o';
T.event.entry.color = T.primary;
T.event.entry.marker = '^';
T.event.exit.color = T.primary;
T.event.exit.marker = 'v';

T.primaryLight = tint(T.primary, T.paper, 0.82);
T.accentWarmLight = tint(T.accentWarm, T.paper, 0.84);
T.accentRiskLight = tint(T.accentRisk, T.paper, 0.84);
T.blueLight = T.primaryLight;
T.amberLight = T.accentWarmLight;
T.coralLight = T.accentRiskLight;

% Single-hue ordered map for response surfaces; never substitute jet.
T.sequential = anchoredMap([ ...
    hexrgb('#F4F5F1'); ...
    hexrgb('#DCE4E5'); ...
    hexrgb('#AEBFC5'); ...
    hexrgb('#607F8E'); ...
    hexrgb('#294E63')], 256);

% Use only when direction around a meaningful zero is itself the claim.
T.diverging = anchoredMap([T.primary; T.paper; T.accentRisk], 257);
T.font = chooseChineseFont();
end


function mixed = tint(color, paper, paperFraction)
mixed = (1 - paperFraction) .* color + paperFraction .* paper;
end


function map = anchoredMap(anchors, count)
position = linspace(0, 1, size(anchors, 1));
query = linspace(0, 1, count);
map = interp1(position, anchors, query, 'pchip');
map = min(1, max(0, map));
end


function rgb = hexrgb(code)
code = char(erase(string(code), '#'));
rgb = [hex2dec(code(1:2)), hex2dec(code(3:4)), hex2dec(code(5:6))] / 255;
end


function passed = assertColorBudget(chromaticHueCount, accentHueCount, ...
        hasWaiver, defaultLimit, waiverLimit, accentLimit)
validateattributes(chromaticHueCount, {'numeric'}, ...
    {'scalar', 'integer', 'nonnegative'});
validateattributes(accentHueCount, {'numeric'}, ...
    {'scalar', 'integer', 'nonnegative'});
assert(islogical(hasWaiver) && isscalar(hasWaiver), ...
    'contest_figure_theme:InvalidWaiverFlag', ...
    'hasWaiver must be one logical scalar.');
if hasWaiver
    hueLimit = waiverLimit;
else
    hueLimit = defaultLimit;
end
assert(chromaticHueCount <= hueLimit, ...
    'contest_figure_theme:ColorBudgetExceeded', ...
    'The figure exceeds its declared chromatic-hue budget.');
assert(accentHueCount <= accentLimit, ...
    'contest_figure_theme:AccentBudgetExceeded', ...
    'Use at most one accent hue in a figure.');
passed = true;
end


function passed = assertGrayscaleEncoding(lineStyles, markers, directLabels)
lineStyles = cellstr(string(lineStyles));
markers = cellstr(string(markers));
directLabels = logical(directLabels(:));
seriesCount = numel(lineStyles);
assert(numel(markers) == seriesCount && numel(directLabels) == seriesCount, ...
    'contest_figure_theme:InvalidGrayscaleEncoding', ...
    'lineStyles, markers and directLabels must describe the same series.');
for firstIndex = 1:seriesCount
    for secondIndex = firstIndex + 1:seriesCount
        hasDifferentLine = ~strcmp(lineStyles{firstIndex}, ...
            lineStyles{secondIndex});
        hasDifferentMarker = ~strcmp(markers{firstIndex}, ...
            markers{secondIndex});
        bothDirectlyLabelled = directLabels(firstIndex) && ...
            directLabels(secondIndex);
        assert(hasDifferentLine || hasDifferentMarker || bothDirectlyLabelled, ...
            'contest_figure_theme:GrayscaleCollision', ...
            ['Two series rely on colour alone. Give them different line ', ...
             'styles/markers or directly label both series.']);
    end
end
passed = true;
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
