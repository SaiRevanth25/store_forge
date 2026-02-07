from datetime import timedelta
from typing import Any, Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import update, select

from core.config import settings
from services.user_services import UserService

from core.orm import get_session
from core.orm import User as UserORM
from core.utils import get_current_user
from fastapi.security import OAuth2PasswordRequestForm


from core.security import (
    get_password_hash,
    verify_password,
    create_access_token, verify_password_reset_token,
)
from models.users import (
    Message,
    UpdatePassword,
    UserCreate,
    UserRegister,
    UserUpdateMe,
    UserBase,
    Token,
    NewPassword,
)


router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserBase)
async def create_user(*, session=Depends(get_session), user_in: UserCreate) -> Any:
    """
    Create new user.
    """
    service = UserService(session)
    user = await service.get_user_by_email(email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )

    user = await service.create_user(user_create=user_in)
    return user


@router.patch("/me", response_model=UserBase)
async def update_user_me(
    *,
    session=Depends(get_session),
    user_in: UserUpdateMe,
    current_user=Depends(get_current_user),
) -> Any:
    """
    Update own user.
    """
    service = UserService(session)

    if user_in.email:
        existing_user = await service.get_user_by_email(email=user_in.email)
        if existing_user and existing_user.user_id != current_user.user_id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )
    current_user = await service.update_user(user_in=user_in, db_user=current_user)
    return current_user


@router.patch("/me/password", response_model=Message)
async def update_password_me(
    *,
    session=Depends(get_session),
    body: UpdatePassword,
    current_user=Depends(get_current_user),
) -> Any:
    """
    Update own password.
    """

    if not verify_password(body.current_password, current_user.password):
        raise HTTPException(status_code=400, detail="Incorrect password")
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=400, detail="New password cannot be the same as the current one"
        )

    hashed_password = get_password_hash(body.new_password)
    current_user.password = hashed_password
    user_update = (
        update(UserORM)
        .where(UserORM.user_id == current_user.user_id)
        .values(
            password=hashed_password,
        )
    )
    await session.execute(user_update)
    await session.commit()
    return Message(message="Password updated successfully")


@router.get("/me", response_model=UserBase)
def read_user_me(current_user=Depends(get_current_user)) -> Any:
    """
    Get current user.
    """
    return current_user


@router.delete("/me", response_model=Message)
async def delete_user_me(
    session=Depends(get_session), current_user=Depends(get_current_user)
) -> Any:
    """
    Delete own user and associated Pinecone namespace.
    """
    user_id = current_user.user_id

    stmt = select(UserORM).where(UserORM.user_id == user_id)
    user = await session.scalar(stmt)

    if not user:
        raise HTTPException(404, f"User '{user_id}' not found")

    # Delete Pinecone namespace
    try:
        pinecone_service.delete_namespace(user_id)
    except Exception as e:
        # Log error but don't fail the deletion
        print(f"Warning: Failed to delete Pinecone namespace for user {user_id}: {e}")

    await session.delete(user)
    await session.commit()
    return Message(message="User deleted successfully")


@router.post("/signup", response_model=UserBase)
async def register_user(user_in: UserRegister, session=Depends(get_session)) -> Any:
    """
    Create new user without the need to be logged in.
    """
    service = UserService(session)
    user = await service.get_user_by_email(email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system",
        )
    user_create = UserCreate.model_validate(dict(user_in))
    user = await service.create_user(user_create=user_create)
    return user


@router.post("/login/access-token")
async def login_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session=Depends(get_session),
) -> Token:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    service = UserService(session)
    user = await service.authenticate(
        email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return Token(
        access_token=create_access_token(
            user.user_id, expires_delta=access_token_expires
        )
    )


@router.patch("/reset-password/", response_model=Message)
async def reset_password(body: NewPassword, session=Depends(get_session)) -> Message:
    """
    Reset password
    """
    service = UserService(session)
    email = await verify_password_reset_token(token=body.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid token")
    user = await service.get_user_by_email(email=email)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this email does not exist in the system.",
        )

    hashed_password = get_password_hash(password=body.new_password)
    user.password = hashed_password
    session.add(user)
    await session.commit()
    return Message(message="Password updated successfully")
