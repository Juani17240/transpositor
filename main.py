from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import music21
from music21 import converter, transpose, stream, note, chord, interval
import subprocess
import os
import tempfile
import base64
from pathlib import Path

app = Flask(__name__)
CORS(app)

SEMITONE_MAP = {
    "C":  0,
    "Bb": -2,
    "Eb": 3,
    "F":  -5,
    "A":  -3,
}

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@app.route('/transpose', methods=['POST'])
def transpose_score():
    try:
        data = request.json
        file_b64  = data.get('file')
        file_type = data.get('fileType', 'xml')
        from_key  = data.get('fromKey', 'C')
        to_key    = data.get('toKey', 'Bb')
        semitones = data.get('semitones', None)

        # Decode file
        file_bytes = base64.b64decode(file_b64)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Save input file
            input_path = os.path.join(tmpdir, f"input.{file_type}")
            with open(input_path, 'wb') as f:
                f.write(file_bytes)

            # If image/PDF, run Audiveris first to get MusicXML
            if file_type in ['jpg', 'jpeg', 'png', 'webp', 'pdf']:
                xml_path = os.path.join(tmpdir, "output.mxl")
                result = subprocess.run([
                    'java', '-jar', '/app/audiveris.jar',
                    '-batch', '-export', '-output', tmpdir,
                    input_path
                ], capture_output=True, text=True, timeout=120)
                
                # Find exported mxl
                mxl_files = list(Path(tmpdir).glob("*.mxl"))
                if not mxl_files:
                    xml_files = list(Path(tmpdir).glob("*.xml"))
                    if not xml_files:
                        return jsonify({"error": "No se pudo reconocer la partitura. Asegurate de que la imagen sea clara."}), 400
                    input_path = str(xml_files[0])
                else:
                    input_path = str(mxl_files[0])

            # Load score with music21
            score = converter.parse(input_path)

            # Calculate semitones to transpose
            if semitones is not None:
                half_steps = int(semitones)
            else:
                from_offset = SEMITONE_MAP.get(from_key, 0)
                to_offset   = SEMITONE_MAP.get(to_key, 0)
                half_steps  = to_offset - from_offset

            if half_steps == 0:
                transposed = score
            else:
                transposed = score.transpose(half_steps)

            # Export to MusicXML
            xml_out = os.path.join(tmpdir, "transposed.xml")
            transposed.write('musicxml', fp=xml_out)

            # Render to PNG with MuseScore
            png_out = os.path.join(tmpdir, "transposed.png")
            mscore_result = subprocess.run([
                'mscore', '-o', png_out, xml_out
            ], capture_output=True, text=True, timeout=60)

            # Find generated PNG files (MuseScore adds page numbers)
            png_files = sorted(Path(tmpdir).glob("transposed*.png"))

            if not png_files:
                # Fallback: return MusicXML if PNG failed
                with open(xml_out, 'rb') as f:
                    xml_b64 = base64.b64encode(f.read()).decode()
                return jsonify({
                    "success": True,
                    "type": "xml",
                    "data": xml_b64,
                    "message": "Partitura transpuesta. Descargá el MusicXML para abrirlo en Sibelius."
                })

            # Encode all PNG pages to base64
            pages = []
            for png_file in png_files:
                with open(png_file, 'rb') as f:
                    pages.append(base64.b64encode(f.read()).decode())

            # Also include MusicXML for Sibelius import
            with open(xml_out, 'rb') as f:
                xml_b64 = base64.b64encode(f.read()).decode()

            return jsonify({
                "success": True,
                "type": "images",
                "pages": pages,
                "xml": xml_b64,
                "semitones": half_steps
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
