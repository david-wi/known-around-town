from __future__ import annotations

import json
from typing import Any
from bson import ObjectId
from fastapi.responses import JSONResponse


class _MongoJSONEncoder(json.JSONEncoder):
    """WHY: some MongoDB collections still have BSON ObjectId values in _id
    and foreign-key fields (pre-UUID-migration documents).  FastAPI's default
    Pydantic serialization can't handle ObjectId, causing 500s on any endpoint
    that returns raw cursor results."""

    def default(self, o: Any) -> Any:
        if isinstance(o, ObjectId):
            return str(o)
        return super().default(o)


class MongoSafeJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
            cls=_MongoJSONEncoder,
        ).encode("utf-8")
