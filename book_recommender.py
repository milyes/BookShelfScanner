import os
import json
import logging
import random
from openai import OpenAI

# Configurer le logging
logging.basicConfig(level=logging.DEBUG)

# Initialiser le client OpenAI avec la clé API
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
openai = OpenAI(api_key=OPENAI_API_KEY)

def generate_book_recommendations(books, num_recommendations=5, include_reasons=True):
    """
    Génère des recommandations de livres basées sur les livres détectés dans la bibliothèque
    en utilisant l'API OpenAI.
    
    Args:
        books: Liste des livres détectés avec leurs informations (titre, auteur, etc.)
        num_recommendations: Nombre de recommandations à générer (défaut: 5)
        include_reasons: Si True, inclut les raisons des recommandations
    
    Returns:
        Liste des recommandations de livres
    """
    try:
        if not books or len(books) == 0:
            logging.warning("Aucun livre fourni pour générer des recommandations.")
            return []
        
        # Créer une liste des titres et auteurs pour le contexte
        book_context = []
        for book in books:
            title = book.get('title', '').strip()
            author = book.get('author', '').strip()
            
            if title and title != 'Unknown Title' and author and author != 'Unknown Author':
                book_context.append(f"'{title}' par {author}")
            elif title and title != 'Unknown Title':
                book_context.append(f"'{title}'")
        
        if not book_context:
            logging.warning("Aucun livre valide pour générer des recommandations.")
            return []
        
        # Construire le prompt pour l'API OpenAI
        prompt = f"""
En tant qu'expert en littérature, j'ai besoin de recommandations de livres basées sur ma bibliothèque actuelle.

Ma bibliothèque contient les livres suivants:
{', '.join(book_context)}

Veuillez me recommander {num_recommendations} livres que je pourrais apprécier en fonction des thèmes, styles ou auteurs que je semble déjà aimer.
{"Pour chaque recommandation, expliquez brièvement pourquoi vous pensez que je pourrais aimer ce livre." if include_reasons else ""}

Répondez au format JSON avec cette structure:
```json
[
  {{
    "title": "Titre du livre",
    "author": "Nom de l'auteur",
    "description": "Brève description du livre",
    "reason": "Pourquoi vous recommandez ce livre en fonction de ma bibliothèque"
  }},
  ...
]
```
"""
        
        # Appeler l'API OpenAI pour générer des recommandations
        # le modèle "gpt-4o" a été libéré le 13 mai 2024 après votre cutoff
        response = openai.chat.completions.create(
            model="gpt-4o",  # ne pas modifier sans demande expresse de l'utilisateur
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=1000
        )
        
        # Extraire et parser la réponse JSON
        content = response.choices[0].message.content
        recommendations = json.loads(content)
        
        # Assurer que la réponse est une liste
        if isinstance(recommendations, dict) and 'recommendations' in recommendations:
            recommendations = recommendations['recommendations']
        
        logging.info(f"Générées {len(recommendations)} recommandations de livres.")
        return recommendations
    
    except Exception as e:
        logging.error(f"Erreur lors de la génération des recommandations: {str(e)}")
        return []

def get_genre_analysis(books):
    """
    Analyse les genres et thèmes des livres dans la bibliothèque.
    
    Args:
        books: Liste des livres détectés
    
    Returns:
        Analyse des genres et thèmes
    """
    try:
        if not books or len(books) == 0:
            return {"genres": [], "themes": [], "analysis": "Pas assez de livres pour l'analyse."}
        
        # Créer une liste des titres et auteurs pour le contexte
        book_context = []
        for book in books:
            title = book.get('title', '').strip()
            author = book.get('author', '').strip()
            
            if title and title != 'Unknown Title' and author and author != 'Unknown Author':
                book_context.append(f"'{title}' par {author}")
            elif title and title != 'Unknown Title':
                book_context.append(f"'{title}'")
        
        if not book_context:
            return {"genres": [], "themes": [], "analysis": "Données insuffisantes pour l'analyse."}
        
        # Construire le prompt pour l'API OpenAI
        prompt = f"""
Analyser les genres, thèmes et tendances littéraires de cette bibliothèque:
{', '.join(book_context)}

Fournir une analyse structurée comprenant:
1. Les 3-5 genres dominants
2. Les 3-5 thèmes ou sujets principaux
3. Une brève analyse (2-3 phrases) du profil littéraire du propriétaire

Répondre uniquement au format JSON avec cette structure:
```json
{{
  "genres": ["genre1", "genre2", "genre3"],
  "themes": ["thème1", "thème2", "thème3"],
  "analysis": "Brève analyse du profil littéraire"
}}
```
"""
        
        # Appeler l'API OpenAI
        response = openai.chat.completions.create(
            model="gpt-4o",  # ne pas modifier sans demande expresse de l'utilisateur
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.5,
            max_tokens=500
        )
        
        # Extraire et parser la réponse JSON
        content = response.choices[0].message.content
        analysis = json.loads(content)
        
        return analysis
    
    except Exception as e:
        logging.error(f"Erreur lors de l'analyse des genres: {str(e)}")
        return {"genres": [], "themes": [], "analysis": f"Erreur d'analyse: {str(e)}"}

