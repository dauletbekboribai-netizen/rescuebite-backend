from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, delete, select
from app.api.deps import get_current_user
from app.database import get_session
from app.models.domain import Address, BatchIngredient, User, UserAllergy
from app.schemas.common import AddressCreate, AddressRead, AllergyCheckRequest, AllergyCheckResponse, AllergyUpdate, UserRead, UserUpdate

router = APIRouter(prefix='/users', tags=['users'])


@router.get('/me', response_model=UserRead)
def me(user: User = Depends(get_current_user)):
    return user


@router.patch('/me', response_model=UserRead)
def update_me(payload: UserUpdate, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    if payload.username is not None:
        exists = session.exec(select(User).where(User.username == payload.username, User.id != user.id)).first()
        if exists:
            raise HTTPException(status_code=409, detail='username already exists')
        user.username = payload.username
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.get('/me/addresses', response_model=list[AddressRead])
def list_addresses(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return session.exec(select(Address).where(Address.user_id == user.id).order_by(Address.created_at.desc())).all()


@router.post('/me/addresses', response_model=AddressRead, status_code=201)
def create_address(payload: AddressCreate, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    address = Address(user_id=user.id, **payload.model_dump())
    session.add(address)
    session.commit()
    session.refresh(address)
    return address


@router.patch('/me/addresses/{addressId}', response_model=AddressRead)
def update_address(addressId: int, payload: AddressCreate, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    address = session.get(Address, addressId)
    if not address or address.user_id != user.id:
        raise HTTPException(status_code=404, detail='address not found')
    for key, value in payload.model_dump().items():
        setattr(address, key, value)
    session.add(address)
    session.commit()
    session.refresh(address)
    return address


@router.delete('/me/addresses/{addressId}', status_code=204)
def delete_address(addressId: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    address = session.get(Address, addressId)
    if not address or address.user_id != user.id:
        raise HTTPException(status_code=404, detail='address not found')
    session.delete(address)
    session.commit()
    return None


@router.put('/me/allergies', response_model=AllergyUpdate)
def replace_allergies(payload: AllergyUpdate, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    session.exec(delete(UserAllergy).where(UserAllergy.user_id == user.id))
    for allergen in set(payload.allergens):
        session.add(UserAllergy(user_id=user.id, allergen=allergen))
    session.commit()
    return AllergyUpdate(allergens=list(set(payload.allergens)))


@router.delete('/me/allergies', status_code=204)
def clear_allergies(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    session.exec(delete(UserAllergy).where(UserAllergy.user_id == user.id))
    session.commit()
    return None


@router.post('/me/allergies/check', response_model=AllergyCheckResponse)
def check_ingredient_payload(payload: AllergyCheckRequest, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    user_allergens = {row.allergen for row in session.exec(select(UserAllergy).where(UserAllergy.user_id == user.id)).all()}
    ingredient_allergens = {item.allergen for item in payload.ingredients if item.allergen is not None}
    conflicts = sorted(user_allergens.intersection(ingredient_allergens), key=lambda x: x.value)
    return AllergyCheckResponse(safe=not conflicts, conflicts=conflicts)
