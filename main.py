import os, requests, json
from flask import Flask, request, send_file, jsonify
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips
from moviepy.video.fx.all import loop

app = Flask(__name__)

@app.route('/render', methods=['POST'])
def render_movie():
    try:
        data = request.get_json(force=True)
        scenes = data.get('scenes', [])
        if isinstance(scenes, str): scenes = json.loads(scenes)
        
        movie_title = data.get('title', 'fairy_tale').replace(" ", "_")
        output_name = f"{movie_title}.mp4"
        
        if not os.path.exists('temp'): os.makedirs('temp')
        final_clips = []

        for i, scene in enumerate(scenes):
            v_url = scene.get('video_url', scene.get('2', '')).replace('www.dropbox.com', 'dl.dropboxusercontent.com')
            a_url = scene.get('audio_url', scene.get('3', '')).replace('www.dropbox.com', 'dl.dropboxusercontent.com')
            
            if not v_url or not a_url: continue
                
            v_path, a_path = f"temp/v_{i}.mp4", f"temp/a_{i}.mp3"
            with open(v_path, 'wb') as f: f.write(requests.get(v_url).content)
            with open(a_path, 'wb') as f: f.write(requests.get(a_url).content)
                
            # Завантажуємо відео без звуку (це швидше і стабільніше)
            video = VideoFileClip(v_path, audio=False)
            audio = AudioFileClip(a_path)

            # ПРОСТЕ ЗАЦИКЛЕННЯ (Це працює швидко!)
            # Якщо відео 5 сек, а звук 10 - воно просто повториться 2 рази
            video = loop(video, duration=audio.duration)
            
            final_clips.append(video.set_audio(audio))

        if final_clips:
            # Склеюємо всі сцени
            final_video = concatenate_videoclips(final_clips, method="compose")
            # Використовуємо 'ultrafast' пресет, щоб не було таймаутів
            final_video.write_videofile(output_name, fps=24, codec="libx264", preset="ultrafast")
            
            return send_file(output_name, as_attachment=True)
        
        return jsonify({"status": "Error"}), 400
    except Exception as e:
        return jsonify({"status": "Error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
