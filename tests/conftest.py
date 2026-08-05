from __future__ import annotations

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="ai_voice_tests_")
os.environ["AI_VOICE_DATA_DIR"] = _TMP
