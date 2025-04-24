import os
import logging
import uuid
import cv2
import numpy as np
import tempfile
import json
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from book_detector import detect_books, extract_book_info
from pdf2image import convert_from_path
from pdf_enhancer import enhance_pdf_image, process_pdf, restore_image, restore_document
from book_recommender import generate_book_recommendations, get_genre_analysis

# Configurer le logging
logging.basicConfig(level=logging.DEBUG)

# Configure app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure file upload settings
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

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
            
            # Check if the file is a PDF
            is_pdf = filepath.lower().endswith('.pdf')
            
            if is_pdf:
                try:
                    # Utiliser notre fonctionnalité d'amélioration de PDF
                    logging.debug("Traitement du PDF pour amélioration...")
                    enhanced_images = process_pdf(filepath)
                    
                    if not enhanced_images or len(enhanced_images) == 0:
                        # Fallback sur la méthode originale si process_pdf a échoué
                        logging.debug("Méthode d'amélioration échouée, utilisation de la méthode standard...")
                        pdf_images = convert_from_path(filepath)
                        
                        if not pdf_images:
                            flash('Failed to extract images from PDF', 'danger')
                            return redirect(url_for('index'))
                        
                        # Use the first page as the primary image
                        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                            temp_path = temp_file.name
                            pdf_images[0].save(temp_path, 'JPEG')
                        
                        # Load the image for processing
                        image = cv2.imread(temp_path)
                        os.unlink(temp_path)  # Clean up
                    else:
                        # Utiliser la première image améliorée
                        image = enhanced_images[0]
                        
                        # Générer un PDF amélioré pour le téléchargement ultérieur
                        enhanced_pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], f"enhanced_{unique_filename}.pdf")
                        # Traiter le PDF et créer un PDF amélioré
                        process_pdf(filepath, enhanced_pdf_path, enhance=True)
                        session['enhanced_pdf'] = enhanced_pdf_path
                        
                        # Sauvegarder le résultat original pour affichage
                        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                            temp_path = temp_file.name
                            cv2.imwrite(temp_path, image)
                            session['original_pdf_image'] = temp_path
                        
                except Exception as e:
                    logging.error(f"Error processing PDF: {str(e)}")
                    flash('Failed to process PDF', 'danger')
                    return redirect(url_for('index'))
            else:
                # Process as a regular image
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
        flash('File type not allowed. Please upload an image (PNG, JPG, JPEG) or a PDF document.', 'danger')
        return redirect(url_for('index'))

@app.route('/results')
def results():
    books = session.get('books', [])
    original_image = session.get('original_image', None)
    enhanced_pdf = session.get('enhanced_pdf', None)
    is_pdf = enhanced_pdf is not None
    
    if not books:
        flash('No book data available. Please upload an image first.', 'warning')
        return redirect(url_for('index'))
    
    # Générer des recommandations basées sur les livres détectés
    try:
        recommendations = session.get('recommendations')
        if not recommendations:
            recommendations = generate_book_recommendations(books, num_recommendations=3)
            session['recommendations'] = recommendations
        
        # Analyser les genres et thèmes
        genre_analysis = session.get('genre_analysis')
        if not genre_analysis:
            genre_analysis = get_genre_analysis(books)
            session['genre_analysis'] = genre_analysis
    except Exception as e:
        logging.error(f"Erreur lors de la génération des recommandations: {str(e)}")
        recommendations = []
        genre_analysis = {"genres": [], "themes": [], "analysis": "Analyse non disponible."}
    
    return render_template('results.html', 
                           books=books, 
                           original_image=original_image,
                           enhanced_pdf=enhanced_pdf, 
                           is_pdf=is_pdf,
                           recommendations=recommendations,
                           genre_analysis=genre_analysis)

