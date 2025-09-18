# study_assistant.py
from flask import Flask, render_template_string, request, redirect
from werkzeug.utils import secure_filename
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from transformers import pipeline
import os
import time

# Initialize Flask app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'png', 'jpg', 'jpeg'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Windows-specific Tesseract path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# COMPLETE HTML TEMPLATES (no inheritance)
INDEX_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>College Study Assistant</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { padding: 20px; background-color: #f8f9fa; }
        .card { margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .summary-box { background-color: #e9ecef; padding: 15px; border-radius: 5px; }
        .navbar { margin-bottom: 20px; }
        pre { 
            white-space: pre-wrap; 
            background: #f8f9fa; 
            padding: 10px; 
            border-radius: 5px;
            font-family: inherit;
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container-fluid">
            <a class="navbar-brand" href="/">College Study Assistant</a>
        </div>
    </nav>
    <div class="container">
        <div class="card">
            <div class="card-body text-center">
                <h2>Upload Study Materials</h2>
                <p class="text-muted">Supports PDF and images (PNG, JPG)</p>
                <form method="POST" enctype="multipart/form-data" action="/upload">
                    <input class="form-control mb-3" type="file" name="file" required>
                    <button type="submit" class="btn btn-primary">Process File</button>
                </form>
            </div>
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

RESULTS_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>College Study Assistant</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { padding: 20px; background-color: #f8f9fa; }
        .card { margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .summary-box { background-color: #e9ecef; padding: 15px; border-radius: 5px; }
        .navbar { margin-bottom: 20px; }
        pre { 
            white-space: pre-wrap; 
            background: #f8f9fa; 
            padding: 10px; 
            border-radius: 5px;
            font-family: inherit;
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container-fluid">
            <a class="navbar-brand" href="/">College Study Assistant</a>
        </div>
    </nav>
    <div class="container">
        <div class="card">
            <div class="card-header bg-primary text-white">
                <h2>Study Summary</h2>
            </div>
            <div class="card-body">
                <div class="summary-box">
                    <pre>{{ summary }}</pre>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-header bg-primary text-white">
                <h2>Ask Questions</h2>
            </div>
            <div class="card-body">
                <form method="POST" action="/process_question/{{ session_id }}">
                    <div class="mb-3">
                        <input type="text" class="form-control" name="question" placeholder="Ask about your document..." required>
                    </div>
                    <button type="submit" class="btn btn-primary">Ask Question</button>
                </form>
                
                {% if question %}
                <div class="mt-4">
                    <h4>Q: {{ question }}</h4>
                    <div class="summary-box mt-2">
                        <strong>A:</strong> <pre>{{ answer }}</pre>
                    </div>
                </div>
                {% endif %}
            </div>
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def extract_text(filepath):
    try:
        if filepath.lower().endswith('.pdf'):
            text = ""
            with fitz.open(filepath) as doc:
                for page in doc:
                    text += page.get_text()
            return text
        else:  # Image
            return pytesseract.image_to_string(Image.open(filepath))
    except Exception as e:
        return f"Error extracting text: {str(e)}"

def generate_summary(text):
    try:
        summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
        chunks = [text[i:i+1000] for i in range(0, len(text), 1000)]
        summaries = []
        for chunk in chunks:
            summary = summarizer(chunk, max_length=130, min_length=30, do_sample=False)
            summaries.append(summary[0]['summary_text'])
        return " ".join(summaries)
    except Exception as e:
        return f"Error generating summary: {str(e)}\n\nFirst 500 characters:\n{text[:500]}"

def answer_question(text, question):
    try:
        qa_pipeline = pipeline("question-answering", model="distilbert-base-cased-distilled-squad")
        result = qa_pipeline(question=question, context=text[:5000])
        return result['answer']
    except Exception as e:
        return f"Error answering question: {str(e)}"

@app.route('/')
def index():
    return render_template_string(INDEX_PAGE)

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return redirect('/')
    
    file = request.files['file']
    if file.filename == '' or not allowed_file(file.filename):
        return redirect('/')
    
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        text = extract_text(filepath)
        summary = generate_summary(text)
        
        session_id = str(int(time.time()))
        session_file = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}.txt")
        with open(session_file, 'w', encoding='utf-8') as f:
            f.write(text)
        
        os.remove(filepath)
        return render_template_string(RESULTS_PAGE, summary=summary, session_id=session_id)
    except Exception as e:
        print(f"Upload error: {e}")
        return redirect('/')

@app.route('/process_question/<session_id>', methods=['POST'])
def process_question(session_id):
    try:
        session_file = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}.txt")
        if not os.path.exists(session_file):
            return redirect('/')
        
        with open(session_file, 'r', encoding='utf-8') as f:
            text = f.read()
        
        question = request.form['question']
        answer = answer_question(text, question)
        
        return render_template_string(
            RESULTS_PAGE,
            summary=generate_summary(text),
            question=question,
            answer=answer,
            session_id=session_id
        )
    except Exception as e:
        print(f"Question processing error: {e}")
        return redirect('/')

if __name__ == '__main__':
    app.run(debug=True, port=5000)