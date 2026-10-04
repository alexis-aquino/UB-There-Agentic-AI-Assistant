from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.sources import SourceNotFoundError, render

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.get("/image")
def source_image(
    file: str = Query(min_length=1, max_length=200),
    page: int = Query(ge=1, le=10000),
    quote: str = Query(default="", max_length=1500),
    crop: bool = True,
) -> Response:
    """A picture of the handbook page an answer came from, with the passage highlighted."""
    try:
        png = render(file, page, quote, crop)
    except SourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "max-age=86400"})
