"""Synthetic demo endpoints (Phase 6). Clearly labeled demo-only helpers that
operate solely on synthetic fixture data. DEMO_ENABLED=0 disables them."""

from fastapi import APIRouter, HTTPException

from app.agent import demo as demo_mod

router = APIRouter()


def _guard() -> None:
    if not demo_mod.demo_enabled():
        raise HTTPException(status_code=403, detail="Synthetic demo endpoints are disabled.")


@router.post("/demo/reset")
async def demo_reset():
    """Synthetic demo reset: clear demo workspaces, rebuild initial mismatch."""
    _guard()
    try:
        return demo_mod.reset_demo()
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Demo fixture missing: {e.filename}.")


@router.post("/demo/supplement")
async def demo_supplement(notice_id: str):
    """Upload supplemental demo evidence and replan for the demo notice."""
    _guard()
    try:
        return demo_mod.supplement_demo(notice_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Notice not found.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Demo fixture missing: {e.filename}.")


@router.get("/demo/describe")
async def demo_describe():
    _guard()
    return {
        "label": demo_mod.DEMO_LABEL,
        "noticeNumber": demo_mod.DEMO_NOTICE_NUMBERS[0],
        "stages": ["initial-mismatch", "reconciled"],
    }
