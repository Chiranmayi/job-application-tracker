from sqlalchemy import text
from app.database import engine
from app import models

try:
    with engine.connect() as connection:
        result = connection.execute(text("SELECT current_database()"))
        print("Connected to database:", result.scalar())

    models.Base.metadata.create_all(bind=engine)
    print("Tables created or already exist successfully!")

except Exception as e:
    print("Database connection failed:", e)
