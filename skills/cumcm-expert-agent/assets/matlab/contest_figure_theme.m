function T = contest_figure_theme()
%CONTEST_FIGURE_THEME Restrained semantic theme for contest-paper figures.
% Visual hierarchy comes from whitespace, value, line style and markers;
% colour is a sparse redundant cue, never the primary differentiator.

T.paper = hexrgb('#FFFFFF');
T.ink = hexrgb('#25313A');
T.muted = hexrgb('#66737C');
T.grid = hexrgb('#DCE2E5');
T.panel = hexrgb('#F3F5F5');

T.blue = hexrgb('#3E6F8F');
T.sky = hexrgb('#7895A3');
T.teal = hexrgb('#5F8375');
T.amber = hexrgb('#C1844F');
T.coral = hexrgb('#9B5B64');
T.plum = hexrgb('#756D78');
T.violet = hexrgb('#586672');

% Entity identity relies on line/marker redundancy instead of a rainbow.
T.drone = [T.blue; T.sky; T.teal; T.muted; T.blue];
T.droneLineStyle = {'-', '--', '-.', ':', '-'};
T.droneMarker = {'o', 's', '^', 'd', 'v'};
T.missile = [T.ink; T.blue; T.teal];
T.missileLineStyle = {'-', '--', '-.'};
T.missileMarker = {'o', 's', '^'};
T.criterion = [T.blue; T.coral];
T.series = T.drone;

% Stable event mappings, with marker-shape redundancy for grayscale output.
T.event.release.color = T.ink;
T.event.release.marker = 'd';
T.event.detonation.color = T.amber;
T.event.detonation.marker = 'o';
T.event.entry.color = T.teal;
T.event.entry.marker = '^';
T.event.exit.color = T.blue;
T.event.exit.marker = 'v';

T.blueLight = tint(T.blue, T.paper, 0.78);
T.skyLight = tint(T.sky, T.paper, 0.78);
T.tealLight = tint(T.teal, T.paper, 0.82);
T.amberLight = tint(T.amber, T.paper, 0.80);
T.coralLight = tint(T.coral, T.paper, 0.82);
T.plumLight = tint(T.plum, T.paper, 0.84);
T.violetLight = tint(T.violet, T.paper, 0.84);

% Low-chroma ordered map for response surfaces; never substitute jet.
T.sequential = anchoredMap([ ...
    hexrgb('#F2F4F3'); ...
    hexrgb('#C8D7D8'); ...
    hexrgb('#86A7AD'); ...
    hexrgb('#3E6F8F')], 256);
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
