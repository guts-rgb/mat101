"""
Upload model for tracking MATLAB file uploads and executions
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Upload(db.Model):
    __tablename__ = 'uploads'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    result_path = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(20), default='uploaded')  # uploaded, running, completed, failed
    execution_log = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f'<Upload {self.file_name} - {self.status}>'
    
    @property
    def execution_duration(self):
        """Calculate execution duration if completed"""
        if self.completed_at and self.timestamp:
            return (self.completed_at - self.timestamp).total_seconds()
        return None