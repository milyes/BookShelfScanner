from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(255))
    isbn = db.Column(db.String(50))
    publisher = db.Column(db.String(255))
    publication_year = db.Column(db.Integer)
    genre = db.Column(db.String(100))
    thumbnail_path = db.Column(db.String(255))
    description = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    modified_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    books = db.relationship('Book', backref='owner', lazy='dynamic')
    libraries = db.relationship('Library', backref='owner', lazy='dynamic')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Library(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    books = db.relationship('LibraryBook', backref='library', lazy='dynamic')

class LibraryBook(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    library_id = db.Column(db.Integer, db.ForeignKey('library.id'))
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'))
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    personal_rating = db.Column(db.Integer)  # 1-5 rating
    read_status = db.Column(db.String(50))  # "Read", "To Read", "Reading"

class RestorationType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    parameters = db.relationship('RestorationParameter', backref='restoration_type', lazy='dynamic')

class RestorationParameter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restoration_type_id = db.Column(db.Integer, db.ForeignKey('restoration_type.id'))
    name = db.Column(db.String(100), nullable=False)
    value = db.Column(db.String(255))
    description = db.Column(db.Text)

class RestorationJob(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    original_file_path = db.Column(db.String(255), nullable=False)
    restored_file_path = db.Column(db.String(255))
    restoration_type_id = db.Column(db.Integer, db.ForeignKey('restoration_type.id'))
    parameters_used = db.Column(db.Text)  # JSON string
    status = db.Column(db.String(50))  # "Pending", "Processing", "Completed", "Failed"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)