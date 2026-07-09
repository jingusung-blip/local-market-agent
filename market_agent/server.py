from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from market_agent.agent import LocalMarketAgent
from market_agent.collectors.molit import MolitClient
from market_agent.collectors.molit_rent import RentClient
from market_agent.config import Settings
from market_agent.models import AnalysisRequest
from market_agent.screener import screen_districts


app = FastAPI(title="주변 상권/정책 영향 분석 에이전트")
app.mount("/static", StaticFiles(directory="market_agent/static"), name="static")
templates = Jinja2Templates(directory="market_agent/templates")

# 스크리닝은 25개 구 x 여러 달을 조회해야 해서 매 요청마다 다시 돌리면
# 느리고 data.go.kr 호출량도 커진다. 하루 단위로 프로세스 내 캐싱한다
# (ECOS 기준금리 캐싱과 같은 방식).
_screen_cache: dict[str, Any] = {}


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


@app.get("/screen", response_class=HTMLResponse)
def screen(request: Request, refresh: bool = False) -> HTMLResponse:
    settings = Settings.from_env()
    if not settings.molit_enabled:
        return templates.TemplateResponse(
            request,
            "screen.html",
            context={
                "request": request,
                "results": None,
                "generated_at": None,
                "error": (
                    "MOLIT_API_KEY가 설정되어 있지 않아 지역 스크리닝을 실행할 수 없습니다. "
                    ".env 또는 Render 환경변수에 키를 등록하세요."
                ),
            },
        )

    today = date.today().isoformat()
    if not refresh and _screen_cache.get("date") == today:
        results = _screen_cache["results"]
    else:
        try:
            trade_client = MolitClient(settings.molit_api_key or "")
            rent_client = RentClient(settings.molit_api_key or "")
            results = screen_districts(trade_client, rent_client)
            _screen_cache["date"] = today
            _screen_cache["results"] = results
        except Exception as exc:
            return templates.TemplateResponse(
                request,
                "screen.html",
                context={"request": request, "results": None, "generated_at": None, "error": str(exc)},
                status_code=400,
            )

    return templates.TemplateResponse(
        request,
        "screen.html",
        context={"request": request, "results": results, "generated_at": today, "error": None},
    )
