require 'json'
require 'liquid'

# This trusted helper is shared by visible checks and the isolated evaluator.
# No Shopify-specific tags, filters, filesystem includes, or custom drops.
request = JSON.parse(STDIN.read)
begin
  template = Liquid::Template.parse(request.fetch('source'), error_mode: :strict)
  template.resource_limits.render_length_limit = 100_000
  template.resource_limits.render_score_limit = 50_000
  template.resource_limits.assign_score_limit = 50_000
  output = template.render!(request.fetch('variables'), strict_variables: true, strict_filters: true)
  puts JSON.generate({ok: true, output: output})
rescue Liquid::Error => e
  puts JSON.generate({ok: false, error: "#{e.class}: #{e.message}"})
end
