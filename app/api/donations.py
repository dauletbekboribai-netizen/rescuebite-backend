from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.api.deps import require_roles
from app.database import get_session
from app.models.domain import BatchState, ClaimStatus, DonationClaim, FoodBatch, Shelter, User, UserRole, VerificationStatus
from app.schemas.common import DonationClaimCreate, DonationClaimRead, DonationClaimUpdate

router = APIRouter(prefix='/donations', tags=['donations'])


def get_user_shelter(session: Session, user: User) -> Shelter | None:
    return session.exec(select(Shelter).where(Shelter.coordinator_id == user.id)).first()


@router.get('/claims', response_model=list[DonationClaimRead])
def list_claims(user: User = Depends(require_roles(UserRole.shelter_coordinator, UserRole.admin)), session: Session = Depends(get_session)):
    if user.role == UserRole.admin:
        return session.exec(select(DonationClaim).where(DonationClaim.status != ClaimStatus.deleted)).all()
    shelter = get_user_shelter(session, user)
    if not shelter:
        return []
    return session.exec(select(DonationClaim).where(DonationClaim.shelter_id == shelter.id, DonationClaim.status != ClaimStatus.deleted)).all()


@router.post('/claims', response_model=DonationClaimRead, status_code=201)
def create_claim(payload: DonationClaimCreate, user: User = Depends(require_roles(UserRole.shelter_coordinator, UserRole.admin)), session: Session = Depends(get_session)):
    batch = session.get(FoodBatch, payload.batch_id)
    if not batch or batch.state not in {BatchState.free, BatchState.discounted}:
        raise HTTPException(status_code=404, detail='donation-eligible batch not found')
    if batch.quantity_available < payload.quantity:
        raise HTTPException(status_code=409, detail='not enough donation stock')
    shelter = get_user_shelter(session, user)
    if not shelter:
        shelter = Shelter(coordinator_id=user.id, name='Default Shelter', capacity_units=100, lat=batch.lat, lng=batch.lng, verification_status=VerificationStatus.verified)
        session.add(shelter); session.commit(); session.refresh(shelter)
    if user.role != UserRole.admin and shelter.verification_status != VerificationStatus.verified:
        raise HTTPException(status_code=403, detail='shelter must be verified')
    batch.quantity_available -= payload.quantity
    claim = DonationClaim(shelter_id=shelter.id, batch_id=batch.id, quantity=payload.quantity)
    session.add(batch); session.add(claim); session.commit(); session.refresh(claim)
    return claim


@router.patch('/claims/{claimId}', response_model=DonationClaimRead)
def update_claim(claimId: int, payload: DonationClaimUpdate, user: User = Depends(require_roles(UserRole.shelter_coordinator, UserRole.admin)), session: Session = Depends(get_session)):
    claim = session.get(DonationClaim, claimId)
    if not claim or claim.status == ClaimStatus.deleted:
        raise HTTPException(status_code=404, detail='claim not found')
    if user.role != UserRole.admin:
        shelter = get_user_shelter(session, user)
        if not shelter or shelter.id != claim.shelter_id:
            raise HTTPException(status_code=403, detail='not your claim')
    if payload.status:
        claim.status = payload.status
    session.add(claim); session.commit(); session.refresh(claim)
    return claim


@router.delete('/claims/{claimId}', status_code=204)
def delete_claim(claimId: int, user: User = Depends(require_roles(UserRole.shelter_coordinator, UserRole.admin)), session: Session = Depends(get_session)):
    claim = session.get(DonationClaim, claimId)
    if not claim:
        raise HTTPException(status_code=404, detail='claim not found')
    claim.status = ClaimStatus.deleted
    session.add(claim); session.commit()
    return None


@router.post('/claims/{claimId}/receive', response_model=DonationClaimRead)
def receive_claim(claimId: int, user: User = Depends(require_roles(UserRole.shelter_coordinator, UserRole.admin)), session: Session = Depends(get_session)):
    claim = session.get(DonationClaim, claimId)
    if not claim or claim.status == ClaimStatus.deleted:
        raise HTTPException(status_code=404, detail='claim not found')
    claim.status = ClaimStatus.received
    claim.received_at = datetime.now(timezone.utc)
    session.add(claim); session.commit(); session.refresh(claim)
    return claim
