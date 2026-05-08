from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.api.deps import require_roles
from app.database import get_session
from app.models.domain import RouteAssignment, RouteStatus, RouteStop, StopStatus, User, UserRole
from app.schemas.common import RouteAssignmentRead, RouteAssignmentUpdate, RouteStopComplete, RouteAssignmentCreate

router = APIRouter(prefix='/routes', tags=['routes'])


@router.get('/assignments', response_model=list[RouteAssignmentRead])
def list_assignments(user: User = Depends(require_roles(UserRole.driver, UserRole.admin)), session: Session = Depends(get_session)):
    statement = select(RouteAssignment).where(RouteAssignment.status != RouteStatus.deleted)
    if user.role != UserRole.admin:
        statement = statement.where(RouteAssignment.driver_id == user.id)
    return session.exec(statement).all()


@router.get('/assignments/{assignmentId}', response_model=RouteAssignmentRead)
def get_assignment(assignmentId: int, user: User = Depends(require_roles(UserRole.driver, UserRole.admin)), session: Session = Depends(get_session)):
    assignment = session.get(RouteAssignment, assignmentId)

    if not assignment or assignment.status == RouteStatus.deleted:
        raise HTTPException(status_code=404, detail='assignment not found')

    if user.role != UserRole.admin and assignment.driver_id != user.id:
        raise HTTPException(status_code=403, detail='not your route')

    stops = session.exec(
        select(RouteStop)
        .where(RouteStop.assignment_id == assignment.id)
        .order_by(RouteStop.sequence)
    ).all()
    return {
    "id": assignment.id,
    "driver_id": assignment.driver_id,
    "status": assignment.status,
    "stops": stops,
    }


@router.patch('/assignments/{assignmentId}', response_model=RouteAssignmentRead)
def update_assignment(assignmentId: int, payload: RouteAssignmentUpdate, user: User = Depends(require_roles(UserRole.driver, UserRole.admin)), session: Session = Depends(get_session)):
    assignment = session.get(RouteAssignment, assignmentId)
    if not assignment:
        raise HTTPException(status_code=404, detail='assignment not found')
    if user.role != UserRole.admin and assignment.driver_id != user.id:
        raise HTTPException(status_code=403, detail='not your route')
    if payload.status:
        assignment.status = payload.status
    session.add(assignment); session.commit(); session.refresh(assignment)
    return assignment


@router.delete('/assignments/{assignmentId}', status_code=204)
def delete_assignment(assignmentId: int, user: User = Depends(require_roles(UserRole.driver, UserRole.admin)), session: Session = Depends(get_session)):
    assignment = session.get(RouteAssignment, assignmentId)
    if not assignment:
        raise HTTPException(status_code=404, detail='assignment not found')
    if user.role != UserRole.admin and assignment.driver_id != user.id:
        raise HTTPException(status_code=403, detail='not your route')
    assignment.status = RouteStatus.deleted
    session.add(assignment); session.commit()
    return None


@router.post('/assignments/{assignmentId}/accept', response_model=RouteAssignmentRead)
def accept_assignment(assignmentId: int, user: User = Depends(require_roles(UserRole.driver, UserRole.admin)), session: Session = Depends(get_session)):
    assignment = session.get(RouteAssignment, assignmentId)
    if not assignment or assignment.status != RouteStatus.proposed:
        raise HTTPException(status_code=404, detail='proposed assignment not found')
    if user.role != UserRole.admin and assignment.driver_id != user.id:
        raise HTTPException(status_code=403, detail='not your route')
    assignment.status = RouteStatus.accepted
    session.add(assignment); session.commit(); session.refresh(assignment)
    return assignment


@router.post('/stops/{stopId}/complete')
def complete_stop(stopId: int, payload: RouteStopComplete, user: User = Depends(require_roles(UserRole.driver, UserRole.admin)), session: Session = Depends(get_session)):
    stop = session.get(RouteStop, stopId)
    if not stop:
        raise HTTPException(status_code=404, detail='stop not found')
    assignment = session.get(RouteAssignment, stop.assignment_id)
    if user.role != UserRole.admin and assignment.driver_id != user.id:
        raise HTTPException(status_code=403, detail='not your stop')
    stop.status = StopStatus.completed
    stop.completed_at = datetime.now(timezone.utc)
    session.add(stop); session.commit()
    return {'id': stop.id, 'status': stop.status, 'completed_at': stop.completed_at}

@router.post('/assignments', response_model=RouteAssignmentRead, status_code=201)
def create_assignment(
    payload: RouteAssignmentCreate,
    user: User = Depends(require_roles(UserRole.admin)),
    session: Session = Depends(get_session),
):
    driver = session.get(User, payload.driver_id)
    if not driver or driver.role != UserRole.driver:
        raise HTTPException(status_code=404, detail='driver not found')

    assignment = RouteAssignment(
        driver_id=payload.driver_id,
        status=RouteStatus.proposed,
    )

    session.add(assignment)
    session.commit()
    session.refresh(assignment)

    for stop_data in payload.stops:
        stop = RouteStop(
            assignment_id=assignment.id,
            batch_id=stop_data.batch_id,
            kind=stop_data.kind,
            sequence=stop_data.sequence,
            address=stop_data.address,
            lat=stop_data.lat,
            lng=stop_data.lng,
        )
        session.add(stop)

    session.commit()

    return assignment