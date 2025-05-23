from flask import Flask, request, send_file
from spleeter.separator import Separator
import os
import uuid
import traceback
from io import BytesIO
import zipfile

# --------------------------------------------------
# Configuración de rutas absolutas
# --------------------------------------------------
BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER  = os.path.join(BASE_DIR, 'uploads')
RESULT_FOLDER  = os.path.join(BASE_DIR, 'results')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

app = Flask(__name__)

# --------------------------------------------------
# Página de bienvenida / formulario
# --------------------------------------------------
@app.route('/')
def index():
    return '''
        <!DOCTYPE html>
        <html lang="es">
        <head>
        <meta charset="UTF-8" />
        <title>Removedor-MusicIAn</title>
        </head>
        <body>
        <h1>Removedor</h1>
        <h2>Separa la voz y el instrumental.</h2>
        <form method="post" action="/separate" enctype="multipart/form-data">
            <input type="file" name="audio" accept="audio/*">
            <input type="submit" value="Separar audio">
        </form>
        <h1>MusicIAn</h1>
        <p> © 2025 MusicIAn - Todos los derechos reservados.</p>
        </body>
        </html>
    '''

# --------------------------------------------------
# Endpoint de separación
# --------------------------------------------------
@app.route('/separate', methods=['POST'])
def separate_audio():
    try:
        # 1) Guardar el archivo subido
        file = request.files['audio']
        original_name = os.path.splitext(file.filename)[0].replace(' ', '_')
        extension     = os.path.splitext(file.filename)[1]
        unique_id     = uuid.uuid4().hex[:8]
        saved_filename = f"{original_name}_{unique_id}{extension}"
        input_path     = os.path.join(UPLOAD_FOLDER, saved_filename)
        file.save(input_path)

        app.logger.info(f"Archivo guardado en: {input_path}")

        # 2) Separar audio en 2 stems (vocals + accompaniment)
        separator = Separator('spleeter:2stems')
        # Forzamos formato para que salga en carpeta: {filename}/vocals.wav y accompaniment.wav
        separator.separate_to_file(
            input_path,
            RESULT_FOLDER,
            filename_format='{filename}/{instrument}.{codec}'
        )
        app.logger.info("Separación finalizada.")

        # 3) Construir rutas a los stems
        output_dir         = os.path.join(RESULT_FOLDER, f"{original_name}_{unique_id}")
        vocals_path        = os.path.join(output_dir, 'vocals.wav')
        accompaniment_path = os.path.join(output_dir, 'accompaniment.wav')

        # 4) Verificar que existen ambos archivos
        missing = []
        for p in (vocals_path, accompaniment_path):
            if not os.path.exists(p):
                missing.append(p)
        if missing:
            app.logger.error("No se encontraron todos los stems:")
            for m in missing:
                app.logger.error(f"  -> {m}")
            return "[ERROR] No se generaron correctamente los stems.", 404

        # 5) Empaquetar ambos stems en un ZIP en memoria
        mem_zip = BytesIO()
        with zipfile.ZipFile(mem_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(vocals_path,        arcname=original_name+'(VOZ).wav')
            zf.write(accompaniment_path, arcname=original_name+'(instrumental).wav')
        mem_zip.seek(0)

        # 6) Devolver el ZIP al cliente
        zip_name = f"{original_name}_{unique_id}.zip"
        return send_file(
            mem_zip,
            mimetype='application/zip',
            as_attachment=True,
            download_name=zip_name
        )

    except Exception as e:
        app.logger.error("Ocurrió una excepción durante la separación:")
        traceback.print_exc()
        return f"[FATAL ERROR] {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True)