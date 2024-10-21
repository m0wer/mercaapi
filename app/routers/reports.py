from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.worker import process_wrong_match_report, process_wrong_nutrition_report
from loguru import logger

router = APIRouter(prefix="/reports", tags=["reports"])


class WrongMatchReportRequest(BaseModel):
    original_name: str
    original_price: float
    wrong_match_id: str


class WrongNutritionReportRequest(BaseModel):
    product_id: str
    nutrition_id: int


@router.post("/wrong-match")
async def report_wrong_match(report: WrongMatchReportRequest):
    try:
        process_wrong_match_report.delay(
            original_name=report.original_name,
            original_price=report.original_price,
            wrong_match_id=report.wrong_match_id,
        )
        return {"status": "Report submitted successfully"}
    except Exception as e:
        logger.error(f"Error submitting wrong match report: {str(e)}")
        raise HTTPException(status_code=500, detail="Error submitting report")


@router.post("/wrong-nutrition")
async def report_wrong_nutrition(report: WrongNutritionReportRequest):
    try:
        process_wrong_nutrition_report.delay(
            product_id=report.product_id, nutrition_id=report.nutrition_id
        )
        return {"status": "Report submitted successfully"}
    except Exception as e:
        logger.error(f"Error submitting wrong nutrition report: {str(e)}")
        raise HTTPException(status_code=500, detail="Error submitting report")