@app.route('/get-recommendations', methods=['POST'])
def get_recommendations():
    """
    Endpoint API pour générer des recommandations de livres personnalisées.
    """
    try:
        books = session.get('books', [])
        
        if not books:
            return jsonify({"error": "Aucun livre disponible."}), 400
        
        data = request.get_json()
        num_recommendations = data.get('num_recommendations', 5) if data else 5
        
        # Générer de nouvelles recommandations
        recommendations = generate_book_recommendations(books, num_recommendations)
        
        # Mettre à jour les recommandations en session
        if recommendations:
            session['recommendations'] = recommendations
        
        return jsonify(recommendations)
    
    except Exception as e:
        logging.error(f"Erreur API recommandations: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/analyze-library', methods=['GET'])
def analyze_library():
    """
    Endpoint API pour analyser la bibliothèque (genres, thèmes).
    """
    try:
        books = session.get('books', [])
        
        if not books:
            return jsonify({"error": "Aucun livre disponible."}), 400
        
        analysis = get_genre_analysis(books)
        
        return jsonify(analysis)
    
    except Exception as e:
        logging.error(f"Erreur API analyse: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/download-enhanced-pdf')
def download_enhanced_pdf():
    enhanced_pdf = session.get('enhanced_pdf', None)
    if enhanced_pdf and os.path.exists(enhanced_pdf):
        # Déterminer le nom du fichier
        filename = os.path.basename(enhanced_pdf)
        # Retourner le fichier pour téléchargement
        return send_file(enhanced_pdf, as_attachment=True, download_name=filename)
    else:
        flash('PDF amélioré non disponible', 'danger')
        return redirect(url_for('results'))

@app.route('/restore', methods=['GET', 'POST'])
def restore_page():
    """
    Page pour la restauration d'images et de documents
    """
    if request.method == 'GET':
        return render_template('restore.html')
    
    if 'file' not in request.files:
        flash('Aucun fichier sélectionné', 'danger')
        return redirect(url_for('restore_page'))
    
    file = request.files['file']
    if file.filename == '':
        flash('Aucun fichier sélectionné', 'danger')
        return redirect(url_for('restore_page'))
    
    if file and allowed_file(file.filename):
        try:
            # Créer un nom de fichier unique
            unique_filename = str(uuid.uuid4()) + os.path.splitext(secure_filename(file.filename))[1]
            file_ext = os.path.splitext(file.filename)[1].lower()
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(filepath)
            
            # Déterminer le type de fichier (image ou document)
            is_pdf = file_ext == '.pdf'
            
            if is_pdf:
                # Restaurer le document PDF
                try:
                    output_path = os.path.join(app.config['UPLOAD_FOLDER'], f"restored_{unique_filename}")
                    restored_doc = restore_document(filepath, output_path)
                    
                    if restored_doc:
                        session['restored_document'] = restored_doc
                        session['original_document'] = filepath
                        session['is_document'] = True
                        flash('Document restauré avec succès', 'success')
                    else:
                        flash('Impossible de restaurer le document', 'danger')
                except Exception as e:
                    logging.error(f"Erreur lors de la restauration du document: {str(e)}")
                    flash(f'Erreur lors de la restauration du document: {str(e)}', 'danger')
            else:
                # Restaurer l'image
                try:
                    output_path = os.path.join(app.config['UPLOAD_FOLDER'], f"restored_{unique_filename}")
                    restored = restore_image(filepath, output_path)
                    
                    if restored:
                        session['restored_image'] = output_path
                        session['original_image_path'] = filepath
                        session['is_document'] = False
                        flash('Image restaurée avec succès', 'success')
                    else:
                        flash('Impossible de restaurer l\'image', 'danger')
                except Exception as e:
                    logging.error(f"Erreur lors de la restauration de l'image: {str(e)}")
                    flash(f'Erreur lors de la restauration de l\'image: {str(e)}', 'danger')
            
            return redirect(url_for('restoration_results'))
        
        except Exception as e:
            logging.error(f"Erreur lors du traitement du fichier: {str(e)}")
            flash(f'Erreur lors du traitement du fichier: {str(e)}', 'danger')
            return redirect(url_for('restore_page'))
    else:
        flash('Type de fichier non autorisé. Veuillez télécharger une image (PNG, JPG, JPEG) ou un document PDF.', 'danger')
        return redirect(url_for('restore_page'))

@app.route('/restoration-results')
def restoration_results():
    """
    Affiche les résultats de la restauration
    """
    is_document = session.get('is_document', False)
    
    if is_document:
        # Pour les documents
        restored_document = session.get('restored_document', None)
        original_document = session.get('original_document', None)
        
        if not restored_document or not os.path.exists(restored_document):
            flash('Document restauré non disponible', 'danger')
            return redirect(url_for('restore_page'))
        
        return render_template('restoration_results.html', 
                              is_document=is_document,
                              restored_document=os.path.basename(restored_document),
                              original_document=os.path.basename(original_document))
    else:
        # Pour les images
        restored_image = session.get('restored_image', None)
        original_image_path = session.get('original_image_path', None)
        
        if not restored_image or not os.path.exists(restored_image):
            flash('Image restaurée non disponible', 'danger')
            return redirect(url_for('restore_page'))
        
        # Obtenez les noms des fichiers pour l'affichage
        restored_image_filename = os.path.basename(restored_image)
        original_image_filename = os.path.basename(original_image_path)
        
        return render_template('restoration_results.html',
                              is_document=is_document,
                              restored_image=restored_image_filename,
                              original_image=original_image_filename)

@app.route('/download-restored-document')
def download_restored_document():
    """
    Télécharge le document restauré
    """
    restored_document = session.get('restored_document', None)
    if restored_document and os.path.exists(restored_document):
        # Déterminer le nom du fichier
        filename = os.path.basename(restored_document)
        # Retourner le fichier pour téléchargement
        return send_file(restored_document, as_attachment=True, download_name=filename)
    else:
        flash('Document restauré non disponible', 'danger')
        return redirect(url_for('restoration_results'))

# Add error handlers
@app.errorhandler(413)
def too_large(e):
    flash('Fichier trop volumineux (max 16Mo)', 'danger')
    return redirect(url_for('index'))

@app.errorhandler(500)
def server_error(e):
    flash('Erreur serveur : ' + str(e), 'danger')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
