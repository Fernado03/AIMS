from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from google.cloud import speech
from google.cloud import storage # New import
import os
import traceback
import sys
import uuid # New import
import sqlite3
from datetime import datetime
import vertexai # Added import
from vertexai.generative_models import GenerativeModel, Part # Added import

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = Flask(__name__, static_folder='.')
CORS(app)
speech_client = speech.SpeechClient()
storage_client = storage.Client() # New storage client
GCS_BUCKET_NAME = "audio-upload-bucket-fernado" # Updated GCS bucket name

# Vertex AI and Gemini Model Initialization
VERTEX_AI_PROJECT_ID = os.environ.get("VERTEX_AI_PROJECT_ID", "macro-dolphin-432908-t4")
VERTEX_AI_LOCATION = os.environ.get("VERTEX_AI_LOCATION", "us-central1")
gemini_model = None

try:
    vertexai.init(project=VERTEX_AI_PROJECT_ID, location=VERTEX_AI_LOCATION)
    gemini_model = GenerativeModel("gemini-2.5-pro-exp-03-25")
    print(f"Vertex AI initialized and Gemini model '{gemini_model._model_name}' loaded successfully in project '{VERTEX_AI_PROJECT_ID}' location '{VERTEX_AI_LOCATION}'.")
except Exception as e:
    print(f"⚠️ Error initializing Vertex AI or Gemini model: {e}\n{traceback.format_exc()}")
    gemini_model = None # Ensure model is None if initialization fails

# Database setup
DATABASE_NAME = 'notes_main.db' # Renamed to avoid conflict with any old db
DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), DATABASE_NAME)

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row # To access columns by name
    return conn

def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subjective_text TEXT,
                objective_text TEXT,
                assessment_text TEXT,
                plan_text TEXT,
                summary_text TEXT, -- Added for summary
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Check if updated_at trigger exists, if not, create it
        cursor.execute('''
            SELECT name FROM sqlite_master WHERE type='trigger' AND name='update_notes_updated_at';
        ''')
        if cursor.fetchone() is None:
            cursor.execute('''
                CREATE TRIGGER update_notes_updated_at
                AFTER UPDATE ON notes
                FOR EACH ROW
                BEGIN
                    UPDATE notes SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
                END;
            ''')
        conn.commit()
        print(f"Database '{DATABASE_NAME}' initialized successfully at {DATABASE_PATH}")
    except Exception as e:
        print(f"Error initializing database: {e}\n{traceback.format_exc()}")
    finally:
        if conn:
            conn.close()

@app.route('/')
def serve_index():
    return send_from_directory('../', 'index.html')

@app.route('/<path:path>')
def serve_file(path):
    return send_from_directory('../', path)

@app.route('/transcribe', methods=['POST'])
def transcribe():
    gcs_uri = None
    blob_name = None
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided."}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "Empty filename."}), 400

        # Generate a unique filename for GCS
        blob_name = f"audio_uploads/{uuid.uuid4()}-{file.filename}"
        
        # Upload to GCS
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(blob_name)
        
        # Rewind the file stream before uploading, just in case it was read before
        file.seek(0)
        blob.upload_from_file(file)
        
        gcs_uri = f"gs://{GCS_BUCKET_NAME}/{blob_name}"
        print(f"Uploaded audio to GCS: {gcs_uri}")

        audio = speech.RecognitionAudio(uri=gcs_uri)
        config = speech.RecognitionConfig(
            language_code="en-US",
            model="medical_conversation",
            enable_automatic_punctuation=True,
            audio_channel_count=2 # Specify audio channel count
        )
        
        # Use long_running_recognize for GCS files
        operation = speech_client.long_running_recognize(config=config, audio=audio)
        print("Waiting for long-running transcription operation to complete...")
        
        # Set a timeout for the operation (e.g., 10 minutes = 600 seconds)
        # Adjust timeout as needed based on expected audio length
        response = operation.result(timeout=600)
        
        transcript_text = "".join([result.alternatives[0].transcript + " " for result in response.results]).strip()
        print(f"📝 Google STT transcript for /transcribe (GCS): {transcript_text}")
        return jsonify({"text": transcript_text})

    except Exception as e:
        # Log the full traceback for better debugging
        print(f"Error during transcription: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Transcription error: {str(e)}"}), 500
    finally:
        # Clean up the GCS file
        if gcs_uri and blob_name:
            try:
                bucket = storage_client.bucket(GCS_BUCKET_NAME)
                blob = bucket.blob(blob_name)
                blob.delete()
                print(f"Deleted GCS file: {gcs_uri}")
            except Exception as e_del:
                print(f"Error deleting GCS file {gcs_uri}: {e_del}\n{traceback.format_exc()}")

