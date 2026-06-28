from __future__ import annotations

import json
from typing import Any
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder


class MongoSafeJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        # WHY: jsonable_encoder handles datetime, date, Decimal, and other custom types,
        # and respects the global ENCODERS_BY_TYPE patch we registered for ObjectId.
        # This prevents both ObjectId and datetime serialization crashes on MongoDB documents.
        return json.dumps(
            jsonable_encoder(content),
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        ).encode("utf-8")
