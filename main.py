import os
import requests
import json
from flask import Flask, request, jsonify
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips

app = Flask(__name__)

@app.route('/render', methods=['POST'])
def render_movie():
    # Отримуємо дані
    data = request.get_json(force=True)
    
    # Виправляємо проблему з форматом: якщо scenes прийшли як рядок, перетворюємо в список
    scenes = data.get('scenes', [])
    if isinstance(scenes, str):
        scenes = json.loads(scenes)
    
    movie_title = data.get('title', 'leo_story')
    
    if not os.path.exists('temp'): os.makedirs('temp')
    final_clips = []

    for i, scene in enumerate(scenes):
        # Код тепер вміє читати і "video_url", і цифру "2"
        v_url = scene.get('video_url', scene.get('2', ''))
        a_url = scene.get('audio_url', scene.get('3', ''))
        
        if not v_url or not a_url: continue
            
        v_url = v_url.replace('www.dropbox.com', 'dl.dropboxusercontent.com')
        a_url = a_url.replace('www.dropbox.com', 'dl.dropboxusercontent.com')
        
        v_path, a_path = f"temp/v_{i}.mp4", f"temp/a_{i}.mp3"
        
        # Завантажуємо шматочки
        with open(v_path, 'wb') as f: f.write(requests.get(v_url).content)
        with open(a_path, 'wb') as f: f.write(requests.get(a_url).content)
            
        video = VideoFileClip(v_path)
        audio = AudioFileClip(a_path)
        
        # Синхронізація
        clip = video.set_audio(audio).set_duration(audio.duration)
        final_clips.append(clip)

    if final_clips:
        final_video = concatenate_videoclips(final_clips, method="compose")
        output_name = f"{movie_title}.mp4"
        final_video.write_videofile(output_name, fps=24, codec="libx264")
        return jsonify({"status": "Success", "video": output_name})
    
    return jsonify({"status": "Error", "message": "No clips processed"}), 400

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