@app.route('/create_note_session', methods=['POST'])
def create_note_session():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Insert a new note with default/NULL values for text fields
        cursor.execute("INSERT INTO notes (subjective_text, objective_text, assessment_text, plan_text, summary_text) VALUES (?, ?, ?, ?, ?)",
                       ("", "", "", "", "")) # Added summary_text
        conn.commit()
        new_note_id = cursor.lastrowid
        conn.close()
        print(f"✨ New note session created with ID: {new_note_id}")
        return jsonify({"message": "New note session created.", "note_id": new_note_id}), 201
    except Exception as e:
        return jsonify({"error": f"Failed to create note session: {e}\n{traceback.format_exc()}"}), 500

# Function to generate assessment using Gemini
def generate_assessment_from_notes(subjective_text, objective_text):
    if not gemini_model:
        print("⚠️ Gemini model not available. Skipping assessment generation.")
        return None

    kb_prompt_assessment_section = """## ASSESSMENT
---

### Diagnosis / Impression:
{Summarize the patient’s condition(s) as concluded from the subjective and objective data. Include both primary and secondary diagnoses.}

### Differential Diagnosis (DDx):
{If a definitive diagnosis is not established, list possible diagnoses in order of likelihood, with rationale for each.}"""

    prompt = f"""You are an AI medical assistant. Your task is to generate the ASSESSMENT section of a medical SOAP note.
Use the provided Subjective and Objective information to create a concise and clinically relevant Assessment.
The Assessment should strictly follow this format:
{kb_prompt_assessment_section}

SUBJECTIVE
---
{subjective_text}

OBJECTIVE
---
{objective_text}

Now, please generate *only* the ASSESSMENT section based on the above information and the guidelines provided.
Do not include "ASSESSMENT" heading in your response, start directly with "### Diagnosis / Impression:".
"""
    try:
        print(f"🧠 Generating assessment for S: '{subjective_text[:100]}...', O: '{objective_text[:100]}...'")
        response = gemini_model.generate_content(prompt)
        if response and response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            generated_text = response.candidates[0].content.parts[0].text.strip()
            print(f"✅ Gemini generated assessment: {generated_text[:200]}...")
            # Basic validation: check if it looks like an assessment
            if "Diagnosis / Impression:" in generated_text or "Differential Diagnosis (DDx):" in generated_text:
                return generated_text
            else:
                print(f"⚠️ Gemini response did not seem to contain a valid assessment structure: {generated_text[:200]}...")
                return None
        else:
            print(f"⚠️ Gemini response was empty or malformed: {response}")
            return None
    except Exception as e:
        print(f"🚨 Error calling Gemini API or processing response: {e}\n{traceback.format_exc()}")
        return None

