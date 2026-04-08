from datetime import datetime, timedelta, timezone
from typing import Generator, Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Integer, String, create_engine
from sqlalchemy.orm import Mapped, Session, declarative_base, mapped_column, sessionmaker

DB_URL = "mysql+pymysql://root:Aa11221122@localhost:3306/pay_chat"
SECRET_KEY = "pay_chat_secret_key_change_in_production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7
REFRESH_TOKEN_EXPIRE_DAYS = 30

engine = create_engine(DB_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    nickname: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    avatar: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    real_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    id_card: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    update_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class UserBase(BaseModel):
    phone: str = Field(..., max_length=20)
    nickname: Optional[str] = Field(default=None, max_length=50)
    avatar: Optional[str] = Field(default=None, max_length=255)
    role: Optional[str] = Field(default=None, max_length=20)
    real_name: Optional[str] = Field(default=None, max_length=50)
    id_card: Optional[str] = Field(default=None, max_length=30)
    status: int = 1


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=255)


class UserUpdate(BaseModel):
    phone: Optional[str] = Field(default=None, max_length=20)
    password: Optional[str] = Field(default=None, min_length=6, max_length=255)
    nickname: Optional[str] = Field(default=None, max_length=50)
    avatar: Optional[str] = Field(default=None, max_length=255)
    role: Optional[str] = Field(default=None, max_length=20)
    real_name: Optional[str] = Field(default=None, max_length=50)
    id_card: Optional[str] = Field(default=None, max_length=30)
    status: Optional[int] = None


class UserOut(UserBase):
    id: int
    create_time: datetime
    update_time: datetime

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    phone: str = Field(..., max_length=20)
    password: str = Field(..., min_length=6, max_length=255)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    access_token_expire_days: int = ACCESS_TOKEN_EXPIRE_DAYS
    refresh_token_expire_days: int = REFRESH_TOKEN_EXPIRE_DAYS


app = FastAPI(title="Pay Chat API", version="0.2.0")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _create_token(user_id: int, token_type: Literal["access", "refresh"], expire_days: int) -> str:
    expire_at = datetime.now(timezone.utc) + timedelta(days=expire_days)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "exp": expire_at,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_token_pair(user_id: int) -> TokenPair:
    return TokenPair(
        access_token=_create_token(user_id, "access", ACCESS_TOKEN_EXPIRE_DAYS),
        refresh_token=_create_token(user_id, "refresh", REFRESH_TOKEN_EXPIRE_DAYS),
    )


def validate_refresh_token(refresh_token: str) -> int:
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="refresh token invalid or expired, please login again")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="invalid token type")

    user_id = payload.get("sub")
    if not user_id or not str(user_id).isdigit():
        raise HTTPException(status_code=401, detail="invalid token subject")

    return int(user_id)


@app.on_event("startup")
def startup_event() -> None:
    Base.metadata.create_all(bind=engine)


@app.post("/auth/login", response_model=TokenPair)
def login(login_in: LoginRequest, db: Session = Depends(get_db)) -> TokenPair:
    user = db.query(User).filter(User.phone == login_in.phone).first()
    if not user or user.password != login_in.password:
        raise HTTPException(status_code=401, detail="phone or password is incorrect")

    if user.status == 0:
        raise HTTPException(status_code=403, detail="user is disabled")

    return create_token_pair(user.id)


@app.post("/auth/refresh", response_model=TokenPair)
def refresh_token(token_in: RefreshTokenRequest, db: Session = Depends(get_db)) -> TokenPair:
    user_id = validate_refresh_token(token_in.refresh_token)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="refresh token invalid, please login again")

    if user.status == 0:
        raise HTTPException(status_code=403, detail="user is disabled")

    return create_token_pair(user.id)


@app.post("/users", response_model=UserOut)
def create_user(user_in: UserCreate, db: Session = Depends(get_db)) -> User:
    exists = db.query(User).filter(User.phone == user_in.phone).first()
    if exists:
        raise HTTPException(status_code=400, detail="phone already exists")

    user = User(**user_in.model_dump())
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.get("/users", response_model=list[UserOut])
def list_users(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[User]:
    return db.query(User).offset(skip).limit(limit).all()


@app.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db)) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    return user


@app.put("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, user_in: UserUpdate, db: Session = Depends(get_db)) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    data = user_in.model_dump(exclude_unset=True)
    if "phone" in data and data["phone"] != user.phone:
        exists = db.query(User).filter(User.phone == data["phone"]).first()
        if exists:
            raise HTTPException(status_code=400, detail="phone already exists")

    for key, value in data.items():
        setattr(user, key, value)

    user.update_time = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return user


@app.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    db.delete(user)
    db.commit()
    return {"message": "deleted"}
