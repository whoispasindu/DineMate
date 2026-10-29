from fastapi import APIRouter

from app import schemas
from app.core.deps import NowDep, SessionDep
from app.safety.service import public_status
from app.services.views import canteen_summary, featured_shops, load_bundles, nearest_walks, pick_best

router = APIRouter(tags=["student"])


@router.get("/student/summary", response_model=schemas.StudentSummary)
def get_student_summary(session: SessionDep, now: NowDep) -> schemas.StudentSummary:
    bundles = load_bundles(session, now)
    walks = nearest_walks(session)
    active, events = public_status(session)
    return schemas.StudentSummary(
        server_time=now,
        best=pick_best(bundles),
        canteens=[canteen_summary(b, walks) for b in bundles],
        shops_now=featured_shops(bundles),
        busy_today=None,
        safety=schemas.SafetyStatus(active=active, events=events),
    )