# Function to generate plan using Gemini
def generate_plan_from_soap_notes(subjective_text, objective_text, assessment_text):
    global gemini_model # Ensure gemini_model is accessible
    if not gemini_model:
        print("⚠️ Gemini model not available for plan generation.")
        return None

    kb_prompt_prefix_plan = """You are an AI medical assistant. Based on the provided Subjective, Objective, and Assessment sections of a SOAP note, generate the PLAN section.
The PLAN section should include:
1. Diagnostics / Tests Ordered: List any additional diagnostic tests ordered and the rationale.
2. Medications / Therapy: Document any medications prescribed, changes to existing meds, or therapies initiated.
3. Referrals / Consults: Include any specialist referrals or consultations.
4. Patient Education & Counseling: Summarize education provided (diagnosis, treatment, medications, lifestyle).
5. Follow-Up Instructions: State when to return for follow-up, or instructions for earlier return if symptoms worsen.

Use the following format for the PLAN:
PLAN
---
### Diagnostics / Tests Ordered:
[Your generated diagnostics/tests here]

### Medications / Therapy:
[Your generated medications/therapy here]

### Referrals / Consults:
[Your generated referrals/consults here]

### Patient Education & Counseling:
[Your generated patient education/counseling here]

### Follow-Up Instructions:
[Your generated follow-up instructions here]

Here is the patient's information:
"""

    full_prompt = f"""{kb_prompt_prefix_plan}
SUBJECTIVE
---
{subjective_text}

OBJECTIVE
---
{objective_text}

ASSESSMENT
---
{assessment_text}

Now, please generate only the PLAN section based on ALL the above information (Subjective, Objective, and Assessment) and the guidelines provided.
"""
    try:
        print(f"🤖 Sending prompt to Gemini for PLAN generation (Note ID context)...")
        response = gemini_model.generate_content(full_prompt)
        generated_plan = ""
        if response.candidates and response.candidates[0].content.parts:
            generated_plan = response.candidates[0].content.parts[0].text.strip()
        
        # Basic check if the response seems like a plan
        if "PLAN" not in generated_plan.upper() and not any(kw in generated_plan.upper() for kw in ["DIAGNOSTICS", "MEDICATIONS", "THERAPY", "REFERRALS", "EDUCATION", "FOLLOW-UP"]):
            print(f"⚠️ Gemini response might not be a valid plan: {generated_plan[:200]}...")
        
        print(f"✅ Gemini generated plan (Note ID context): {generated_plan[:200]}...")
        return generated_plan
    except Exception as e:
        print(f"Error calling Gemini API for plan generation: {e}\\n{traceback.format_exc()}")
        return None

# Function to generate summary using Gemini
def generate_summary_from_soap_note(subjective_text, objective_text, assessment_text, plan_text):
    global gemini_model # Ensure gemini_model is accessible
    if not gemini_model:
        print("Gemini model not available for summary generation.")
        return None

    prompt = f"""You are an AI medical assistant. Based on the complete SOAP note provided below (Subjective, Objective, Assessment, and Plan), generate a concise clinical summary of the patient encounter.

SUBJECTIVE:
{subjective_text}

OBJECTIVE:
{objective_text}

ASSESSMENT:
{assessment_text}

PLAN:
{plan_text}

Now, please generate a concise clinical summary of this entire encounter.
"""
    try:
        print(f"🤖 Sending prompt to Gemini for SUMMARY generation...")
        response = gemini_model.generate_content(prompt)
        generated_summary = ""
        if response.candidates and response.candidates[0].content.parts:
            generated_summary = response.candidates[0].content.parts[0].text.strip()
        
        print(f"✅ Gemini generated summary: {generated_summary[:200]}...") # Log a snippet
        return generated_summary
    except Exception as e:
        print(f"Error calling Gemini API for summary generation: {e}\\n{traceback.format_exc()}")
        return None

