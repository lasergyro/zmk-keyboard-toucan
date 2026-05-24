#!/usr/bin/env ruby
# frozen_string_literal: true
#
# Crop a region of a keymap SVG by listing key labels to keep.
#
# Usage:
#   ruby crop-keymap.rb <input.svg> <output.svg> <keys> [--pad N] [--layer NAME]
#
#   <keys>        comma-separated list of single-character key labels or keypos
#                 indices (e.g. "A", "D,F", "A,S,D,F", "pos:36,pos:37").
#   --pad N       extra pixels of padding around the bounding box (default 12).
#   --layer NAME  restrict to a specific layer group (e.g. "Base", "Nav").
#                 Default: search all layers; the first layer that contains
#                 the requested labels is used.
#
# Reads the SVG, locates each requested key by either its rendered text
# (matching the `class="key tap"` label) or its `keypos-N` class, computes
# a bounding box from each matching `<g transform="translate(x,y)" ...>`
# element, then writes a new SVG with an adjusted viewBox.
#
# Intended for automated visual debugging — e.g. snapshot a single region
# around the A key, diff across runs, etc.

require "optparse"

PAD_DEFAULT = 12
KEY_HALF = 26  # keys are 52x52 centred at the translate(x, y)

def die(msg)
  warn "error: #{msg}"
  exit 1
end

opts = { pad: PAD_DEFAULT, layer: nil }
parser = OptionParser.new do |o|
  o.on("--pad N", Integer) { |v| opts[:pad] = v }
  o.on("--layer NAME", String) { |v| opts[:layer] = v }
end
parser.parse!(ARGV)

input_path, output_path, keys_arg = ARGV
die "usage: crop-keymap.rb <input.svg> <output.svg> <keys>" unless input_path && output_path && keys_arg

requests = keys_arg.split(",").map(&:strip).reject(&:empty?)
die "no keys given" if requests.empty?

svg = File.read(input_path)

# Optionally restrict search to one layer group: <g ... class="layer-NAME"> ... </g>
search_space = svg
if opts[:layer]
  layer_name = opts[:layer]
  m = svg.match(/<g[^>]*class="layer-#{Regexp.escape(layer_name)}"[^>]*>(.*?)<\/g>\s*(?=<g[^>]*class="layer-|<g[^>]*class="(?:combo|layer-header)|$)/m)
  die "layer not found: #{layer_name}" unless m
  search_space = m[1]
end

# Find <g transform="translate(X, Y)..." class="key ... keypos-N"> ... </g>
# along with any <text class="key tap">LABEL</text> child.
key_regex = /
  <g\s+transform="translate\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)[^"]*"
  [^>]*class="[^"]*keypos-(\d+)[^"]*"[^>]*>
  (.*?)
  <\/g>
/mx

keys = []
search_space.scan(key_regex).each do |x, y, pos, body|
  label = nil
  if (lm = body.match(/<text[^>]*class="key tap[^"]*">([^<]+)<\/text>/))
    label = lm[1].strip
  end
  keys << { x: x.to_f, y: y.to_f, pos: pos.to_i, label: label }
end
die "no keys parsed from SVG" if keys.empty?

matched = []
requests.each do |req|
  if req.start_with?("pos:")
    want = req.sub("pos:", "").to_i
    found = keys.select { |k| k[:pos] == want }
  else
    found = keys.select { |k| k[:label] == req }
  end
  die "no key matched '#{req}'" if found.empty?
  matched.concat(found)
end

xs = matched.map { |k| k[:x] }
ys = matched.map { |k| k[:y] }
min_x = xs.min - KEY_HALF - opts[:pad]
min_y = ys.min - KEY_HALF - opts[:pad]
max_x = xs.max + KEY_HALF + opts[:pad]
max_y = ys.max + KEY_HALF + opts[:pad]
width  = max_x - min_x
height = max_y - min_y

# Replace the root <svg ...> viewBox/width/height.
new_svg = svg.sub(/<svg\b[^>]*>/) do |tag|
  t = tag.dup
  t.sub!(/\sviewBox="[^"]*"/, "")
  t.sub!(/\swidth="[^"]*"/, "")
  t.sub!(/\sheight="[^"]*"/, "")
  t.sub!(/>\z/, %Q{ viewBox="#{min_x.round(2)} #{min_y.round(2)} #{width.round(2)} #{height.round(2)}" width="#{width.round(2)}" height="#{height.round(2)}">})
  t
end

File.write(output_path, new_svg)
labels = matched.map { |k| k[:label] || "pos:#{k[:pos]}" }.uniq.join(",")
warn "cropped to #{labels} → #{output_path} (#{width.round}x#{height.round})"
