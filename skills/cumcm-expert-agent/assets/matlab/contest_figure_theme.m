function T = contest_figure_theme()
%CONTEST_FIGURE_THEME Restrained semantic theme for contest-paper figures.
% Visual hierarchy comes from whitespace, value, line style and markers;
% colour is a sparse redundant cue, never the primary differentiator.

T.paper = hexrgb('#FAFAF7');
T.ink = hexrgb('#1E2A32');
T.muted = hexrgb('#647078');
T.grid = hexrgb('#D6DEE1');
T.panel = hexrgb('#F1F4F2');

T.blue = hexrgb('#2F6079');
T.sky = hexrgb('#7795A2');
T.teal = hexrgb('#3D7A70');
T.amber = hexrgb('#B5782F');
T.coral = hexrgb('#8B4E5A');
T.plum = hexrgb('#73677F');
T.violet = hexrgb('#665F82');

% Entity identity defaults to one neutral colour plus redundant line/marker
% coding.  This is safe when event/risk colours share the same panel.
T.entityNeutral = repmat(T.muted, 7, 1);
T.entityLineStyle = {'-', '--', '-.', ':', '-', '--', '-.'};
T.entityMarker = {'o', 's', '^', 'd', 'v', '>', '<'};

% A restrained 7-colour category palette is available only after an
% entity_color_waiver passes.  Never use it in a panel containing event,
% risk, criterion or threshold semantics.
T.entityCategorical = [ ...
    hexrgb('#4F6E7B'); ...
    hexrgb('#627B73'); ...
    hexrgb('#7A6F62'); ...
    hexrgb('#6E687B'); ...
    hexrgb('#7A626A'); ...
    hexrgb('#5E7186'); ...
    hexrgb('#77785D')];
T.entityColorWaiver.required = true;
T.entityColorWaiver.minCount = 4;
T.entityColorWaiver.maxCount = 7;
T.entityColorWaiver.requiresRedundantEncoding = true;
T.entityColorWaiver.disallowReservedSemanticCoexistence = true;

T.drone = T.entityNeutral(1:5, :);
T.droneLineStyle = T.entityLineStyle(1:5);
T.droneMarker = T.entityMarker(1:5);
T.missile = T.entityNeutral(1:3, :);
T.missileLineStyle = T.entityLineStyle(1:3);
T.missileMarker = T.entityMarker(1:3);
T.criterion = [T.blue; T.coral];
T.series = [T.blue; T.sky];

% Stable event mappings, with marker-shape redundancy for grayscale output.
T.event.release.color = T.ink;
T.event.release.marker = 'd';
T.event.detonation.color = T.amber;
T.event.detonation.marker = 'o';
T.event.entry.color = T.teal;
T.event.entry.marker = '^';
T.event.exit.color = T.blue;
T.event.exit.marker = 'v';

% Registry used by figure-level waiver/audit checks.  Category colours
% must not be repurposed as any of these semantic roles.
T.semanticReserved.names = { ...
    'release_or_threshold', 'detonation_or_optimum', 'event_entry', ...
    'exit_or_primary_criterion', 'risk_or_conservative_criterion'};
T.semanticReserved.colors = [ ...
    T.event.release.color; ...
    T.event.detonation.color; ...
    T.event.entry.color; ...
    T.event.exit.color; ...
    T.coral];
T.entityColorWaiver.paletteSource = 'T.entityCategorical';
T.entityColorWaiver.reservedSemanticNames = T.semanticReserved.names;
assertNoExactColorCollision(T.entityCategorical, T.semanticReserved.colors);

T.blueLight = tint(T.blue, T.paper, 0.78);
T.skyLight = tint(T.sky, T.paper, 0.78);
T.tealLight = tint(T.teal, T.paper, 0.82);
T.amberLight = tint(T.amber, T.paper, 0.80);
T.coralLight = tint(T.coral, T.paper, 0.82);
T.plumLight = tint(T.plum, T.paper, 0.84);
T.violetLight = tint(T.violet, T.paper, 0.84);

% Low-chroma ordered map for response surfaces; never substitute jet.
T.sequential = anchoredMap([ ...
    hexrgb('#F4F5F1'); ...
    hexrgb('#D8E2E1'); ...
    hexrgb('#B7CFCC'); ...
    hexrgb('#557F87'); ...
    hexrgb('#294E63')], 256);
T.diverging = anchoredMap([T.blue; T.paper; T.coral], 257);
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


function assertNoExactColorCollision(categoryColors, reservedColors)
for categoryIndex = 1:size(categoryColors, 1)
    channelDistance = max(abs(reservedColors - categoryColors(categoryIndex, :)), [], 2);
    assert(all(channelDistance > 1e-12), ...
        'contest_figure_theme:SemanticColorCollision', ...
        ['An entity category colour collides with a reserved semantic ', ...
         'colour. Update entityCategorical before rendering figures.']);
end
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
