from __future__ import annotations

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from market_agent.agent import LocalMarketAgent
from market_agent.models import AnalysisRequest


app = FastAPI(title="주변 상권/정책 영향 분석 에이전트")
app.mount("/static", StaticFiles(directory="market_agent/static"), name="static")
templates = Jinja2Templates(directory="market_agent/templates")


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        context={
            "request": request,
            "report": None,
            "error": None,
            "form": {"address": "", "apartment_name": "", "radius_km": 3.0},
        },
    )


@app.post("/analyze", response_class=HTMLResponse)
def analyze(
    request: Request,
    address: str = Form(""),
    radius_km: float = Form(3.0),
    apartment_name: str = Form(""),
    offline: bool = Form(False),
) -> HTMLResponse:
    form = {
        "address": address,
        "apartment_name": apartment_name,
        "radius_km": radius_km,
        "offline": offline,
    }
    try:
        report = LocalMarketAgent().analyze(
            AnalysisRequest(
                address=address,
                radius_km=radius_km,
                apartment_name=apartment_name or None,
                offline=offline,
            )
        )
        return templates.TemplateResponse(
            request,
            "index.html",
            context={"request": request, "report": report, "error": None, "form": form},
        )
    except Exception as exc:
        return templates.TemplateResponse(
            request,
            "index.html",
            context={"request": request, "report": None, "error": str(exc), "form": form},
            status_code=400,
        )
