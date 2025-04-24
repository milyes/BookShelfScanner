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
from book_recommender import generate_book_recommendations, get_genre_analysis, enrich_books_batch
from datetime import datetime
import csv
import io
from flask_sqlalchemy import SQLAlchemy

# Configurer le logging
logging.basicConfig(level=logging.DEBUG)

# Configure app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure la base de données
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Importer les modèles après la configuration
from models import db, Book, User, Library, LibraryBook, RestorationType, RestorationParameter, RestorationJob

# Initialiser la base de données
db.init_app(app)

# Créer les tables si elles n'existent pas
with app.app_context():
    db.create_all()

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
    
    # Vérifier si les livres ont déjà été enrichis
    enriched_books = session.get('enriched_books')
    if not enriched_books:
        try:
            # Enrichir jusqu'à 5 livres maximum pour éviter de surcharger l'API
            enriched_books = enrich_books_batch(books, max_books=5)
            session['enriched_books'] = enriched_books
            books = enriched_books  # Utiliser les livres enrichis pour l'affichage
        except Exception as e:
            logging.error(f"Erreur lors de l'enrichissement des livres: {str(e)}")
            # Continuer avec les livres non enrichis en cas d'erreur
    else:
        books = enriched_books  # Utiliser les livres enrichis déjà en session
    
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
        
@app.route('/export-csv')
def export_csv():
    """
    Exporte la liste des livres détectés au format CSV
    """
    books = session.get('books', [])
    
    if not books:
        flash('Aucun livre à exporter. Veuillez d\'abord analyser une bibliothèque.', 'warning')
        return redirect(url_for('index'))
    
    # Créer un buffer en mémoire pour le CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Écrire l'en-tête
    writer.writerow(['ID', 'Titre', 'Auteur', 'ISBN', 'Éditeur', 'Confiance'])
    
    # Écrire les données des livres
    for book in books:
        writer.writerow([
            book.get('id', ''),
            book.get('title', ''),
            book.get('author', ''),
            book.get('isbn', ''),
            book.get('publisher', ''),
            book.get('confidence', '')
        ])
    
    # Préparer la réponse
    output.seek(0)
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'bibliotheque_export_{now}.csv'
    )
    
@app.route('/export-pdf')
def export_pdf():
    """
    Génère un catalogue PDF de la bibliothèque
    """
    books = session.get('books', [])
    
    if not books:
        flash('Aucun livre à exporter. Veuillez d\'abord analyser une bibliothèque.', 'warning')
        return redirect(url_for('index'))
    
    try:
        # Créer un PDF temporaire
        from fpdf import FPDF
        
        pdf = FPDF()
        pdf.add_page()
        
        # Définir la police
        pdf.set_font('Arial', 'B', 16)
        
        # Titre
        pdf.cell(190, 10, 'Catalogue de votre bibliothèque', 0, 1, 'C')
        pdf.set_font('Arial', 'I', 10)
        pdf.cell(190, 10, f'Généré le {datetime.now().strftime("%d/%m/%Y à %H:%M")}', 0, 1, 'C')
        pdf.ln(10)
        
        # Contenu
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(190, 10, f'Nombre de livres: {len(books)}', 0, 1, 'L')
        pdf.ln(5)
        
        # En-tête du tableau
        pdf.set_fill_color(200, 220, 255)
        pdf.cell(10, 10, 'ID', 1, 0, 'C', 1)
        pdf.cell(80, 10, 'Titre', 1, 0, 'C', 1)
        pdf.cell(50, 10, 'Auteur', 1, 0, 'C', 1)
        pdf.cell(50, 10, 'ISBN/Éditeur', 1, 1, 'C', 1)
        
        # Contenu du tableau
        pdf.set_font('Arial', '', 10)
        for book in books:
            # Ajuster la hauteur de cellule en fonction de la longueur du titre
            title = book.get('title', 'Inconnu')
            title_height = max(10, len(title) // 25 * 6)  # 6pt par ligne, environ 25 caractères par ligne
            
            # Ajouter une nouvelle page si nécessaire
            if pdf.get_y() + title_height > 270:
                pdf.add_page()
                
                # Réafficher l'en-tête du tableau
                pdf.set_font('Arial', 'B', 12)
                pdf.set_fill_color(200, 220, 255)
                pdf.cell(10, 10, 'ID', 1, 0, 'C', 1)
                pdf.cell(80, 10, 'Titre', 1, 0, 'C', 1)
                pdf.cell(50, 10, 'Auteur', 1, 0, 'C', 1)
                pdf.cell(50, 10, 'ISBN/Éditeur', 1, 1, 'C', 1)
                pdf.set_font('Arial', '', 10)
            
            # Écrire les informations du livre
            pdf.cell(10, title_height, str(book.get('id', '')), 1, 0, 'C')
            pdf.multi_cell(80, title_height/2, title, 1, 'L')
            current_y = pdf.get_y()
            pdf.set_xy(pdf.get_x() + 90, current_y - title_height)
            pdf.cell(50, title_height, book.get('author', 'Inconnu'), 1, 0, 'L')
            
            isbn_publisher = f"ISBN: {book.get('isbn', 'N/A')}"
            if book.get('publisher', '') != 'Unknown Publisher':
                isbn_publisher += f"\nÉditeur: {book.get('publisher', '')}"
            
            pdf.multi_cell(50, title_height/2, isbn_publisher, 1, 'L')
        
        # Ajouter les infos d'analyse
        genre_analysis = session.get('genre_analysis', None)
        if genre_analysis:
            pdf.add_page()
            pdf.set_font('Arial', 'B', 14)
            pdf.cell(190, 10, 'Analyse de votre bibliothèque', 0, 1, 'L')
            pdf.ln(5)
            
            # Genres
            if genre_analysis.get('genres', []):
                pdf.set_font('Arial', 'B', 12)
                pdf.cell(190, 10, 'Genres principaux:', 0, 1, 'L')
                pdf.set_font('Arial', '', 10)
                
                for genre in genre_analysis.get('genres', []):
                    pdf.cell(190, 8, f"• {genre}", 0, 1, 'L')
                
                pdf.ln(5)
            
            # Thèmes
            if genre_analysis.get('themes', []):
                pdf.set_font('Arial', 'B', 12)
                pdf.cell(190, 10, 'Thèmes récurrents:', 0, 1, 'L')
                pdf.set_font('Arial', '', 10)
                
                for theme in genre_analysis.get('themes', []):
                    pdf.cell(190, 8, f"• {theme}", 0, 1, 'L')
                
                pdf.ln(5)
            
            # Analyse
            if genre_analysis.get('analysis', ''):
                pdf.set_font('Arial', 'B', 12)
                pdf.cell(190, 10, 'Analyse littéraire:', 0, 1, 'L')
                pdf.set_font('Arial', '', 10)
                
                analysis_text = genre_analysis.get('analysis', '')
                pdf.multi_cell(190, 6, analysis_text, 0, 'L')
        
        # Sauvegarder le PDF
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], f'catalogue_bibliotheque_{now}.pdf')
        pdf.output(pdf_path)
        
        # Retourner le fichier pour téléchargement
        return send_file(pdf_path, as_attachment=True, download_name=f'catalogue_bibliotheque_{now}.pdf')
    
    except Exception as e:
        logging.error(f"Erreur lors de la génération du PDF: {str(e)}")
        flash(f'Erreur lors de la génération du PDF: {str(e)}', 'danger')
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
