from datetime import datetime
from config.database import db
from bson.objectid import ObjectId

class Contribution:
    def __init__(self, banglish, bengali, user_id, feedback=None, _id=None):
        self.banglish = banglish
        self.bengali = bengali
        self.user_id = user_id
        self.feedback = feedback
        self.status = 'pending'  # pending, approved, rejected
        self.submitted_at = datetime.now()
        self.reviewed_at = None
        self.reviewer_id = None
        self.reviewer_comment = None
        self._id = _id

    def save(self):
        contribution_data = {
            'banglish': self.banglish,
            'bengali': self.bengali,
            'user_id': self.user_id,
            'feedback': self.feedback,
            'status': self.status,
            'submitted_at': self.submitted_at,
            'reviewed_at': self.reviewed_at,
            'reviewer_id': self.reviewer_id,
            'reviewer_comment': self.reviewer_comment
        }
        
        if self._id:
            db.contributions.update_one(
                {'_id': ObjectId(self._id)},
                {'$set': contribution_data}
            )
        else:
            result = db.contributions.insert_one(contribution_data)
            self._id = str(result.inserted_id)
        
        return self

    @staticmethod
    def get_pending_contributions():
        contributions = db.contributions.find({'status': 'pending'})
        return [Contribution(
            banglish=c['banglish'],
            bengali=c['bengali'],
            user_id=c['user_id'],
            feedback=c.get('feedback'),
            _id=str(c['_id'])
        ) for c in contributions]

    @staticmethod
    def get_by_id(contribution_id):
        c = db.contributions.find_one({'_id': ObjectId(contribution_id)})
        if c:
            return Contribution(
                banglish=c['banglish'],
                bengali=c['bengali'],
                user_id=c['user_id'],
                feedback=c.get('feedback'),
                _id=str(c['_id'])
            )
        return None

    def approve(self, reviewer_id, comment=None):
        self.status = 'approved'
        self.reviewed_at = datetime.now()
        self.reviewer_id = reviewer_id
        self.reviewer_comment = comment
        self.save()

    def reject(self, reviewer_id, comment=None):
        self.status = 'rejected'
        self.reviewed_at = datetime.now()
        self.reviewer_id = reviewer_id
        self.reviewer_comment = comment
        self.save() 