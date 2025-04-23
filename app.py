import os
import logging
import uuid
import cv2
import numpy as np
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from book_detector import detect_books, extract_book_info

# Configure app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure file upload settings
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# Create upload folder if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_image():
    if 'file' not in request.files:
        flash('No file part', 'danger')
        return redirect(request.url)
    
    file = request.files['file']
    if file.filename == '':
        flash('No selected file', 'danger')
        return redirect(url_for('index'))
    
    if file and allowed_file(file.filename):
        try:
            # Create a unique filename
            unique_filename = str(uuid.uuid4()) + os.path.splitext(secure_filename(file.filename))[1]
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(filepath)
            
            # Process the image and detect books
            image = cv2.imread(filepath)
            if image is None:
                flash('Failed to process image', 'danger')
                return redirect(url_for('index'))
            
            # Detect books in the image
            book_images = detect_books(image)
            
            # If no books were detected
            if not book_images or len(book_images) == 0:
                flash('No books detected in the image. Please try a clearer image.', 'warning')
                return redirect(url_for('index'))
            
            # Extract book information from the detected book images
            books = []
            for i, book_img in enumerate(book_images):
                # Save book image temporarily for display
                book_filename = f"book_{i}_{unique_filename}"
                book_filepath = os.path.join(app.config['UPLOAD_FOLDER'], book_filename)
                cv2.imwrite(book_filepath, book_img)
                
                # Extract book info
                book_info = extract_book_info(book_img)
                
                # Add relative path for display
                book_info['image_path'] = f"/static/uploads/{book_filename}"
                book_info['id'] = i + 1
                books.append(book_info)
            
            # Store the results in session
            session['books'] = books
            session['original_image'] = unique_filename
            
            return redirect(url_for('results'))
            
        except Exception as e:
            logging.error(f"Error processing image: {str(e)}")
            flash(f'Error processing image: {str(e)}', 'danger')
            return redirect(url_for('index'))
    else:
        flash('File type not allowed. Please upload an image (PNG, JPG, JPEG).', 'danger')
        return redirect(url_for('index'))

@app.route('/results')
def results():
    books = session.get('books', [])
    original_image = session.get('original_image', None)
    
    if not books:
        flash('No book data available. Please upload an image first.', 'warning')
        return redirect(url_for('index'))
    
    return render_template('results.html', books=books, original_image=original_image)

# Add error handlers
@app.errorhandler(413)
def too_large(e):
    flash('File too large (max 16MB)', 'danger')
    return redirect(url_for('index'))

@app.errorhandler(500)
def server_error(e):
    flash('Server error: ' + str(e), 'danger')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
