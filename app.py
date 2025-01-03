from flask import Flask, render_template, request, jsonify, send_file
import google.generativeai as genai
import os
from dotenv import load_dotenv
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
import arabic_reshaper
from bidi.algorithm import get_display
import io

# Load environment variables
load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.getenv('AIzaSyAqIxtRkwnfqJ3b2zLIShNf6fFylJjVJEM'))
model = genai.GenerativeModel('gemini-pro')

app = Flask(__name__)

def convert_to_bengali(text):
    prompt = f"""Convert the following Banglish text to proper Bengali (Bangla) text:
    Banglish: {text}
    
    Only provide the Bengali translation, nothing else. For example if the Banglish text is "tumi kemon acho" then the Bengali translation should be "তুমি কেমন আছো". If the Banglish text is "Ami valo achi" then the Bengali translation should be "আমি ভালো আছি".
    
    Vowels mapping:     
    "o" means "ও", "a" means "আ", "e" means "এ", "i" means "ই", "u" means "উ, "oi" means "ঐ", "ou" means "ঔ""
    Consonant mappings:
    "b" means "ব", "d" means "দ", "g" means "গ", "r" means "র", "k" means "ক", "sh" means "শ", "bh" means "ভ", "ch" means "ছ", "dh" means "ধ", "kh" means "খ", "ph" means "ফ"
    ,"sh" means "শ"
    ,"th" means "থ"
    ,"ng" means "ঙ"
    ,"gh" means "ঘ"
    ,"jh" means "ঝ"
    ,"rr" means "ঋ"
    ,"ny" means "ঞ".
    Retroflex and Aspirated Consonants:
    "T" means "ট",
    "Th" means "ঠ",
    "D" means "ড",
    "Dh" means "ঢ",
    "N" means "ণ".

    Special Clusters and Phonetics:
    "tr" means "ত্র"
    "dr" means "দ্র"
    "kr" means "ক্র"
    "gr" means "গ্র"
    "pr" means "প্র"
    "br" means "ব্র"
    "sr" means "স্র"
    "shri" means "শ্রী"
    "hr" means "হ্র"
    "jy" means "জ্ঞ"
    "gy" means "গ্য"
    "tw" means "ত্ব"
    "dv" means "দ্ব"

    Here are some examples for words:
    - "আমার" for "amar" 
    - "ইিত" for "iti"
    - "ঈগল" for "Igol" or "eegol" 
    - "কী" for "kI" 
    - "উজান" for "ujan" or "oojan" 
    - "বুঝি" for "bujhi" or "boojhi"
    - "ঊনচিল্লশ" for "Unocollish"
    - "দূর" for "dUr"
    - "ঋজু" for "rriju"
    - "গৃহ" for "grriho"
    - "এমন" for "emon"
    - "ঋজু" for "rriju"
    - "ঐরাবত" for "OIrabot" 
    - "কৈ" for kOI 
    - "ওতপ্রোত" for "OtoprOto"
    - "ঔপদেশিক" for "OUpodeshik"
    """
    
    response = model.generate_content(prompt)
    return response.text.strip()

def generate_title_caption(text):
    prompt = f"""Generate a creative title and caption in Bengali for the following Bengali text. 
    The title should be short (2-4 words) and catchy, while the caption should be a brief summary (15-20 words).
    
    Text: {text}
    
    Provide the output in this format:
    Title: <bengali_title>
    Caption: <bengali_caption>
    """
    
    response = model.generate_content(prompt)
    response.resolve()
    
    # Split the response into title and caption
    lines = response.text.strip().split('\n')
    title = lines[0].replace('Title:', '').strip()
    caption = lines[1].replace('Caption:', '').strip()
    
    return title, caption

def create_pdf(bengali_text, title, caption):
    # Create a PDF buffer
    buffer = io.BytesIO()
    
    # Create the PDF object
    pdf = canvas.Canvas(buffer, pagesize=A4)
    
    # Register Bengali font (you'll need to provide the path to a Bengali font file)
    bengali_font_path = "static/fonts/kalpurush.ttf"  # You'll need to add this font
    pdfmetrics.registerFont(TTFont('Kalpurush', bengali_font_path))
    
    # Set font
    pdf.setFont('Kalpurush', 16)
    
    # Add title
    pdf.drawString(50, 800, title)
    
    # Add caption
    pdf.setFont('Kalpurush', 12)
    pdf.drawString(50, 770, caption)
    
    # Add main text
    pdf.setFont('Kalpurush', 12)
    text_object = pdf.beginText(50, 700)
    
    # Wrap text to fit page width
    words = bengali_text.split()
    line = ""
    for word in words:
        if len(line + " " + word) < 80:  # Adjust number based on page width
            line += " " + word
        else:
            text_object.textLine(line.strip())
            line = word
    text_object.textLine(line.strip())
    
    pdf.drawText(text_object)
    pdf.save()
    
    buffer.seek(0)
    return buffer

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert():
    data = request.get_json()
    banglish_text = data.get('text', '')
    
    try:
        bengali_text = convert_to_bengali(banglish_text)
        title, caption = generate_title_caption(bengali_text)
        return jsonify({
            'success': True, 
            'bengali_text': bengali_text,
            'title': title,
            'caption': caption
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/export-pdf', methods=['POST'])
def export_pdf():
    try:
        data = request.get_json()
        bengali_text = data.get('text', '')
        title = data.get('title', '')
        caption = data.get('caption', '')
        
        pdf_buffer = create_pdf(bengali_text, title, caption)
        
        return send_file(
            pdf_buffer,
            download_name='bengali_text.pdf',
            as_attachment=True,
            mimetype='application/pdf'
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)
