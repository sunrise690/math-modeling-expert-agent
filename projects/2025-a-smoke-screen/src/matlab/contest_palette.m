function C = contest_palette()
%CONTEST_PALETTE Load and validate the project's sole semantic colour spec.

specPath = fullfile(fileparts(mfilename('fullpath')), 'palette_spec.json');
assert(isfile(specPath), 'Palette specification is missing: %s', specPath);
spec = jsondecode(fileread(specPath));

C.paletteId = char(spec.palette_id);
C.paper = hexrgb(spec.roles.paper);
C.ink = hexrgb(spec.roles.ink);
C.muted = hexrgb(spec.roles.muted);
C.secondary = hexrgb(spec.roles.secondary);
C.grid = hexrgb(spec.roles.grid);
C.primary = hexrgb(spec.roles.primary);
C.clay = hexrgb(spec.roles.clay);
C.wine = hexrgb(spec.roles.risk);
C.warm = C.clay;
C.accent = C.clay;
C.guide = C.grid;

C.sequentialAnchors = zeros(numel(spec.sequential), 3);
for index = 1:numel(spec.sequential)
    C.sequentialAnchors(index, :) = hexrgb(spec.sequential{index});
end

C.constraints = spec.constraints;
assert(all(abs(C.paper - 1) < 1e-12), ...
    'Formal figures must use an exact white background.');

textColours = [C.ink; C.muted; C.secondary; C.primary; C.clay; C.wine];
for index = 1:size(textColours, 1)
    ratio = contrastRatio(textColours(index, :), C.paper);
    assert(ratio >= C.constraints.minimum_text_contrast_on_paper, ...
        'Palette text colour %d has insufficient contrast: %.3f.', index, ratio);
end
assert(contrastRatio(C.grid, C.paper) <= ...
    C.constraints.maximum_grid_contrast_on_paper, ...
    'Grid colour is too visually heavy for the paper background.');

orderedLuminance = relativeLuminance(C.sequentialAnchors);
assert(all(diff(orderedLuminance) < 0), ...
    'Sequential palette luminance must decrease strictly from low to high.');
end


function ratio = contrastRatio(first, second)
values = sort([relativeLuminance(first), relativeLuminance(second)], 'descend');
ratio = (values(1) + 0.05) / (values(2) + 0.05);
end


function value = relativeLuminance(rgb)
linear = rgb ./ 12.92;
mask = rgb > 0.04045;
linear(mask) = ((rgb(mask) + 0.055) ./ 1.055) .^ 2.4;
value = linear(:, 1) .* 0.2126 + linear(:, 2) .* 0.7152 + ...
    linear(:, 3) .* 0.0722;
end


function rgb = hexrgb(code)
code = char(erase(string(code), '#'));
rgb = [hex2dec(code(1:2)), hex2dec(code(3:4)), hex2dec(code(5:6))] / 255;
end
