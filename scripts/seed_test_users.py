#!/usr/bin/env python3
"""Script to seed test users in the database."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from bondable.bond.config import Config
from bondable.bond.providers.metadata import User, Base


def seed_test_users():
    """Seed test users into the database."""
    
    # Test users data
    test_users = [
        {
            "id": "00us5pzixgemQF8c0697",
            "email": "testuser1@bondai.com",
            "sign_in_method": "okta",
            "name": "testuser1@bondai.com"
        },
        {
            "id": "00us5pzixxlUQmS9I697",
            "email": "testuser2@bondai.com",
            "sign_in_method": "okta",
            "name": "testuser2@bondai.com"
        },
        {
            "id": "00us5pziy4pXMWcz3697",
            "email": "testuser3@bondai.com",
            "sign_in_method": "okta",
            "name": "testuser3@bondai.com"
        },
        {
            "id": "00us5pziy97wgOJP6697",
            "email": "testuser4@bondai.com",
            "sign_in_method": "okta",
            "name": "testuser4@bondai.com"
        },
        {
            "id": "00us5pziyeKZ4WStH697",
            "email": "testuser5@bondai.com",
            "sign_in_method": "okta",
            "name": "testuser5@bondai.com"
        },
        {
            "id": "00us5pziyj3ATFuJz697",
            "email": "testuser6@bondai.com",
            "sign_in_method": "okta",
            "name": "testuser6@bondai.com"
        }
    ]
    
    # Get database configuration
    config = Config.config()
    database_url = config.get_metadata_db_url()
    
    # Create engine and session
    engine = create_engine(database_url, echo=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        for user_data in test_users:
            # Check if user with this email already exists
            existing_user = session.query(User).filter(
                User.email == user_data["email"]
            ).first()
            
            if existing_user:
                print(f"User with email {user_data['email']} already exists, skipping...")
                continue
            
            # Create new user
            new_user = User(
                id=user_data["id"],
                email=user_data["email"],
                sign_in_method=user_data["sign_in_method"],
                name=user_data["name"]
            )
            
            session.add(new_user)
            print(f"Created user: {user_data['email']}")
        
        # Commit the transaction
        session.commit()
        print("\nSuccessfully seeded all test users!")
        
    except Exception as e:
        session.rollback()
        print(f"Error seeding users: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed_test_users()