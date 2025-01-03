from flask_login import UserMixin
from bson.objectid import ObjectId
from config.database import users
import bcrypt

class User(UserMixin):
    def __init__(self, username, email, password=None, _id=None):
        self.username = username
        self.email = email
        self.password = password
        self._id = _id
        self._is_active = True
        self.role = 'user'
        self.last_login = None
        self.login_attempts = 0
        self.locked_until = None

    def is_admin(self):
        return self.role == 'admin'

    @staticmethod
    def create_admin(username, email, password):
        user = User(username, email, password)
        user.role = 'admin'
        return user.save()

    @staticmethod
    def get_by_id(user_id):
        user_data = users.find_one({'_id': ObjectId(user_id)})
        if user_data:
            return User(
                username=user_data['username'],
                email=user_data['email'],
                _id=str(user_data['_id'])
            )
        return None

    @staticmethod
    def get_by_email(email):
        user_data = users.find_one({'email': email})
        if user_data:
            return User(
                username=user_data['username'],
                email=user_data['email'],
                password=user_data['password'],
                _id=str(user_data['_id'])
            )
        return None

    def get_id(self):
        return str(self._id)

    def save(self):
        if not self.password:
            raise ValueError("Password is required")
            
        # Hash password
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(self.password.encode('utf-8'), salt)
        
        user_data = {
            'username': self.username,
            'email': self.email,
            'password': hashed
        }
        
        result = users.insert_one(user_data)
        self._id = str(result.inserted_id)
        return self

    @staticmethod
    def check_password(email, password):
        user = User.get_by_email(email)
        if user and bcrypt.checkpw(
            password.encode('utf-8'), 
            user.password
        ):
            return user
        return None 