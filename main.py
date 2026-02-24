import os
import requests
from flask import Flask, request, jsonify
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, TextClip, CompositeVideoClip

app = Flask(__name__)

@app.route('/render', methods=['POST'])
def render_movie():
    data = request.json
    scenes = data.get('scenes', [])
    movie_title = data.get('title', 'fairy_tale')
    
    final_clips = []
    
    # Створюємо тимчасову папку
    if not os.path.exists('temp'):
        os.makedirs('temp')

    for i, scene in enumerate(scenes):
        v_url = scene['video_url']
        a_url = scene['audio_url']
        text = scene['narration']
        
        # Завантажуємо файли
        v_path = f"temp/v_{i}.mp4"
        a_path = f"temp/a_{i}.mp3"
        
        with open(v_path, 'wb') as f:
            f.write(requests.get(v_url).content)
        with open(a_path, 'wb') as f:
            f.write(requests.get(a_url).content)
            
        video = VideoFileClip(v_path)
        audio = AudioFileClip(a_path)
        
        # Синхронізація: якщо аудіо довше за відео
        if audio.duration > video.duration:
            # Робимо стоп-кадр останнього моменту відео до кінця звуку
            video = video.set_duration(audio.duration)
        
        video = video.set_audio(audio)
        
        # Додаємо субтитри (простий варіант)
        txt_clip = TextClip(text, fontsize=24, color='white', font='Arial', 
                           method='caption', size=(video.w*0.8, None)).set_duration(audio.duration)
        txt_clip = txt_clip.set_position(('center', 'bottom')).margin(bottom=50, opacity=0)
        
        result_scene = CompositeVideoClip([video, txt_clip])
        final_clips.append(result_scene)

    # Склеюємо все відео
    final_video = concatenate_videoclips(final_clips, method="compose")
    final_v_path = f"{movie_title}.mp4"
    final_video.write_videofile(final_v_path, fps=24, codec="libx264")
    
    # Тут можна додати завантаження на YouTube або видачу посилання
    return jsonify({"status": "completed", "video_url": "готові завантажити"})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
