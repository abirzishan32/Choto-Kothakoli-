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
import json
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import re


# Load environment variables
load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
model = genai.GenerativeModel('gemini-pro')

app = Flask(__name__)
# banglish_corrector = BanglishCorrector()

# Create a directory for storing contributions if it doesn't exist
CONTRIBUTIONS_DIR = Path('contributions')
CONTRIBUTIONS_DIR.mkdir(exist_ok=True)

# Available fonts for PDF
BENGALI_FONTS = {
    'kalpurush': {
        'name': 'Kalpurush',
        'file': 'kalpurush.ttf',
        'display': 'Kalpurush (কালপুরুষ)'
    },
    'nikosh': {
        'name': 'Nikosh',
        'file': 'nikosh.ttf',
        'display': 'Nikosh (নিকষ)'
    },
    'mitra': {
        'name': 'Mitra',
        'file': 'mitra.ttf',
        'display': 'Mitra (মিত্র)'
    },
    'solaimanlipi': {
        'name': 'MuktiNarrow',
        'file': 'muktinarrow.ttf',
        'display': 'Mukti Narrow (মুক্তি নার্দান)'
    }
}

# Analytics storage
class Analytics:
    def __init__(self):
        self.total_words_translated = 0
        self.total_documents = 0
        self.daily_translations = defaultdict(int)
        self.font_usage = defaultdict(int)
        self.contribution_count = 0
        self.most_common_words = defaultdict(int)
        self.avg_text_length = 0
        self._total_length = 0
        self.hourly_activity = defaultdict(int)
        self.translation_lengths = []
        self.success_rate = {'success': 0, 'failed': 0}
        self.user_sessions = defaultdict(int)
        # self.correction_stats = {'total_corrections': 0, 'correction_types': defaultdict(int)}

analytics = Analytics()

def update_analytics(bengali_text, banglish_text=None, font=None):
    """Update analytics data"""
    today = datetime.now().date()
    hour = datetime.now().hour
    
    # Update word counts
    bengali_words = len(re.findall(r'\S+', bengali_text))
    analytics.total_words_translated += bengali_words
    
    # Update document count
    analytics.total_documents += 1
    
    # Update daily translations
    analytics.daily_translations[today] += 1
    
    # Update font usage if provided
    if font:
        analytics.font_usage[font] += 1
    
    # Update average text length
    analytics._total_length += len(bengali_text)
    analytics.avg_text_length = analytics._total_length / analytics.total_documents
    
    # Update most common words (from Banglish text if available)
    if banglish_text:
        words = re.findall(r'\w+', banglish_text.lower())
        for word in words:
            analytics.most_common_words[word] += 1
    
    # Track hourly activity
    analytics.hourly_activity[hour] += 1
    
    # Track translation lengths
    analytics.translation_lengths.append(len(bengali_text))
    
    # Update success rate
    analytics.success_rate['success'] += 1

def save_contribution(banglish_text, bengali_text, feedback=None):
    """Save user contributions to help improve the model."""
    timestamp = datetime.now().isoformat()
    contribution = {
        'banglish': banglish_text,
        'bengali': bengali_text,
        'feedback': feedback,
        'timestamp': timestamp
    }
    
    # Save to a JSON file with timestamp in filename to avoid conflicts
    filename = CONTRIBUTIONS_DIR / f'contribution_{timestamp.replace(":", "-")}.json'
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(contribution, f, ensure_ascii=False, indent=2)

def enhance_prompt_with_contributions():
    """Update the conversion prompt with recent user contributions."""
    examples = []
    
    # Load recent contributions (limit to last 10 for performance)
    contribution_files = sorted(CONTRIBUTIONS_DIR.glob('*.json'), reverse=True)[:10]
    
    for file in contribution_files:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                contribution = json.load(f)
                example = f"- \"{contribution['banglish']}\" should be \"{contribution['bengali']}\""
                # Add feedback as context if available
                if contribution.get('feedback'):
                    example += f"\n  Context: {contribution['feedback']}"
                examples.append(example)
        except Exception as e:
            print(f"Error loading contribution {file}: {e}")
    
    return "\n".join(examples)