def generate_book_details(book):
    """
    Génère une description détaillée d'un livre en utilisant l'API OpenAI.
    
    Args:
        book: Dictionnaire contenant les informations du livre (titre, auteur, etc.)
    
    Returns:
        Dictionnaire avec les informations enrichies (description, genre, etc.)
    """
    try:
        title = book.get('title', '').strip()
        author = book.get('author', '').strip()
        
        if (not title or title == 'Unknown Title') and (not author or author == 'Unknown Author'):
            return book
        
        # Créer un contexte pour le livre
        book_context = ""
        if title and title != 'Unknown Title':
            book_context += f"Titre: {title}\n"
        if author and author != 'Unknown Author':
            book_context += f"Auteur: {author}\n"
        if book.get('publisher', '') and book.get('publisher', '') != 'Unknown Publisher':
            book_context += f"Éditeur: {book.get('publisher', '')}\n"
        if book.get('isbn', ''):
            book_context += f"ISBN: {book.get('isbn', '')}\n"
        
        # Construire le prompt pour l'API OpenAI
        prompt = f"""
En tant qu'expert en littérature, veuillez enrichir les informations de ce livre:

{book_context}

Fournir les informations suivantes:
1. Une description concise (2-3 phrases) du livre
2. Le genre principal du livre
3. L'année de publication (approximative si non connue)
4. Une liste de 2-3 thèmes abordés
5. Public cible probable

Répondre uniquement au format JSON avec cette structure:
```json
{{
  "description": "Description du livre...",
  "genre": "Genre principal",
  "publication_year": "Année de publication (nombre entier)",
  "themes": ["thème1", "thème2", "thème3"],
  "audience": "Public cible (ex: adultes, jeunes adultes, enfants)"
}}
```
"""
        
        # Appeler l'API OpenAI
        response = openai.chat.completions.create(
            model="gpt-4o",  # ne pas modifier sans demande expresse de l'utilisateur
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=500
        )
        
        # Extraire et parser la réponse JSON
        content = response.choices[0].message.content
        details = json.loads(content)
        
        # Mettre à jour les informations du livre
        book.update(details)
        
        logging.info(f"Détails enrichis générés pour '{title}'")
        return book
    
    except Exception as e:
        logging.error(f"Erreur lors de la génération des détails du livre: {str(e)}")
        return book

def enrich_books_batch(books, max_books=None):
    """
    Enrichit les informations pour un lot de livres.
    
    Args:
        books: Liste des livres à enrichir
        max_books: Nombre maximum de livres à traiter (par défaut tous)
    
    Returns:
        Liste des livres avec informations enrichies
    """
    if not books:
        return []
    
    # Limiter le nombre de livres si spécifié
    if max_books and max_books < len(books):
        # Sélectionner aléatoirement un sous-ensemble de livres
        selected_books = random.sample(books, max_books)
    else:
        selected_books = books
    
    enriched_books = []
    for book in selected_books:
        try:
            enriched_book = generate_book_details(book)
            enriched_books.append(enriched_book)
        except Exception as e:
            logging.error(f"Erreur lors de l'enrichissement du livre {book.get('title', 'Unknown')}: {str(e)}")
            enriched_books.append(book)
    
    return enriched_books