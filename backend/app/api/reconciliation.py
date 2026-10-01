from fastapi import APIRouter, HTTPException

from app.services import lineage as lineage_service
from app.services import reconciliation as recon_service

router = APIRouter()


@router.get("/{run_id}")
async def get_run(run_id: str):
    try:
        return recon_service.get_reconciliation_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Reconciliation run not found.")


@router.get("/findings/{finding_id}/lineage")
async def get_finding_lineage(finding_id: str):
    try:
        return lineage_service.get_finding_lineage(finding_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Finding not found.")
