# frozen_string_literal: true

Gem::Specification.new do |spec|
  spec.name          = "memdog"
  spec.version       = "0.1.0"
  spec.authors       = ["mem-dog"]
  spec.summary       = "Ruby SDK for the mem-dog private AI system"
  spec.description   = "High-level client for the mem-dog data ingestion and AI enrichment API. " \
                        "Provides seven methods -- add, search, get, delete, entities, related, compress -- " \
                        "that orchestrate the REST endpoints for data, memories, graph, and AI features."
  spec.homepage      = "https://github.com/mem-dog/mem-dog"
  spec.license       = "MIT"

  spec.required_ruby_version = ">= 3.1"

  spec.files         = Dir["lib/**/*.rb"]
  spec.require_paths = ["lib"]

  spec.add_dependency "faraday",            "~> 2.0"
  spec.add_dependency "faraday-multipart",  "~> 1.0"
end
