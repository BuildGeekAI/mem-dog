"""Sub-agents package.

Instantiates all typed sub-agents as module-level singletons and
exposes two lookup structures:

* ``AGENT_REGISTRY`` — ``{agent_type: agent_instance}`` for direct lookup
  by the explicit-field and LLM routing layers.
* ``MIME_REGISTRY`` — a :class:`~registry.MimeRegistry` instance for
  MIME-type prefix/exact matching.

Adding a new agent
------------------
1. Create a file in the appropriate category sub-package.
2. Define a class that extends :class:`~base.BaseSubAgent`.
3. Import and instantiate it below, then add it to ``_ALL_AGENTS``.
"""

from .binary.archive import ArchiveAgent
from .binary.binary_blob import BinaryBlobAgent
from .binary.medical_imaging import MedicalImagingAgent
from .binary.time_series import TimeSeriesAgent
from .code_logs.code import CodeAgent
from .code_logs.log_file import LogFileAgent
from .code_logs.log_stream import LogStreamAgent
from .communication.calendar_agent import CalendarAgent
from .communication.channel_message import ChannelMessageAgent  # Plan 2
from .communication.chat import ChatAgent
from .communication.email_agent import EmailAgent
from .communication.feed import FeedAgent
from .communication.web_page import WebPageAgent
from .conferencing.conferencing_agent import ConferencingAgent  # Plan 3
from .documents.html_doc import HtmlDocAgent
from .documents.markdown import MarkdownAgent
from .documents.office_doc import OfficeDocAgent
from .documents.pdf import PdfAgent
from .financial.financial_agent import FinancialAgent            # Plan 3
from .industrial.industrial_agent import IndustrialAgent         # Plan 3
from .infrastructure.infrastructure_agent import InfrastructureAgent  # Plan 3
from .media.audio_stream import AudioStreamAgent
from .media.audio_url import AudioUrlAgent
from .media.image import ImageAgent
from .media.image_batch import ImageBatchAgent
from .media.video_stream import VideoStreamAgent
from .media.video_url import VideoUrlAgent
from .registry import MimeRegistry
from .satellite.satellite_agent import SatelliteAgent            # Plan 3
from .scientific.scientific_agent import ScientificAgent         # Plan 3
from .sensor.biometric import BiometricAgent
from .sensor.gps import GpsAgent
from .sensor.iot_sensor import IotSensorAgent                    # Plan 3
from .sensor.sensor import SensorAgent
from .spatial.geospatial import GeospatialAgent
from .spatial.lidar import LidarAgent
from .spatial.model_3d import Model3dAgent
from .structured.csv_agent import CsvAgent
from .structured.json_agent import JsonAgent
from .structured.xml_agent import XmlAgent
from .structured.yaml_agent import YamlAgent
from .download.url_download import UrlDownloadAgent
from .vehicle.vehicle_telemetry import VehicleTelemetryAgent     # Plan 3

# ---------------------------------------------------------------------------
# Module-level singletons — one instance per agent type
# ---------------------------------------------------------------------------

_ALL_AGENTS = [
    # Media
    VideoStreamAgent(),
    VideoUrlAgent(),
    AudioStreamAgent(),
    AudioUrlAgent(),
    ImageAgent(),
    ImageBatchAgent(),
    # Documents
    PdfAgent(),
    OfficeDocAgent(),
    MarkdownAgent(),
    HtmlDocAgent(),
    # Structured data
    JsonAgent(),
    XmlAgent(),
    CsvAgent(),
    YamlAgent(),
    # Code & logs
    CodeAgent(),
    LogStreamAgent(),
    LogFileAgent(),
    # Sensor / IoT
    SensorAgent(),
    GpsAgent(),
    BiometricAgent(),
    IotSensorAgent(),       # Plan 3 — generic IoT telemetry
    # Spatial / 3D
    LidarAgent(),
    GeospatialAgent(),
    Model3dAgent(),
    # Communication & web
    EmailAgent(),
    ChatAgent(),
    CalendarAgent(),
    WebPageAgent(),
    FeedAgent(),
    ChannelMessageAgent(),  # Plan 2 — normalised channel messages
    # Plan 3 — extended source types
    ConferencingAgent(),
    VehicleTelemetryAgent(),
    SatelliteAgent(),
    ScientificAgent(),
    FinancialAgent(),
    IndustrialAgent(),
    InfrastructureAgent(),
    # Binary / scientific
    ArchiveAgent(),
    TimeSeriesAgent(),
    MedicalImagingAgent(),
    # Download — URL crawl + fetch
    UrlDownloadAgent(),
    BinaryBlobAgent(),      # catch-all — must be last
]

# ---------------------------------------------------------------------------
# AGENT_REGISTRY: agent_type string → agent instance
# ---------------------------------------------------------------------------

AGENT_REGISTRY: dict = {agent.AGENT_TYPE: agent for agent in _ALL_AGENTS}

# ---------------------------------------------------------------------------
# MIME_REGISTRY: MIME type → agent instance (best-match)
# ---------------------------------------------------------------------------

MIME_REGISTRY: MimeRegistry = MimeRegistry()
for _agent in _ALL_AGENTS:
    MIME_REGISTRY.register(_agent)

# Convenience fallback reference
FALLBACK_AGENT: BinaryBlobAgent = AGENT_REGISTRY["binary_blob"]

__all__ = ["AGENT_REGISTRY", "MIME_REGISTRY", "FALLBACK_AGENT", "_ALL_AGENTS"]
