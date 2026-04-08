from datetime import datetime
from typing import Generator, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Integer, String, create_engine
from sqlalchemy.orm import Mapped, Session, declarative_base, mapped_column, sessionmaker

from utils import generate_unique_nickname

DB_URL = "mysql+pymysql://root:Aa11221122@localhost:3306/pay_chat"

engine = create_engine(DB_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    nickname: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default=None)
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


app = FastAPI(title="Pay Chat API", version="0.1.0")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.on_event("startup")
def startup_event() -> None:
    Base.metadata.create_all(bind=engine)


@app.post("/users", response_model=UserOut)
def create_user(user_in: UserCreate, db: Session = Depends(get_db)) -> User:
    exists = db.query(User).filter(User.phone == user_in.phone).first()
    if exists:
        raise HTTPException(status_code=400, detail="phone already exists")

    if not user_in.nickname:
        user_in.nickname = generate_unique_nickname(user_in.phone)

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