def convert_to_bengali(text):
    # First, correct any Banglish typing errors
    # corrected_text, corrections = banglish_corrector.correct_text(text)
    # suggestions = banglish_corrector.suggest_improvements(text)

    # If corrections were made, update analytics
    # if corrections:
    #     analytics.correction_stats['total_corrections'] += len(corrections)
    #     for correction in corrections:
    #         analytics.correction_stats['correction_types'][correction['type']] += 1

    prompt = f"""Convert the following Banglish text to proper Bengali (Bangla) text:
    Banglish: {text}
    
    Only provide the Bengali translation, nothing else. For example if the Banglish text is "tumi kemon acho" then the Bengali translation should be "তুমি কেমন আছো". If the Banglish text is "Ami valo achi" then the Bengali translation should be "আমি ভালো আছি".
    
    Recent user-contributed examples with context:
    {enhance_prompt_with_contributions()}
    
    Note: Pay attention to the context provided with examples to understand special cases,
    dialectal variations, and cultural nuances in the translations.
    
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
    return {
        'bengali_text': response.text.strip(),
        # 'corrections': corrections,
        # 'suggestions': suggestions,
        # 'corrected_banglish': corrected_text
    }

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

def create_pdf(bengali_text, title, caption, font_choice='kalpurush'):
    # Create a PDF buffer
    buffer = io.BytesIO()
    
    # Create the PDF object
    pdf = canvas.Canvas(buffer, pagesize=A4)
    
    # Register Bengali font
    font_info = BENGALI_FONTS.get(font_choice, BENGALI_FONTS['kalpurush'])
    bengali_font_path = f"static/fonts/{font_info['file']}"
    font_name = font_info['name']
    pdfmetrics.registerFont(TTFont(font_name, bengali_font_path))
    
    # Set font
    pdf.setFont(font_name, 16)
    
    # Add title
    pdf.drawString(50, 800, title)
    
    # Add caption
    pdf.setFont(font_name, 12)
    pdf.drawString(50, 770, caption)
    
    # Add main text
    pdf.setFont(font_name, 12)
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
    return render_template('index.html', fonts=BENGALI_FONTS)

@app.route('/convert', methods=['POST'])
def convert():
    data = request.get_json()
    banglish_text = data.get('text', '')
    
    try:
        result = convert_to_bengali(banglish_text)
        bengali_text = result['bengali_text']
        title, caption = generate_title_caption(bengali_text)
        
        update_analytics(bengali_text, banglish_text)
        
        return jsonify({
            'success': True, 
            'bengali_text': bengali_text,
            'title': title,
            'caption': caption,
            # 'corrections': result['corrections'],
            # 'suggestions': result['suggestions'],
            # 'corrected_banglish': result['corrected_banglish']
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
        font_choice = data.get('font', 'kalpurush')
        
        pdf_buffer = create_pdf(bengali_text, title, caption, font_choice)
        # Update font usage analytics
        analytics.font_usage[font_choice] += 1
        
        return send_file(
            pdf_buffer,
            download_name='bengali_text.pdf',
            as_attachment=True,
            mimetype='application/pdf'
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/contribute', methods=['POST'])
def contribute():
    try:
        data = request.get_json()
        banglish_text = data.get('banglish', '')
        bengali_text = data.get('bengali', '')
        feedback = data.get('feedback', '')
        
        if not banglish_text or not bengali_text:
            return jsonify({
                'success': False,
                'error': 'Both Banglish and Bengali texts are required'
            })
        
        save_contribution(banglish_text, bengali_text, feedback)
        # Update contribution count
        analytics.contribution_count += 1
        
        return jsonify({
            'success': True,
            'message': 'Thank you for your contribution!'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/view-contributions')
def view_contributions():
    contributions = []
    try:
        # Load all contributions, sorted by timestamp (newest first)
        contribution_files = sorted(CONTRIBUTIONS_DIR.glob('*.json'), reverse=True)
        
        for file in contribution_files:
            with open(file, 'r', encoding='utf-8') as f:
                contribution = json.load(f)
                # Add filename as ID
                contribution['id'] = file.stem
                contributions.append(contribution)
        
        return render_template('contributions.html', contributions=contributions)
    except Exception as e:
        return f"Error loading contributions: {str(e)}"

@app.route('/analytics')
def view_analytics():
    # Prepare analytics data
    data = {
        'total_words': analytics.total_words_translated,
        'total_documents': analytics.total_documents,
        'contributions': analytics.contribution_count,
        'avg_length': round(analytics.avg_text_length, 2),
        
        # Get daily translations for the last 7 days
        'daily_stats': {
            (datetime.now().date() - timedelta(days=i)): 
            analytics.daily_translations[datetime.now().date() - timedelta(days=i)]
            for i in range(7)
        },
        
        # Get top 10 most common words
        'common_words': dict(sorted(
            analytics.most_common_words.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:10]),
        
        # Get font usage statistics
        'font_usage': dict(analytics.font_usage),
        
        # Add new analytics
        'hourly_stats': dict(analytics.hourly_activity),
        'avg_translation_length': sum(analytics.translation_lengths) / len(analytics.translation_lengths) if analytics.translation_lengths else 0,
        'success_rate': (
            analytics.success_rate['success'] / 
            (analytics.success_rate['success'] + analytics.success_rate['failed'])
            * 100 if analytics.success_rate['success'] + analytics.success_rate['failed'] > 0 else 0
        ),
        'peak_hours': sorted(
            analytics.hourly_activity.items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]
    }
    
    return render_template('analytics.html', data=data)

@app.route('/analytics/data')
def get_analytics_data():
    days = int(request.args.get('days', 7))
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    
    # Filter data for the selected time period
    filtered_data = {
        'daily_stats': {
            date: analytics.daily_translations[date]
            for date in (start_date + timedelta(days=x) for x in range(days))
        },
        'total_words': sum(
            count for date, count in analytics.daily_translations.items()
            if start_date <= date <= end_date
        ),
        'total_documents': sum(
            1 for date in analytics.daily_translations.keys()
            if start_date <= date <= end_date
        ),
        'avg_length': analytics.avg_text_length
    }
    
    return jsonify({
        'daily_stats': {
            'keys': list(filtered_data['daily_stats'].keys()),
            'values': list(filtered_data['daily_stats'].values())
        },
        'total_words': filtered_data['total_words'],
        'total_documents': filtered_data['total_documents'],
        'avg_length': round(filtered_data['avg_length'], 2)
    })

if __name__ == '__main__':
    app.run(debug=True)
