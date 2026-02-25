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
            
            v_path, a_path = f"temp/v_{i}.mp4", f"temp/a_{i}.mp3"
            with open(v_path, 'wb') as f: f.write(requests.get(v_url).content)
            with open(a_path, 'wb') as f: f.write(requests.get(a_url).content)
                
            video = VideoFileClip(v_path, audio=False)
            audio = AudioFileClip(a_path)
            
            # Ping-Pong ефект для плавності
            rev_video = video.fx(vfx.time_mirror)
            ping_pong = concatenate_videoclips([video, rev_video])
            video = ping_pong.fx(vfx.loop, duration=audio.duration)
            
            final_clips.append(video.set_audio(audio))

        if final_clips:
            final_video = concatenate_videoclips(final_clips, method="compose")
            final_video.write_videofile(output_name, fps=24, codec="libx264", preset="ultrafast")
            
            # ІНІЦІАЛІЗАЦІЯ DROPBOX З REFRESH TOKEN
            dbx = dropbox.Dropbox(
                oauth2_refresh_token=dbx_token,
                app_key=app_key,
                app_secret=app_secret
            )
            
            with open(output_name, "rb") as f:
                dbx.files_upload(f.read(), f"/{output_name}", mode=dropbox.files.WriteMode.overwrite)
            print(f"DONE: {output_name} uploaded to Dropbox")
            
    except Exception as e:
        print(f"FATAL ERROR: {str(e)}")

@app.route('/render', methods=['POST'])
def render_movie():
    data = request.get_json(force=True)
    scenes = data.get('scenes', [])
    if isinstance(scenes, str): scenes = json.loads(scenes)
    
    thread = threading.Thread(target=background_render, args=(
        scenes, 
        data.get('title', 'fairy_tale'), 
        os.environ.get('DROPBOX_ACCESS_TOKEN'),
        os.environ.get('DROPBOX_APP_KEY'),
        os.environ.get('DROPBOX_APP_SECRET')
    ))
    thread.start()

    return jsonify({"status": "Accepted"}), 202

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
