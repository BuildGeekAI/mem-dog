"""Normalised prompt builder for all sub-agent LLM analysis.

Every content type (PDF, image, video, JSON, code, …) produces the same
structured JSON output with identical fields and the same depth of analysis.
Audio/video types get two additional fields: ``transcript`` and ``scenes``.

``build_prompt(agent_type)`` is the single public entry point.
"""

# ---------------------------------------------------------------------------
# Content-type intro lines — tells the LLM what it's looking at
# ---------------------------------------------------------------------------

_INTRO: dict[str, str] = {
    "json":             "Analyse this JSON content thoroughly",
    "xml":              "Analyse this XML document thoroughly",
    "csv":              "Analyse this CSV data thoroughly",
    "yaml":             "Analyse this YAML content thoroughly",
    "markdown":         "Read and analyse this Markdown document thoroughly",
    "html_doc":         "Extract the main content from this HTML and analyse it thoroughly",
    "code":             "Read and analyse this source code thoroughly",
    "log_file":         "Read and analyse this log file thoroughly",
    "log_stream":       "Read and analyse this streaming log data thoroughly",
    "web_page":         "Read and analyse this web page content thoroughly",
    "feed":             "Read and analyse this RSS/Atom feed thoroughly",
    "email":            "Read and analyse this email thoroughly",
    "chat":             "Read and analyse this chat transcript thoroughly",
    "calendar":         "Read and analyse these calendar events thoroughly",
    "channel_message":  "Read and analyse this channel message thoroughly",
    "sensor":           "Analyse this sensor telemetry thoroughly",
    "iot_sensor":       "Analyse this IoT sensor telemetry thoroughly",
    "gps":              "Analyse this GPS/location data thoroughly",
    "biometric":        "Analyse this biometric data thoroughly",
    "time_series":      "Analyse this time series data thoroughly",
    "geospatial":       "Analyse this geospatial data thoroughly",
    "lidar":            "Analyse this LiDAR point cloud data thoroughly",
    "model_3d":         "Analyse this 3D model data thoroughly",
    "archive":          "Analyse the contents of this archive thoroughly",
    "pdf":              "Read and analyse this PDF document thoroughly",
    "office_doc":       "Read and analyse this Office document thoroughly",
    "image":            "Look at this image carefully and analyse it thoroughly",
    "image_batch":      "Look at these images carefully and analyse them thoroughly",
    "medical_imaging":  "Analyse this medical imaging data thoroughly",
    "video_url":        "Watch this video carefully and analyse it thoroughly",
    "video_stream":     "Watch this video carefully and analyse it thoroughly",
    "audio_url":        "Listen to this audio carefully and analyse it thoroughly",
    "audio_stream":     "Listen to this audio carefully and analyse it thoroughly",
    "binary_blob":      "Analyse this binary data thoroughly",
    "conferencing":     "Analyse this conferencing/meeting data thoroughly",
    "vehicle_telemetry": "Analyse this vehicle telemetry data thoroughly",
    "satellite":        "Analyse this satellite data thoroughly",
    "scientific":       "Analyse this scientific data thoroughly",
    "financial":        "Analyse this financial data thoroughly",
    "industrial":       "Analyse this industrial data thoroughly",
    "infrastructure":   "Analyse this infrastructure data thoroughly",
    "url_download":     "Read and analyse this downloaded content thoroughly",
}

# Agent types that should include transcript and scenes fields
_AV_TYPES = frozenset({
    "video_url", "video_stream", "audio_url", "audio_stream",
})

_TRUNCATION_NOTE = (
    "\nNote: You are seeing a truncated excerpt. "
    "Analyse only what is visible."
)

# ---------------------------------------------------------------------------
# The single normalised JSON schema — same for ALL content types
# ---------------------------------------------------------------------------

_BASE_FIELDS = """\
  "category": "string — One domain label (e.g. \\"User Analytics\\", \\"DevOps / Config\\", \\"Financial Transaction\\")",
  "entities": ["array of strings — All named entities: people, organisations, products, IDs, URLs, locations, dates"],
  "typed_entities": [{"name": "string — entity name", "type": "string — one of: person, organization, product, location, date, url, concept, event", "confidence": 0.9}],
  "relationships": [{"source": "string — source entity name", "target": "string — target entity name", "type": "string — relationship type e.g. works_at, located_in, part_of, created_by, mentions"}],
  "keywords": ["array of strings — 5-15 topical keywords and technical terms that describe this content"],
  "summary": "string — Comprehensive 3-5 sentence summary. Describe WHAT the content is, what it contains, its structure, key details, findings, and purpose. Be specific and thorough — include numbers, names, and concrete details.",
  "queries": ["array of strings — 5-8 natural language questions a person might ask that this content would answer"]\
"""

_AV_EXTRA_FIELDS = """\
  "transcript": "string — Full verbatim transcript of all speech and narration",
  "scenes": ["array of strings — Chronological scene-by-scene descriptions of key visual/audio content"],\
"""


def build_prompt_from_config(config: dict, agent_type: str, is_truncated: bool = False) -> str:
    """Build a prompt from a DB-stored agent config, falling back to hardcoded parts.

    For any field that is ``None`` in *config*, the corresponding hardcoded
    default from this module is used instead.
    """
    intro = config.get("intro") or _INTRO.get(agent_type, "Analyse this content thoroughly")
    output_schema = config.get("output_schema")
    is_av = agent_type in _AV_TYPES

    if output_schema:
        fields = output_schema
    elif is_av:
        fields = f"{{\n{_BASE_FIELDS},\n{_AV_EXTRA_FIELDS}\n}}"
    else:
        fields = f"{{\n{_BASE_FIELDS}\n}}"

    prompt = (
        f"{intro} and return a JSON object with EXACTLY these fields:\n\n"
        f"{fields}\n\n"
        "Read/examine ALL of the content. Extract every detail you can find. "
        "Be thorough and specific in your summary — include concrete details, "
        "numbers, names, and key findings. Do not give a vague or high-level overview.\n\n"
        "IMPORTANT: Return ONLY valid JSON. No markdown, no code fences, "
        "no text before or after the JSON object."
    )

    if is_truncated:
        prompt += _TRUNCATION_NOTE

    return prompt


def build_prompt(agent_type: str, *, is_truncated: bool = False) -> str:
    """Build a normalised analysis prompt for *agent_type*.

    All content types produce the same JSON fields at the same depth.
    Audio/video types additionally get ``transcript`` and ``scenes``.
    """
    intro = _INTRO.get(agent_type, "Analyse this content thoroughly")
    is_av = agent_type in _AV_TYPES

    if is_av:
        fields = f"{{\n{_BASE_FIELDS},\n{_AV_EXTRA_FIELDS}\n}}"
    else:
        fields = f"{{\n{_BASE_FIELDS}\n}}"

    prompt = (
        f"{intro} and return a JSON object with EXACTLY these fields:\n\n"
        f"{fields}\n\n"
        "Read/examine ALL of the content. Extract every detail you can find. "
        "Be thorough and specific in your summary — include concrete details, "
        "numbers, names, and key findings. Do not give a vague or high-level overview.\n\n"
        "IMPORTANT: Return ONLY valid JSON. No markdown, no code fences, "
        "no text before or after the JSON object."
    )

    if is_truncated:
        prompt += _TRUNCATION_NOTE

    return prompt
