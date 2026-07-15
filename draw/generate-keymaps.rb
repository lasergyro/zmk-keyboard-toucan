#!/usr/bin/env ruby

require "set"
require "yaml"

raw_yaml_path = ARGV.fetch(0)
base_yaml_path = ARGV.fetch(1)
keymap_yaml_path = ARGV.fetch(2)
leader_config_path = ARGV.fetch(3)
draw_config_path = ARGV.fetch(4)
kd_draw_config_path = ARGV.fetch(5)

def deep_copy(value)
  Marshal.load(Marshal.dump(value))
end

def entry_text(entry)
  case entry
  when Hash
    entry["t"] || entry["tap"] || ""
  when nil
    ""
  else
    entry.to_s
  end
end

def trans?(entry)
  entry.is_a?(Hash) && entry["type"] == "trans"
end

def held?(entry)
  entry.is_a?(Hash) && entry["type"] == "held"
end

def normalize_entry(entry)
  case entry
  when Hash
    deep_copy(entry)
  else
    { "t" => entry.to_s }
  end
end

# Read all lines from a file, recursively following #include "..." directives
# relative to the file's directory.
def read_with_includes(path, visited = Set.new)
  return [] if visited.include?(path)
  visited.add(path)

  dir = File.dirname(path)
  File.readlines(path, chomp: true).flat_map do |line|
    if (m = line.match(/^\s*#include\s+"([^"]+)"/))
      read_with_includes(File.join(dir, m[1]), visited)
    else
      [line]
    end
  end
end

def load_simple_defines(path)
  read_with_includes(path).each_with_object({}) do |line, defines|
    match = line.match(/^\s*#define\s+([A-Z0-9_]+)\s+(\S+)\s*$/)
    next unless match

    defines[match[1]] = match[2]
  end
end

def load_leader_sequences(path, defines)
  read_with_includes(path).each_with_object([]) do |line, sequences|
    match = line.match(/ZMK_LEADER_SEQUENCE\(\s*([^,]+?)\s*,\s*([^,]+?)\s*,\s*([^)]+?)\s*\)\s*(?:(?:\/\/)\s*(.+))?$/)
    next unless match

    sequences << {
      "name" => match[1].strip,
      "binding" => match[2].strip,
      "sequence" => match[3].split(/\s+/).map { |token| defines.fetch(token.strip, token.strip) },
      "comment" => match[4]&.strip,
    }
  end
end

# Wrap `text` with a `{{class:NAME}}` prefix so utils.py's _draw_legend
# tags the rendered element with an extra CSS class (see kd_patches/utils.py).
def annotate(text, extra_class)
  extra_class ? "{{class:#{extra_class}}}#{text}" : text
end

# ── Load inputs ─────────────────────────────────────────────────────────────

raw_data = YAML.load_file(raw_yaml_path) || {}
draw_config = YAML.load_file(draw_config_path) || {}
toucan = draw_config.fetch("toucan", {})

layers = raw_data.fetch("layers", {})
combos = Array(raw_data["combos"]).map { |combo| deep_copy(combo) }
two_key_combos = combos.select { |combo| Array(combo["p"]).length == 2 && !combo["hidden"] }

# ── Combo Shifts ────────────────────────────────────────────────────────────
# Convert automatically parsed 's' (shifted) properties on combos to 'right'
# and tag them with combo-shift for pink, smaller rendering.
two_key_combos.each do |combo|
  next unless combo["k"].is_a?(Hash)
  if combo["k"]["s"]
    combo["k"]["right"] = annotate(combo["k"].delete("s"), "combo-shift")
  end
  # Drop auto-parsed hold labels on home-row-mod combos (e.g. the raw
  # "&mods_rsft_rgui" behavior): the combo layer doesn't need to show the
  # home-row mods, and the raw binding name just overflows the small cell.
  hold = combo["k"]["h"]
  combo["k"].delete("h") if hold.is_a?(String) && hold.start_with?("&")
end

# ── Toucan config ───────────────────────────────────────────────────────────

# annotation_layers: { "Nav" => { "field" => "tr", "color" => "#e9ab2e" }, ... }
annotation_layers = toucan.fetch("annotation_layers", {})

# leader_namespaces: single source of truth for each namespace's field, color,
# extra_class and combo_type.  See toucan.leader_namespaces in config.yaml.
leader_ns_config = toucan.fetch("leader_namespaces", {})

LEADER_ANNOTATIONS = leader_ns_config.each_with_object({}) do |(name, ns), h|
  h[name.to_sym] = { field: ns["field"], extra_class: ns["extra_class"] }
end

# ── Base YAML (all layers for the full-layout SVG) ──────────────────────────

base_layer = deep_copy(layers.fetch("Base"))

base_yaml_layers = {}
layers.each do |name, keys|
  base_yaml_layers[name] = deep_copy(keys)
end

base_yaml = {
  "layout" => deep_copy(raw_data["layout"]),
  "layers" => base_yaml_layers,
  "combos" => two_key_combos.map do |combo|
    combo = deep_copy(combo)
    combo["l"] = ["Combos"]
    combo
  end,
}

# ── Build overlay keymap ────────────────────────────────────────────────────

# Map: base key label → position index (single uppercase letter or ";")
base_key_positions = {}
base_layer.each_with_index do |entry, index|
  label = entry_text(entry)
  next unless label.match?(/\A[A-Z]\z/) || label == ";"
  base_key_positions[label] = index
end

overlay_layer = base_layer.each_with_index.map do |entry, index|
  overlay = normalize_entry(entry)
  base_text = entry_text(entry)

  # For each annotation layer: tag the activator key and place the overlay annotation.
  annotation_layers.each do |layer_name, layer_cfg|
    field = layer_cfg["field"]
    if base_text == layer_name
      overlay["t"] = "{{class:#{layer_name.downcase}-activator}}#{base_text}"
    end

    anno_layer = layers[layer_name]
    next unless anno_layer

    anno_entry = anno_layer[index]
    anno_text = entry_text(anno_entry)
    if !anno_text.empty? && !trans?(anno_entry) && !held?(anno_entry) && anno_text != base_text
      overlay[field] = anno_text
    end
  end

  overlay
end

# ── Leader sequence annotations ─────────────────────────────────────────────

defines = load_simple_defines(leader_config_path)
leader_sequences = load_leader_sequences(leader_config_path, defines)

# Resolve any define-name prefixes (e.g. TOUCAN_GREEK_LEADER_PREFIX → "L").
# Namespaces without a prefix key match single-key sequences.
resolved_prefixes = leader_ns_config.transform_values do |ns|
  raw = ns["prefix"]
  raw ? defines.fetch(raw, raw) : nil
end

leader_sequences.each do |seq|
  binding  = seq.fetch("binding")
  sequence = seq.fetch("sequence")
  comment  = seq["comment"]

  # Find the first namespace whose prefix matches this sequence.
  ns_name, _prefix = resolved_prefixes.find do |name, prefix|
    if prefix
      sequence.length == 2 && sequence.first == prefix
    else
      sequence.length == 1
    end
  end
  next unless ns_name

  ns_cfg = leader_ns_config[ns_name]
  label = if ns_cfg["fallback_to_binding"]
    comment || binding.split.last
  else
    comment
  end
  next unless label

  anno = LEADER_ANNOTATIONS[ns_name.to_sym]
  idx  = base_key_positions[sequence.last]
  next unless idx

  overlay_layer[idx][anno[:field]] = annotate(label, anno[:extra_class])
end


# ── Keymap YAML (overlay + ghost combo layer) ───────────────────────────────

combo_layer = Array.new(base_layer.length) { { "type" => "ghost" } }
keymap_yaml = {
  "layout" => deep_copy(raw_data["layout"]),
  "layers" => {
    "overlay" => overlay_layer,
    "combo"   => combo_layer,
  },
  "combos" => two_key_combos.map do |combo|
    combo = deep_copy(combo)
    combo["l"] = ["combo"]
    combo
  end,
}

# ── Generate CSS and write the KD draw config ───────────────────────────────

annotation_css_lines = annotation_layers.flat_map do |layer_name, layer_cfg|
  field = layer_cfg["field"]
  color = layer_cfg["color"]
  next [] unless field && color
  [
    "    text.#{field} { fill: #{color}; font-size: 10px; font-weight: 600; }",
    "    use.#{field}  { fill: #{color}; }",
    "    text.#{layer_name.downcase}-activator { fill: #{color}; }",
  ]
end

# Two-pass emission: field defaults first so that extra-class overrides
# (same CSS specificity) always win regardless of namespace order in the config.
leader_css_field_lines  = []
leader_css_override_lines = []

leader_ns_config.each do |_name, ns|
  color       = ns["color"]
  extra_class = ns["extra_class"]
  combo_type  = ns["combo_type"]
  field       = ns["field"]
  next unless color

  if extra_class
    leader_css_override_lines << "    text.#{extra_class}, use.#{extra_class} { fill: #{color}; }"
    leader_css_override_lines << "    .combo.#{combo_type} text, .combo.#{combo_type} use { fill: #{color}; }" if combo_type
  elsif field
    leader_css_field_lines << "    text.#{field} { fill: #{color}; font-size: 10px; font-weight: 600; }"
    leader_css_field_lines << "    use.#{field}  { fill: #{color}; }"
    leader_css_field_lines << "    .combo.#{combo_type} text, .combo.#{combo_type} use { fill: #{color}; }" if combo_type
  end
end

leader_css_lines = leader_css_field_lines + leader_css_override_lines

kd_draw_config = deep_copy(draw_config)
kd_draw_config.delete("toucan")
all_css_lines = annotation_css_lines + leader_css_lines
unless all_css_lines.empty?
  kd_draw_config["draw_config"] ||= {}
  existing = (kd_draw_config["draw_config"]["svg_extra_style"] || "").rstrip
  kd_draw_config["draw_config"]["svg_extra_style"] = "#{existing}\n#{all_css_lines.join("\n")}\n"
end

File.write(base_yaml_path, YAML.dump(base_yaml))
File.write(keymap_yaml_path, YAML.dump(keymap_yaml))
File.write(kd_draw_config_path, YAML.dump(kd_draw_config))
