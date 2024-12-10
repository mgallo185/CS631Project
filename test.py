from sqlalchemy import create_engine

# Define the SQLAlchemy connection string
SQLALCHEMY_DATABASE_URI = 'mysql+mysqldb://songjiang:123456@34.42.219.23:3306/wallet'

# Create the SQLAlchemy engine
engine = create_engine(SQLALCHEMY_DATABASE_URI, echo=True)

# Test the connection
try:
    connection = engine.connect()
    print("Connection successful!")
except Exception as e:
    print(f"Connection failed: {e}")
finally:
    connection.close()
