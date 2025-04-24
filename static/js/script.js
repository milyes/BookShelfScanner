document.addEventListener('DOMContentLoaded', function() {
    // File Upload Preview
    const fileInput = document.getElementById('fileInput');
    const uploadArea = document.querySelector('.upload-area');
    const previewContainer = document.getElementById('previewContainer');
    const imagePreview = document.getElementById('imagePreview');
    const uploadForm = document.getElementById('uploadForm');
    
    if (uploadArea) {
        uploadArea.addEventListener('click', function() {
            fileInput.click();
        });
    }
    
    if (fileInput) {
        fileInput.addEventListener('change', function() {
            if (fileInput.files.length > 0) {
                const file = fileInput.files[0];
                
                // Check if the file is an image
                if (!file.type.match('image.*')) {
                    alert('Please select an image file (JPG, PNG)');
                    return;
                }
                
                // Check file size (max 16MB)
                if (file.size > 16 * 1024 * 1024) {
                    alert('File is too large. Maximum size is 16MB.');
                    fileInput.value = '';
                    return;
                }
                
                // Show preview
                const reader = new FileReader();
                
                reader.onload = function(e) {
                    imagePreview.src = e.target.result;
                    previewContainer.classList.remove('d-none');
                }
                
                reader.readAsDataURL(file);
            }
        });
    }
    
    // Show loading overlay when form is submitted
    if (uploadForm) {
        uploadForm.addEventListener('submit', function() {
            // Create loading overlay
            const overlay = document.createElement('div');
            overlay.className = 'analyzing-overlay';
            
            const spinner = document.createElement('div');
            spinner.className = 'spinner-border text-primary loading-spinner';
            spinner.setAttribute('role', 'status');
            
            const spinnerText = document.createElement('span');
            spinnerText.className = 'visually-hidden';
            spinnerText.textContent = 'Loading...';
            
            const text = document.createElement('div');
            text.className = 'analyzing-text';
            text.textContent = 'Analyzing your bookshelf...';
            
            spinner.appendChild(spinnerText);
            overlay.appendChild(spinner);
            overlay.appendChild(text);
            
            document.body.appendChild(overlay);
        });
    }
    
    // Toggle between grid and list view
    const gridViewBtn = document.getElementById('gridViewBtn');
    const listViewBtn = document.getElementById('listViewBtn');
    const gridView = document.getElementById('gridView');
    const listView = document.getElementById('listView');
    
    if (gridViewBtn && listViewBtn) {
        gridViewBtn.addEventListener('click', function() {
            gridView.classList.remove('d-none');
            listView.classList.add('d-none');
            gridViewBtn.classList.add('active');
            listViewBtn.classList.remove('active');
        });
        
        listViewBtn.addEventListener('click', function() {
            gridView.classList.add('d-none');
            listView.classList.remove('d-none');
            gridViewBtn.classList.remove('active');
            listViewBtn.classList.add('active');
        });
    }
    
    // Export functions
    const exportCSV = document.getElementById('exportCSV');
    const exportJSON = document.getElementById('exportJSON');
    const printResults = document.getElementById('printResults');
    const refreshRecommendations = document.getElementById('refreshRecommendations');
    
    if (exportCSV) {
        exportCSV.addEventListener('click', function() {
            // Function to convert book data to CSV
            function convertToCSV(objArray) {
                const array = typeof objArray !== 'object' ? JSON.parse(objArray) : objArray;
                let str = 'ID,Title,Author,ISBN,Publisher,Confidence\r\n';
                
                for (let i = 0; i < array.length; i++) {
                    let line = '';
                    line += (array[i].id || '') + ',';
                    line += '"' + (array[i].title || '').replace(/"/g, '""') + '",';
                    line += '"' + (array[i].author || '').replace(/"/g, '""') + '",';
                    line += '"' + (array[i].isbn || '') + '",';
                    line += '"' + (array[i].publisher || '').replace(/"/g, '""') + '",';
                    line += '"' + (array[i].confidence || '') + '"';
                    str += line + '\r\n';
                }
                
                return str;
            }
            
            const csv = convertToCSV(booksData);
            const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
            const url = URL.createObjectURL(blob);
            
            const link = document.createElement('a');
            link.setAttribute('href', url);
            link.setAttribute('download', 'bookshelf_analysis.csv');
            link.style.visibility = 'hidden';
            
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        });
    }
    
    if (exportJSON) {
        exportJSON.addEventListener('click', function() {
            const json = JSON.stringify(booksData, null, 2);
            const blob = new Blob([json], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            
            const link = document.createElement('a');
            link.setAttribute('href', url);
            link.setAttribute('download', 'bookshelf_analysis.json');
            link.style.visibility = 'hidden';
            
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        });
    }
    
    if (printResults) {
        printResults.addEventListener('click', function() {
            window.print();
        });
    }
    
    // Fonctionnalité de rafraîchissement des recommandations
    if (refreshRecommendations) {
        refreshRecommendations.addEventListener('click', function() {
            // Afficher un indicateur de chargement
            const button = this;
            const originalText = button.innerHTML;
            button.disabled = true;
            button.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Chargement...';
            
            // Appeler l'API pour obtenir de nouvelles recommandations
            fetch('/get-recommendations', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    num_recommendations: 3
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Erreur lors de la récupération des recommandations');
                }
                return response.json();
            })
            .then(data => {
                // Recharger la page pour afficher les nouvelles recommandations
                // Dans le cas d'une application plus avancée, on pourrait mettre à jour dynamiquement le DOM
                // Mais pour simplifier, nous rechargeons la page entière
                sessionStorage.setItem('refreshedRecommendations', JSON.stringify(data));
                window.location.reload();
            })
            .catch(error => {
                console.error('Erreur:', error);
                alert('Erreur lors du rafraîchissement des recommandations. Veuillez réessayer.');
            })
            .finally(() => {
                // Réinitialiser le bouton
                button.disabled = false;
                button.innerHTML = originalText;
            });
        });
    }
    
    // Drag and drop functionality
    if (uploadArea && fileInput) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, preventDefaults, false);
        });
        
        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }
        
        ['dragenter', 'dragover'].forEach(eventName => {
            uploadArea.addEventListener(eventName, highlight, false);
        });
        
        ['dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, unhighlight, false);
        });
        
        function highlight() {
            uploadArea.classList.add('border-primary');
            uploadArea.style.backgroundColor = 'rgba(var(--bs-primary-rgb), 0.1)';
        }
        
        function unhighlight() {
            uploadArea.classList.remove('border-primary');
            uploadArea.style.backgroundColor = 'rgba(255, 255, 255, 0.05)';
        }
        
        uploadArea.addEventListener('drop', handleDrop, false);
        
        function handleDrop(e) {
            const dt = e.dataTransfer;
            const files = dt.files;
            
            if (files.length > 0) {
                fileInput.files = files;
                
                // Trigger change event
                const event = new Event('change', { bubbles: true });
                fileInput.dispatchEvent(event);
            }
        }
    }
});
