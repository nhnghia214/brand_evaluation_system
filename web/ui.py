# web/ui.py

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from agent.agent_service import BrandEvaluationAgent

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "question": "",
            "answer": None
        }
    )


@router.post("/ask", response_class=HTMLResponse)
def ask(
    request: Request,
    question: str = Form(...)
):
    answer = BrandEvaluationAgent.handle(question)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "question": question,
            "answer": answer
        }
    )
