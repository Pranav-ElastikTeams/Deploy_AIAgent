from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError, ProgrammingError
from db.models import Base
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Fetch database URI from .env
DATABASE_URI = os.getenv('DATABASE_URI')

if not DATABASE_URI:
    # Fallback to SQLite for testing if no DATABASE_URI is set
    DATABASE_URI = 'sqlite:///site.db'
    print("No DATABASE_URI found, using SQLite for testing")

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URI, echo=False)  # Set echo=False for production

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency to get DB session
def get_db_session() -> sessionmaker:
    """Get a new SQLAlchemy database session."""
    db = SessionLocal()
    return db

# Initialize DB with models
def init_db() -> None:
    """Initialize the database and create tables if they do not exist."""
    try:
        Base.metadata.create_all(bind=engine)
        print("Database initialized successfully.")
    except (OperationalError, ProgrammingError) as e:
        print(f"Error initializing the database: {e}")
        print("This might be due to insufficient permissions.")
        print("Please ensure your database user has CREATE TABLE permissions.")
        print("For testing, you can use SQLite by setting DATABASE_URI=sqlite:///site.db")
        # Do not raise the error - let the app continue without database
        # The app will fail gracefully when trying to use database features
