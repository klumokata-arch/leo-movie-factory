import os
import requests
from flask import Flask, request, jsonify
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips

app = Flask(__name__)

@app.route('/render', methods=['POST'])
def render_movie():
    data = request.json
    scenes = data.get('scenes', [])
    movie_title = data.get('title', 'leo_fairy_tale')
    
    if not os.path.exists('temp'): os.makedirs('temp')
    final_clips = []

    for i, scene in enumerate(scenes):
        v_url = scene['video_url'].replace('www.dropbox.com', 'dl.dropboxusercontent.com')
        a_url = scene['audio_url'].replace('www.dropbox.com', 'dl.dropboxusercontent.com')
        
        v_path, a_path = f"temp/v_{i}.mp4", f"temp/a_{i}.mp3"
        
        # Завантажуємо шматочки
        with open(v_path, 'wb') as f: f.write(requests.get(v_url).content)
        with open(a_path, 'wb') as f: f.write(requests.get(a_url).content)
            
        video = VideoFileClip(v_path)
        audio = AudioFileClip(a_path)
        
        # Синхронізація (відео стає довжиною як звук)
        clip = video.set_audio(audio).set_duration(audio.duration)
        final_clips.append(clip)

    # Збираємо фінальний файл
    final_video = concatenate_videoclips(final_clips, method="compose")
    output_name = f"{movie_title}.mp4"
    final_video.write_videofile(output_name, fps=24, codec="libx264")
    
    # ТУТ МОЖЕШ ДОДАТИ ЛОГІКУ ЗАВАНТАЖЕННЯ НА YOUTUBE
    
    return jsonify({"status": "Success", "message": f"Video {output_name} created!"})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
