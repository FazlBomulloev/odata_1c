import logging
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import (
    OWNER_PASSWORD,
    OWNER_USERNAME,
    SESSION_SECRET,
)
from .db import SessionLocal, User, get_session
from .security import hash_password, verify_password

logger = logging.getLogger(__name__)

ROLE_OWNER = 'owner'
ROLE_EMPLOYEE = 'employee'

router = APIRouter(prefix='/api/auth', tags=['auth'])
users_router = APIRouter(prefix='/api/users', tags=['users'])


def resolve_session_secret() -> str:
    """Возвращает SESSION_SECRET из env или временный на время процесса."""
    if SESSION_SECRET:
        return SESSION_SECRET
    logger.warning(
        'SESSION_SECRET не задан в .env — сгенерирую временный. '
        'После рестарта все сессии инвалидируются.'
    )
    return secrets.token_urlsafe(32)


async def ensure_owner() -> None:
    """Создаёт owner-а при первом запуске, если таблица пуста."""
    async with SessionLocal() as session:
        q = select(User).where(User.role == ROLE_OWNER)
        exists = (await session.execute(q)).scalars().first()
        if exists:
            return
        if not OWNER_PASSWORD:
            logger.warning(
                'OWNER_PASSWORD не задан — owner не создан. '
                'Задайте OWNER_USERNAME и OWNER_PASSWORD в .env '
                'и перезапустите backend.'
            )
            return
        user = User(
            username=OWNER_USERNAME,
            password_hash=hash_password(OWNER_PASSWORD),
            role=ROLE_OWNER,
            is_active=True,
            created_at=datetime.utcnow(),
        )
        session.add(user)
        await session.commit()
        logger.info(
            'Создан owner "%s" (это единоразово, дальше сотрудники '
            'заводятся через UI).', OWNER_USERNAME,
        )


async def require_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    """Достаёт текущего пользователя из session-cookie."""
    user_id = request.session.get('user_id')
    if not user_id:
        raise HTTPException(status_code=401, detail='Нужна авторизация')
    user = await session.get(User, user_id)
    if not user or not user.is_active:
        request.session.clear()
        raise HTTPException(
            status_code=401, detail='Сессия недействительна',
        )
    return user


async def require_owner(
    user: User = Depends(require_user),
) -> User:
    if user.role != ROLE_OWNER:
        raise HTTPException(
            status_code=403, detail='Доступно только владельцу',
        )
    return user


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime
    created_by: int | None


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=6, max_length=256)
    role: str = ROLE_EMPLOYEE


class UserPatchRequest(BaseModel):
    password: str | None = Field(default=None, min_length=6)
    is_active: bool | None = None


def _to_out(u: User) -> UserOut:
    return UserOut(
        id=u.id, username=u.username, role=u.role,
        is_active=u.is_active, created_at=u.created_at,
        created_by=u.created_by,
    )


@router.post('/login', response_model=UserOut)
async def login(
    req: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    q = select(User).where(User.username == req.username)
    user = (await session.execute(q)).scalars().first()
    if (
        not user
        or not user.is_active
        or not verify_password(req.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=401, detail='Неверный логин или пароль',
        )
    request.session['user_id'] = user.id
    return _to_out(user)


@router.post('/logout')
async def logout(request: Request):
    request.session.clear()
    return {'ok': True}


@router.get('/me', response_model=UserOut)
async def me(user: User = Depends(require_user)):
    return _to_out(user)


@users_router.get('', response_model=list[UserOut])
async def list_users(
    _: User = Depends(require_owner),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(
            select(User).order_by(User.id),
        )
    ).scalars().all()
    return [_to_out(u) for u in rows]


@users_router.post('', response_model=UserOut)
async def create_user(
    req: UserCreateRequest,
    owner: User = Depends(require_owner),
    session: AsyncSession = Depends(get_session),
):
    if req.role not in (ROLE_OWNER, ROLE_EMPLOYEE):
        raise HTTPException(status_code=400, detail='Неверная роль')
    q = select(User).where(User.username == req.username)
    if (await session.execute(q)).scalars().first():
        raise HTTPException(
            status_code=409, detail='Логин уже занят',
        )
    user = User(
        username=req.username,
        password_hash=hash_password(req.password),
        role=req.role,
        is_active=True,
        created_at=datetime.utcnow(),
        created_by=owner.id,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return _to_out(user)


@users_router.patch('/{user_id}', response_model=UserOut)
async def patch_user(
    user_id: int,
    req: UserPatchRequest,
    owner: User = Depends(require_owner),
    session: AsyncSession = Depends(get_session),
):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail='Не найдено')
    if req.password is not None:
        user.password_hash = hash_password(req.password)
    if req.is_active is not None:
        if (
            user.id == owner.id
            and req.is_active is False
        ):
            raise HTTPException(
                status_code=400,
                detail='Нельзя деактивировать самого себя',
            )
        user.is_active = req.is_active
    await session.commit()
    await session.refresh(user)
    return _to_out(user)


@users_router.delete('/{user_id}')
async def delete_user(
    user_id: int,
    owner: User = Depends(require_owner),
    session: AsyncSession = Depends(get_session),
):
    if user_id == owner.id:
        raise HTTPException(
            status_code=400,
            detail='Нельзя удалить самого себя',
        )
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail='Не найдено')
    if user.role == ROLE_OWNER:
        # На случай будущих сценариев с несколькими owner-ами —
        # запретим удаление последнего.
        q = select(User).where(
            User.role == ROLE_OWNER, User.is_active.is_(True),
        )
        owners = (await session.execute(q)).scalars().all()
        if len(owners) <= 1:
            raise HTTPException(
                status_code=400,
                detail='Нельзя удалить единственного владельца',
            )
    await session.delete(user)
    await session.commit()
    return {'ok': True}
