from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.api.deps import require_roles
from app.database import get_session
from app.models.domain import AuditLog, DriverProfile, Restaurant, Shelter, User, UserRole, VerificationStatus
from app.schemas.common import VerificationRequest

router = APIRouter(prefix='/admin', tags=['admin'])


@router.post('/verifications')
def verify_entity(payload: VerificationRequest, admin: User = Depends(require_roles(UserRole.admin)), session: Session = Depends(get_session)):
    status = VerificationStatus.verified if payload.approved else VerificationStatus.rejected
    if payload.entity_type == 'restaurant':
        entity = session.get(Restaurant, payload.entity_id)
    elif payload.entity_type == 'shelter':
        entity = session.get(Shelter, payload.entity_id)
    else:
        entity = session.get(DriverProfile, payload.entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail='entity not found')
    entity.verification_status = status
    session.add(entity)
    session.add(AuditLog(actor_user_id=admin.id, action='verification.changed', entity_type=payload.entity_type, entity_id=payload.entity_id, details=payload.reason or ''))
    session.commit()
    return {'entity_type': payload.entity_type, 'entity_id': payload.entity_id, 'status': status}
