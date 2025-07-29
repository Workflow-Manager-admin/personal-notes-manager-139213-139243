from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
import os
import sys

# Add notes_database to sys.path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../notes_database")))

from db import SessionLocal  # type: ignore
from models import User, Note  # type: ignore

# JWT settings
SECRET_KEY = os.getenv("SECRET_KEY", "temporary_dev_secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30  # 30 days

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# Pydantic models for serialization and validation

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=64, description="User's username")
    email: EmailStr

class UserCreate(UserBase):
    password: str = Field(..., min_length=5, max_length=256)

class UserOut(UserBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True

class Token(BaseModel):
    access_token: str
    token_type: str

class NoteBase(BaseModel):
    title: str = Field(..., max_length=128)
    content: Optional[str] = Field(default=None, description="Note content")

class NoteCreate(NoteBase):
    pass

class NoteUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=128)
    content: Optional[str] = Field(None)

class NoteOut(NoteBase):
    id: int
    created_at: datetime
    updated_at: datetime
    user_id: int

    class Config:
        orm_mode = True

# FastAPI app config
app = FastAPI(
    title="Personal Notes Backend API",
    description="Backend API for handling user auth and personal notes management.",
    version="1.0.0",
    openapi_tags=[
        {"name": "Authentication", "description": "User registration, login, and security"},
        {"name": "Notes", "description": "Create, update, view, delete, search notes"}
    ]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DATABASE Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Utility functions for auth
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Generates JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# User auth helpers
def get_user_by_username(db, username: str):
    return db.query(User).filter(User.username == username).first()

def get_user_by_email(db, email: str):
    return db.query(User).filter(User.email == email).first()

def get_user(db, user_id: int):
    return db.query(User).filter(User.id == user_id).first()

def authenticate_user(db, username: str, password: str):
    user = get_user_by_username(db, username)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user

def get_current_user(token: str = Depends(oauth2_scheme), db=Depends(get_db)):
    """Decodes JWT and retrieves user from DB."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user(db, user_id)
    if user is None:
        raise credentials_exception
    return user

# Root Health Check
@app.get("/", summary="Health Check", tags=["General"])
def health_check():
    """Simple health check endpoint."""
    return {"message": "Healthy"}


#####################
# AUTH ENDPOINTS
#####################

# PUBLIC_INTERFACE
@app.post("/auth/register", response_model=UserOut, summary="Register a new user", tags=["Authentication"])
def register(user: UserCreate, db=Depends(get_db)):
    """
    Register a new user.
    Returns the newly created user record (excluding password).
    """
    if get_user_by_username(db, user.username):
        raise HTTPException(status_code=409, detail="Username already taken.")
    if get_user_by_email(db, user.email):
        raise HTTPException(status_code=409, detail="Email already in use.")
    user_obj = User(
        username=user.username,
        email=user.email,
        hashed_password=get_password_hash(user.password)
    )
    db.add(user_obj)
    db.commit()
    db.refresh(user_obj)
    return user_obj

# PUBLIC_INTERFACE
@app.post("/auth/login", response_model=Token, summary="Login and get JWT token", tags=["Authentication"])
def login(form_data: OAuth2PasswordRequestForm = Depends(), db=Depends(get_db)):
    """
    User login.
    Returns JWT access token on success.
    Use 'username' field for either username or email.
    """
    # Try username first, then email
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        user_by_email = get_user_by_email(db, form_data.username)
        if user_by_email and verify_password(form_data.password, user_by_email.hashed_password):
            user = user_by_email
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    access_token = create_access_token(
        data={"sub": user.id}
    )
    return {"access_token": access_token, "token_type": "bearer"}

# PUBLIC_INTERFACE
@app.get("/auth/me", response_model=UserOut, summary="Get current user profile", tags=["Authentication"])
def get_profile(current_user: User = Depends(get_current_user)):
    """
    Get details about the current authed user.
    """
    return current_user


#####################
# NOTES ENDPOINTS
#####################

# PUBLIC_INTERFACE
@app.post("/notes/", response_model=NoteOut, status_code=201, summary="Create a new note", tags=["Notes"])
def create_note(note: NoteCreate, db=Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Create a new note for the authenticated user.
    """
    note_obj = Note(
        title=note.title,
        content=note.content,
        user_id=current_user.id,
    )
    db.add(note_obj)
    db.commit()
    db.refresh(note_obj)
    return note_obj

# PUBLIC_INTERFACE
@app.get("/notes/", response_model=List[NoteOut], summary="List all user notes", tags=["Notes"])
def list_notes(
    q: Optional[str] = Query(None, description="Search term for note title or content"),
    skip: int = 0,
    limit: int = 100,
    db=Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all notes for the authenticated user.
    Supports filtering by search term (on title or content).
    """
    query = db.query(Note).filter(Note.user_id == current_user.id)
    if q:
        search = f"%{q}%"
        query = query.filter((Note.title.ilike(search)) | (Note.content.ilike(search)))
    notes = query.order_by(Note.updated_at.desc()).offset(skip).limit(limit).all()
    return notes

# PUBLIC_INTERFACE
@app.get("/notes/{note_id}", response_model=NoteOut, summary="Get a single note", tags=["Notes"])
def get_note(note_id: int, db=Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Retrieve a single note belonging to the authenticated user.
    """
    note = db.query(Note).filter(Note.id == note_id, Note.user_id == current_user.id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")
    return note

# PUBLIC_INTERFACE
@app.put("/notes/{note_id}", response_model=NoteOut, summary="Update a note", tags=["Notes"])
def update_note(note_id: int, note_update: NoteUpdate, db=Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Update a note belonging to the authenticated user.
    """
    note = db.query(Note).filter(Note.id == note_id, Note.user_id == current_user.id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")
    if note_update.title is not None:
        note.title = note_update.title
    if note_update.content is not None:
        note.content = note_update.content
    db.commit()
    db.refresh(note)
    return note

# PUBLIC_INTERFACE
@app.delete("/notes/{note_id}", status_code=204, summary="Delete a note", tags=["Notes"])
def delete_note(note_id: int, db=Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Delete a note belonging to the authenticated user.
    """
    note = db.query(Note).filter(Note.id == note_id, Note.user_id == current_user.id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")
    db.delete(note)
    db.commit()
    return JSONResponse(status_code=204, content=None)

# Error handler examples
@app.exception_handler(HTTPException)
def custom_http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )
