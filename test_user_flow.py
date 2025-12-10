from app import app, db, User, SearchHistory
import uuid

def test_user_flow():
    with app.app_context():
        # Create a unique email for testing
        email = f"test_{uuid.uuid4()}@example.com"
        password = "password123"
        
        print(f"Creating user {email}...")
        user = User(email=email, name="Test", surname="User", 
                    privacy_accepted=True, newsletter_opt_in=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        print("User created successfully.")
        
        # Verify user exists
        retrieved_user = User.query.filter_by(email=email).first()
        assert retrieved_user is not None
        assert retrieved_user.check_password(password)
        print("User verification passed.")
        
        # Add search history
        print("Adding search history...")
        search = SearchHistory(user_id=retrieved_user.id, search_term="Fender Stratocaster")
        db.session.add(search)
        db.session.commit()
        
        # Verify history
        history = SearchHistory.query.filter_by(user_id=retrieved_user.id).all()
        assert len(history) == 1
        assert history[0].search_term == "Fender Stratocaster"
        print("Search history verification passed.")
        
        print("\nAll tests passed!")

if __name__ == "__main__":
    test_user_flow()
