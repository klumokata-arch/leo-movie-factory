import os, requests, json
from flask import Flask, request, send_file, jsonify
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, vfx

app = Flask(__name__)

@app.route('/render', methods=['POST'])
def render_movie():
    try:
        data = request.get_json(force=True)
        scenes = data.get('scenes', [])
        if isinstance(scenes, str):
            scenes = json.loads(scenes)
        
        movie_title = data.get('title', 'final_movie').replace(" ", "_")
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
                
            video = VideoFileClip(v_path)
            audio = AudioFileClip(a_path)

            # --- ШЛЯХ 3: PING-PONG ЕФЕКТ ---
            # Створюємо зворотну версію кліпу
            reversed_video = video.fx(vfx.time_mirror)
            # Склеюємо: вперед + назад (отримуємо 10 сек плавного руху)
            ping_pong_base = concatenate_videoclips([video, reversed_video])
            
            # Зациклюємо цей пінг-понг, поки не закінчиться звук
            final_clip = ping_pong_base.fx(vfx.loop, duration=audio.duration)
            
            final_clips.append(final_clip.set_audio(audio))

        if final_clips:
            final_video = concatenate_videoclips(final_clips, method="compose")
            final_video.write_videofile(output_name, fps=24, codec="libx264")
            
            return send_file(output_name, as_attachment=True)
        
        return jsonify({"status": "Error", "message": "No clips processed"}), 400
    except Exception as e:
        return jsonify({"status": "Error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
