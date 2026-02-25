import os
import requests
import json
import threading
import dropbox
import shutil
from flask import Flask, request, jsonify
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips
import moviepy.video.fx.all as vfx

app = Flask(__name__)

# Функція рендеру (без змін логіки, тільки додано стабільність)
def background_render(scenes, movie_title, dbx_token):
    try:
        output_name = f"{movie_title.replace(' ', '_')}.mp4"
        if os.path.exists('temp'): shutil.rmtree('temp')
        os.makedirs('temp')

        final_clips = []
        for i, scene in enumerate(scenes):
            v_url = scene.get('video_url', scene.get('2', '')).replace('www.dropbox.com', 'dl.dropboxusercontent.com')
            a_url = scene.get('audio_url', scene.get('3', '')).replace('www.dropbox.com', 'dl.dropboxusercontent.com')
            
            if not v_url or not a_url: continue
                
            v_path, a_path = f"temp/v_{i}.mp4", f"temp/a_{i}.mp3"
            
            # Завантаження з тайм-аутом
            with open(v_path, 'wb') as f: f.write(requests.get(v_url, timeout=30).content)
            with open(a_path, 'wb') as f: f.write(requests.get(a_url, timeout=30).content)
            
            if os.path.getsize(v_path) < 500: continue

            video = VideoFileClip(v_path, audio=False)
            audio = AudioFileClip(a_path)
            
            speed_factor = video.duration / audio.duration
            video = video.fx(vfx.speedx, speed_factor)
            final_clips.append(video.set_audio(audio))

        if final_clips:
            final_video = concatenate_videoclips(final_clips, method="compose")
            final_video.write_videofile(output_name, fps=24, codec="libx264", preset="ultrafast")
            
            dbx = dropbox.Dropbox(dbx_token)
            with open(output_name, "rb") as f:
                dbx.files_upload(f.read(), f"/{output_name}", mode=dropbox.files.WriteMode.overwrite)
            
            os.remove(output_name)
            shutil.rmtree('temp')
            print(f"--- SUCCESS: {output_name} is in Dropbox ---")
    except Exception as e:
        print(f"ERROR DURING RENDER: {str(e)}")

@app.route('/render', methods=['POST'])
def render_movie():
    try:
        data = request.get_json(force=True)
        scenes = data.get('scenes', [])
        if isinstance(scenes, str): scenes = json.loads(scenes)
        
        token = os.environ.get('DROPBOX_ACCESS_TOKEN')
        if not token:
            print("CRITICAL: DROPBOX_ACCESS_TOKEN is not set in Railway!")
            return jsonify({"status": "error", "message": "Token missing"}), 500

        # Починаємо роботу в фоні
        thread = threading.Thread(target=background_render, args=(
            scenes, data.get('title', 'movie'), token
        ))
        thread.start()
        
        return jsonify({"status": "Accepted"}), 202
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

# Тестовий маршрут, щоб перевірити чи живе додаток
@app.route('/')
def home():
    return "Movie Factory is Online!"

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
