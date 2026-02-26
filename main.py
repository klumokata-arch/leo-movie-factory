import os
import requests
import json
import threading
import dropbox
import shutil
import time
from flask import Flask, request, jsonify
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips
import moviepy.video.fx.all as vfx

app = Flask(__name__)
render_lock = threading.Lock()

def background_render(scenes, movie_title, dbx_token):
    with render_lock:
        try:
            output_name = f"{movie_title.replace(' ', '_')}.mp4"
            if os.path.exists('temp'): shutil.rmtree('temp')
            os.makedirs('temp')
            
            final_clips = []

            for i, scene in enumerate(scenes):
                time.sleep(0.5)
                
                v_url = scene.get('video_url', scene.get('2', '')).replace('www.dropbox.com', 'dl.dropboxusercontent.com')
                a_url = scene.get('audio_url', scene.get('3', '')).replace('www.dropbox.com', 'dl.dropboxusercontent.com')
                
                if not v_url or not a_url: continue
                    
                v_path, a_path = f"temp/v_{i}.mp4", f"temp/a_{i}.mp3"
                
                # Завантаження з тайм-аутом
                with open(v_path, 'wb') as f: f.write(requests.get(v_url, timeout=60).content)
                with open(a_path, 'wb') as f: f.write(requests.get(a_url, timeout=60).content)
                
                v_size = os.path.getsize(v_path)
                print(f"Scene {i}: video={v_size}b - processing...")
                
                if v_size < 10000: continue

                try:
                    video = VideoFileClip(v_path, audio=False)
                    audio = AudioFileClip(a_path)
                    
                    # 1. ПІДГОНКА ШВИДКОСТІ: відео під довжину аудіо
                    speed_factor = video.duration / audio.duration
                    video = video.fx(vfx.speedx, speed_factor)
                    
                    # 2. ФІКСАЦІЯ ТРИВАЛОСТІ: щоб уникнути мікро-обривів
                    video = video.set_duration(audio.duration)
                    
                    # 3. НАКЛАДАННЯ ЗВУКУ
                    clip = video.set_audio(audio)
                    
                    # 4. М'ЯКЕ ЗАТУХАННЯ: 0.1 сек в кінці кожної сцени прибирає "клацання"
                    clip = clip.audio_fadeout(0.1)
                    
                    final_clips.append(clip)
                    print(f"Scene {i}: OK - duration={audio.duration:.2f}s")
                    
                except Exception as e:
                    print(f"Scene {i}: ERROR - {str(e)}")
                    continue

            print(f"Total clips ready: {len(final_clips)}. Starting final render...")

            if final_clips:
                # method="compose" забезпечує стабільність при склейці різних джерел
                final_video = concatenate_videoclips(final_clips, method="compose")
                
                final_video.write_videofile(
                    output_name, 
                    fps=24, 
                    codec="libx264", 
                    audio_codec="aac",
                    preset="ultrafast", 
                    threads=2,
                    logger=None
                )
                
                print(f"Uploading to Dropbox...")
                dbx = dropbox.Dropbox(dbx_token)
                with open(output_name, "rb") as f:
                    dbx.files_upload(f.read(), f"/{output_name}", mode=dropbox.files.WriteMode.overwrite)
                
                # Очищення ресурсів
                final_video.close()
                for c in final_clips: c.close()
                
                os.remove(output_name)
                shutil.rmtree('temp')
                print(f"--- SUCCESS: {output_name} ---")
            else:
                print("ERROR: No clips successfully processed!")

        except Exception as e:
            print(f"FATAL ERROR DURING RENDER: {str(e)}")

@app.route('/render', methods=['POST'])
def render_movie():
    try:
        data = request.get_json(force=True)
        scenes = data.get('scenes', [])
        if isinstance(scenes, str): scenes = json.loads(scenes)
        
        token = os.environ.get('DROPBOX_ACCESS_TOKEN')
        if not token:
            return jsonify({"status": "error", "message": "Token missing"}), 500

        thread = threading.Thread(target=background_render, args=(
            scenes, data.get('title', 'movie'), token
        ))
        thread.start()
        
        return jsonify({"status": "Accepted"}), 202
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/')
def home():
    return "Movie Factory is Online!"

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