def update_note_field(note_id, data_dict, field_map):
    conn = get_db_connection()
    cursor = conn.cursor()
    fields_to_update = []
    values_to_update = []
    for key, column_name in field_map.items():
        if key in data_dict:
            fields_to_update.append(f"{column_name} = ?")
            values_to_update.append(data_dict[key])
    
    if not fields_to_update:
        conn.close()
        return jsonify({"error": "No valid fields provided for update."}), 400

    values_to_update.append(note_id)
    sql = f"UPDATE notes SET {', '.join(fields_to_update)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
    
    try:
        cursor.execute(sql, tuple(values_to_update))
        conn.commit()
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({"error": "Note not found or no update made."}), 404
        print(f"💾 Note ID {note_id} updated. Fields: {', '.join(field_map.values())}")
        return jsonify({"message": f"Note ID {note_id} updated successfully."}), 200
    except Exception as e:
        return jsonify({"error": f"Database error updating note: {e}\n{traceback.format_exc()}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/update_note_subjective', methods=['POST'])
def update_subjective():
    data = request.get_json()
    note_id = data.get('note_id')
    if not note_id: return jsonify({"error": "Missing note_id."}), 400
    return update_note_field(note_id, data, {"subjective_text": "subjective_text"})

@app.route('/update_note_objective', methods=['POST'])
def update_objective():
    data = request.get_json()
    note_id = data.get('note_id')
    objective_text_to_save = data.get('objective_text')

    if not note_id:
        return jsonify({"error": "Missing note_id."}), 400
    if objective_text_to_save is None: # Check for None explicitly, empty string might be valid
        return jsonify({"error": "Missing objective_text."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE notes SET objective_text = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (objective_text_to_save, note_id))
        conn.commit()
        if cursor.rowcount == 0:
            print(f"⚠️ Objective update failed: Note ID {note_id} not found or no update made.")
            return jsonify({"error": "Note not found or no update made for objective text."}), 404
        print(f"💾 Objective text for Note ID {note_id} updated successfully.")
        return jsonify({"message": f"Objective text for Note ID {note_id} updated successfully."}), 200
    except Exception as e:
        print(f"🚨 Database error during objective update for Note ID {note_id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Database error: {e}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/generate_assessment/<int:note_id>', methods=['GET'])
def generate_assessment_api(note_id):
    conn = None  # Initialize conn to None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT subjective_text, objective_text FROM notes WHERE id = ?", (note_id,))
        note_data = cursor.fetchone()

        if not note_data:
            return jsonify({"error": "Note not found."}), 404

        subjective_text = note_data['subjective_text']
        objective_text = note_data['objective_text']

        if subjective_text is None or objective_text is None or subjective_text.strip() == "" or objective_text.strip() == "":
            print(f"ℹ️ Missing S or O data for Note ID {note_id} for on-demand assessment generation.")
            return jsonify({"error": "Could not generate assessment. Missing S/O data."}), 500

        print(f"🤖 Attempting to generate assessment on-demand for note ID {note_id}...")
        generated_assessment = generate_assessment_from_notes(subjective_text, objective_text)
        
        if generated_assessment:
            print(f"✅ On-demand assessment generated for Note ID {note_id}.")
            return jsonify({"assessment_text": generated_assessment}), 200
        else:
            print(f"⚠️ On-demand assessment generation failed for Note ID {note_id} (AI error or empty response).")
            return jsonify({"error": "Could not generate assessment. AI error."}), 500

    except Exception as e:
        print(f"🚨 Error in /api/generate_assessment/{note_id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Server error: {e}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/update_note_assessment', methods=['POST'])
def update_assessment():
    data = request.get_json()
    note_id = data.get('note_id')
    assessment_text_to_save = data.get('assessment_text')

    if not note_id:
        return jsonify({"error": "Missing note_id."}), 400
    if assessment_text_to_save is None: # Check for None explicitly
        return jsonify({"error": "Missing assessment_text."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Save the assessment text
        cursor.execute("UPDATE notes SET assessment_text = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (assessment_text_to_save, note_id))
        conn.commit()
        if cursor.rowcount == 0:
            print(f"⚠️ Assessment update failed: Note ID {note_id} not found or no update made.")
            return jsonify({"error": "Note not found or no update made for assessment text."}), 404
        print(f"💾 Assessment text for Note ID {note_id} updated successfully.")
        return jsonify({"message": f"Assessment text for Note ID {note_id} updated successfully."}), 200

    except Exception as e:
        print(f"🚨 Database error during assessment update for Note ID {note_id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Database error: {e}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/generate_plan/<int:note_id>', methods=['GET'])
def generate_plan_api(note_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT subjective_text, objective_text, assessment_text FROM notes WHERE id = ?", (note_id,))
        note_data = cursor.fetchone()

        if not note_data:
            return jsonify({"error": "Note not found."}), 404

        subjective_text = note_data['subjective_text']
        objective_text = note_data['objective_text']
        assessment_text = note_data['assessment_text']

        if not all([subjective_text, objective_text, assessment_text]):
            missing_fields = []
            if not subjective_text: missing_fields.append("Subjective")
            if not objective_text: missing_fields.append("Objective")
            if not assessment_text: missing_fields.append("Assessment")
            print(f"ℹ️ Missing data for Note ID {note_id} for on-demand plan generation. Missing: {', '.join(missing_fields)}")
            return jsonify({"error": f"Could not generate plan. Missing S/O/A data ({', '.join(missing_fields)} is missing or empty)."}), 500

        print(f"🤖 Attempting to generate plan on-demand for note ID {note_id}...")
        generated_plan_text = generate_plan_from_soap_notes(subjective_text, objective_text, assessment_text)
        
        if generated_plan_text is not None: # Check for None, as empty string could be a valid (though unlikely) plan
            print(f"✅ On-demand plan generated for Note ID {note_id}.")
            return jsonify({"plan_text": generated_plan_text}), 200
        else:
            print(f"⚠️ On-demand plan generation failed for Note ID {note_id} (AI error or empty response).")
            return jsonify({"error": "Could not generate plan. AI error or empty response."}), 500

    except Exception as e:
        print(f"🚨 Error in /api/generate_plan/{note_id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Server error: {e}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/update_note_plan', methods=['POST'])
def update_plan():
    data = request.get_json()
    note_id = data.get('note_id')
    plan_text_to_save = data.get('plan_text')

    if not note_id:
        return jsonify({"error": "Missing note_id."}), 400
    if plan_text_to_save is None: # Check for None explicitly
        return jsonify({"error": "Missing plan_text."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Save the plan text
        cursor.execute("UPDATE notes SET plan_text = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (plan_text_to_save, note_id))
        conn.commit()
        if cursor.rowcount == 0:
            print(f"⚠️ Plan update failed: Note ID {note_id} not found or no update made.")
            return jsonify({"error": "Note not found or no update made for plan text."}), 404
        print(f"💾 Plan text for Note ID {note_id} updated successfully.")
        return jsonify({"message": f"Plan text for Note ID {note_id} updated successfully."}), 200

    except Exception as e:
        print(f"🚨 Database error during plan update for Note ID {note_id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Database error: {e}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/generate_summary/<int:note_id>', methods=['GET'])
def generate_summary_api(note_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT subjective_text, objective_text, assessment_text, plan_text FROM notes WHERE id = ?", (note_id,))
        note_data = cursor.fetchone()

        if not note_data:
            return jsonify({"error": "Note not found."}), 404

        subjective_text = note_data['subjective_text']
        objective_text = note_data['objective_text']
        assessment_text = note_data['assessment_text']
        plan_text = note_data['plan_text']

        if not all([subjective_text, objective_text, assessment_text, plan_text]):
            missing_fields = []
            if not subjective_text: missing_fields.append("Subjective")
            if not objective_text: missing_fields.append("Objective")
            if not assessment_text: missing_fields.append("Assessment")
            if not plan_text: missing_fields.append("Plan")
            print(f"ℹ️ Missing data for Note ID {note_id} for on-demand summary generation. Missing: {', '.join(missing_fields)}")
            return jsonify({"error": f"Could not generate summary. Missing S/O/A/P data ({', '.join(missing_fields)} is missing or empty)."}), 500

        print(f"🤖 Attempting to generate summary on-demand for note ID {note_id}...")
        generated_summary_text = generate_summary_from_soap_note(subjective_text, objective_text, assessment_text, plan_text)
        
        if generated_summary_text is not None:
            print(f"✅ On-demand summary generated for Note ID {note_id}.")
            return jsonify({"summary_text": generated_summary_text}), 200
        else:
            print(f"⚠️ On-demand summary generation failed for Note ID {note_id} (AI error or empty response).")
            return jsonify({"error": "Could not generate summary. Missing S/O/A/P data or AI error."}), 500

    except Exception as e:
        print(f"🚨 Error in /api/generate_summary/{note_id}: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Server error: {e}"}), 500
    finally:
        if conn:
            conn.close()
@app.route('/get_note_data/<int:note_id>', methods=['GET'])
def get_note(note_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
        note = cursor.fetchone()
        conn.close()
        if note:
            return jsonify(dict(note))
        else:
            return jsonify({"error": "Note not found"}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to fetch note: {e}\n{traceback.format_exc()}"}), 500

if __name__ == '__main__':
    init_db()
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        print("⚠️ WARNING: GOOGLE_APPLICATION_CREDENTIALS environment variable not set.")
    app.run(debug=True, host='0.0.0.0', port=5000)