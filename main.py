import os, requests, json
from flask import Flask, request, send_file, jsonify
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips
import moviepy.video.fx.all as vfx

app = Flask(__name__)

@app.route('/render', methods=['POST'])
def render_movie():
    try:
        data = request.get_json(force=True)
        scenes = data.get('scenes', [])
        if isinstance(scenes, str):
            scenes = json.loads(scenes)
        
        movie_title = data.get('title', 'final_movie').replace(" ", "_").replace("'", "")
        output_name = f"{movie_title}.mp4"
        
        temp_dir = 'temp'
        if not os.path.exists(temp_dir): os.makedirs(temp_dir)
        final_clips = []

        for i, scene in enumerate(scenes):
            v_url = scene.get('video_url', scene.get('2', '')).replace('www.dropbox.com', 'dl.dropboxusercontent.com')
            a_url = scene.get('audio_url', scene.get('3', '')).replace('www.dropbox.com', 'dl.dropboxusercontent.com')
            
            if not v_url or not a_url: continue
                
            v_path, a_path = os.path.join(temp_dir, f"v_{i}.mp4"), os.path.join(temp_dir, f"a_{i}.mp3")
            
            # Скачуємо з перевіркою статусу
            v_data = requests.get(v_url, timeout=30).content
            a_data = requests.get(a_url, timeout=30).content
            
            with open(v_path, 'wb') as f: f.write(v_data)
            with open(a_path, 'wb') as f: f.write(a_data)
                
            # Завантажуємо кліпи з явним зазначенням використання ffmpeg
            video = VideoFileClip(v_path, audio=False)
            audio = AudioFileClip(a_path)

            # Ping-Pong Ефект
            reversed_video = video.fx(vfx.time_mirror)
            ping_pong_base = concatenate_videoclips([video, reversed_video])
            
            # Зациклення під довжину звуку
            final_clip = ping_pong_base.fx(vfx.loop, duration=audio.duration)
            final_clips.append(final_clip.set_audio(audio))

        if final_clips:
            final_video = concatenate_videoclips(final_clips, method="compose")
            # Рендеримо у файл з максимальною сумісністю
            final_video.write_videofile(output_name, fps=24, codec="libx264", audio_codec="aac", temp_audiofile='temp-audio.m4a', remove_temp=True)
            
            return send_file(output_name, as_attachment=True)
        
        return jsonify({"status": "Error", "message": "No clips processed"}), 400
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return jsonify({"status": "Error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
