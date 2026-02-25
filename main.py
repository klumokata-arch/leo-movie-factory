import os
import requests
import json
import threading
import dropbox
import shutil
import subprocess
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
                v_url = scene.get('video_url', scene.get('2', '')).replace('www.dropbox.com', 'dl.dropboxusercontent.com')
                a_url = scene.get('audio_url', scene.get('3', '')).replace('www.dropbox.com', 'dl.dropboxusercontent.com')
                
                if not v_url or not a_url:
                    print(f"Scene {i}: SKIPPING - missing URL")
                    continue
                    
                v_path = f"temp/v_{i}.mp4"
                v_converted = f"temp/vc_{i}.mp4"
                a_path = f"temp/a_{i}.mp3"
                
                with open(v_path, 'wb') as f: f.write(requests.get(v_url, timeout=60).content)
                with open(a_path, 'wb') as f: f.write(requests.get(a_url, timeout=60).content)
                
                v_size = os.path.getsize(v_path)
                a_size = os.path.getsize(a_path)
                print(f"Scene {i}: video={v_size}b audio={a_size}b")
                
                if v_size < 10000:
                    print(f"Scene {i}: SKIPPING - video too small")
                    continue
                if a_size < 500:
                    print(f"Scene {i}: SKIPPING - audio too small")
                    continue

                # Конвертуємо в стандартний H.264
                subprocess.run(
                    ["ffmpeg", "-i", v_path, "-vcodec", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast", "-an", v_converted, "-y"],
                    capture_output=True
                )

                if os.path.exists(v_converted) and os.path.getsize(v_converted) > 10000:
                    print(f"Scene {i}: converted OK")
                    v_final = v_converted
                else:
                    print(f"Scene {i}: using original")
                    v_final = v_path

                try:
                    video = VideoFileClip(v_final, audio=False)
                    audio = AudioFileClip(a_path)
                    speed_factor = video.duration / audio.duration
                    video = video.fx(vfx.speedx, speed_factor)
                    final_clips.append(video.set_audio(audio))
                    print(f"Scene {i}: OK - duration={audio.duration:.1f}s")
                except Exception as e:
                    print(f"Scene {i}: ERROR - {str(e)}")
                    continue

            print(f"Total clips: {len(final_clips)}")

            if final_clips:
                final_video = concatenate_videoclips(final_clips, method="compose")
                final_video.write_videofile(output_name, fps=24, codec="libx264", preset="ultrafast")
                
                dbx = dropbox.Dropbox(dbx_token)
                with open(output_name, "rb") as f:
                    dbx.files_upload(f.read(), f"/{output_name}", mode=dropbox.files.WriteMode.overwrite)
                
                os.remove(output_name)
                shutil.rmtree('temp')
                print(f"--- SUCCESS: {output_name} ---")
            else:
                print("ERROR: No clips to render!")

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
