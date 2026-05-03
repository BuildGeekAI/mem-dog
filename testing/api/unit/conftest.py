"""Pytest conftest for webhook agent unit tests.

Ensures requests and google.adk stubs are installed before any test file
imports webhook_agent (so tests can run without full ADK/requests deps).
"""
import sys
import types
from unittest.mock import MagicMock

# Apply same stubs as test_agent_routing.py so any unit test file can import webhook_agent
if "requests" not in sys.modules or not getattr(sys.modules["requests"], "Session", None):
    _req = types.ModuleType("requests")
    _req.adapters = types.ModuleType("requests.adapters")
    _req.adapters.HTTPAdapter = MagicMock()
    _req.get = MagicMock()
    _req.post = MagicMock()
    _req.delete = MagicMock()
    _req.RequestException = type("RequestException", (Exception,), {})
    _mock_sess = MagicMock()
    _mock_sess.get = _req.get
    _mock_sess.post = _req.post
    _req.Session = MagicMock(return_value=_mock_sess)
    sys.modules["requests"] = _req
    sys.modules["requests.adapters"] = _req.adapters

if "google.adk.models.lite_llm" not in sys.modules:
    _google = sys.modules.get("google")
    if _google is None or not hasattr(getattr(_google, "adk", None), "models"):
        _g = types.ModuleType("google")
        _g.adk = types.ModuleType("google.adk")
        _g.adk.agents = types.ModuleType("google.adk.agents")
        _g.adk.agents.Agent = MagicMock()
        _g.adk.models = types.ModuleType("google.adk.models")
        _g.adk.models.lite_llm = types.ModuleType("google.adk.models.lite_llm")
        _g.adk.models.lite_llm.LiteLlm = MagicMock()
        sys.modules["google"] = _g
        sys.modules["google.adk"] = _g.adk
        sys.modules["google.adk.agents"] = _g.adk.agents
        sys.modules["google.adk.models"] = _g.adk.models
        sys.modules["google.adk.models.lite_llm"] = _g.adk.models.lite_llm
