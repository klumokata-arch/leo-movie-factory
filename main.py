import os, requests, json, threading, dropbox
from flask import Flask, request, jsonify
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips
import moviepy.video.fx.all as vfx

app = Flask(__name__)

def background_render(scenes, movie_title, dbx_token, app_key, app_secret):
    try:
        output_name = f"{movie_title.replace(' ', '_')}.mp4"
        if not os.path.exists('temp'): os.makedirs('temp')
        final_clips = []

        for i, scene in enumerate(scenes):
            v_url = scene.get('video_url', scene.get('2', '')).replace('www.dropbox.com', 'dl.dropboxusercontent.com')
            a_url = scene.get('audio_url', scene.get('3', '')).replace('www.dropbox.com', 'dl.dropboxusercontent.com')
            
            if not v_url or not a_url: continue
                
            v_path, a_path = f"temp/v_{i}.mp4", f"temp/a_{i}.mp3"
            with open(v_path, 'wb') as f: f.write(requests.get(v_url).content)
            with open(a_path, 'wb') as f: f.write(requests.get(a_url).content)
                
            # Завантажуємо відео БЕЗ звуку (це стабільніше)
            video = VideoFileClip(v_path, audio=False)
            audio = AudioFileClip(a_path)
            
            # ПРОСТЕ ЗАЦИКЛЕННЯ (Замість Ping-Pong)
            # Це працює миттєво і не видає помилку декодування
            speed_factor = video.duration / audio.duration
            video = video.fx(vfx.speedx, speed_factor)
            
            final_clips.append(video.set_audio(audio))

        if final_clips:
            final_video = concatenate_videoclips(final_clips, method="compose")
            # Використовуємо ultrafast для швидкості та уникнення таймаутів
            final_video.write_videofile(output_name, fps=24, codec="libx264", preset="ultrafast")
            
            # ✅ ВИПРАВЛЕНО: використовуємо ТІЛЬКИ access token
            print(f"Testing token before upload...")
            dbx = dropbox.Dropbox(dbx_token)  # Правильний виклик для Access Token!
            account = dbx.users_get_current_account()
            print(f"✅ Token OK: {account.name}")
            
            with open(output_name, "rb") as f:
                dbx.files_upload(f.read(), f"/{output_name}", mode=dropbox.files.WriteMode.overwrite)
            print(f"DONE: {output_name} uploaded to Dropbox")
            
            # Очищення тимчасових файлів
            os.remove(output_name)
            for i in range(len(scenes)):
                v_path = f"temp/v_{i}.mp4"
                a_path = f"temp/a_{i}.mp3"
                if os.path.exists(v_path): os.remove(v_path)
                if os.path.exists(a_path): os.remove(a_path)
                
    except Exception as e:
        print(f"FATAL ERROR: {str(e)}")

@app.route('/render', methods=['POST'])
def render_movie():
    data = request.get_json(force=True)
    scenes = data.get('scenes', [])
    if isinstance(scenes, str): scenes = json.loads(scenes)
    
    # 202 Accepted - миттєва відповідь для Make.com
    thread = threading.Thread(target=background_render, args=(
        scenes, 
        data.get('title', 'fairy_tale'), 
        os.environ.get('DROPBOX_ACCESS_TOKEN'),
        os.environ.get('DROPBOX_APP_KEY'),      # Залишаємо (ігноруємо в функції)
        os.environ.get('DROPBOX_APP_SECRET')    # Залишаємо (ігноруємо в функції)
    ))
    thread.start()
    return jsonify({"status": "Accepted"}), 202

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
