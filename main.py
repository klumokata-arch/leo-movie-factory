import os
import requests
import json
import threading
import dropbox
import shutil
import time
from flask import Flask, request, jsonify
from moviepy.editor import (VideoFileClip, AudioFileClip, 
                             concatenate_videoclips, concatenate_audioclips,
                             CompositeAudioClip)
import moviepy.video.fx.all as vfx

app = Flask(__name__)
render_lock = threading.Lock()

def build_music_track(music_segments, scene_durations):
    """
    Будує єдину музичну доріжку з кількох сегментів.
    Кожен сегмент грає безперервно на свій блок сцен.
    Між сегментами — плавний crossfade 2 секунди.
    """
    music_parts = []

    for idx, seg in enumerate(music_segments):
        from_s = seg['from_scene'] - 1  # індекс з 0
        to_s = seg['to_scene']

        block_duration = sum(scene_durations[from_s:to_s])
        if block_duration <= 0:
            continue

        try:
            music_path = f"temp/music_{from_s}_{to_s}.mp3"
            with open(music_path, 'wb') as f:
                f.write(requests.get(seg['url'], timeout=60).content)

            music_clip = AudioFileClip(music_path)

            # Зациклюємо якщо мелодія коротша за блок
            if music_clip.duration < block_duration:
                loops = int(block_duration / music_clip.duration) + 1
                music_clip = concatenate_audioclips([music_clip] * loops)

            # Обрізаємо точно під тривалість блоку
            music_clip = music_clip.subclip(0, block_duration)
            music_clip = music_clip.volumex(seg.get('volume', 0.15))

            # Плавний вхід тільки для першого сегменту
            if idx == 0:
                music_clip = music_clip.audio_fadein(1.5)

            # Плавний вихід тільки для останнього сегменту
            if idx == len(music_segments) - 1:
                music_clip = music_clip.audio_fadeout(2.0)

            music_parts.append(music_clip)
            print(f"Music segment {seg['from_scene']}-{seg['to_scene']}: {block_duration:.1f}s OK")

        except Exception as e:
            print(f"Music segment error ({seg['from_scene']}-{seg['to_scene']}): {str(e)}")
            continue

    if not music_parts:
        return None

    # Склеюємо всі частини в одну безперервну доріжку
    return concatenate_audioclips(music_parts)


def background_render(scenes, movie_title, dbx_token, music_segments=None):
    with render_lock:
        try:
            output_name = f"{movie_title.replace(' ', '_')}.mp4"
            if os.path.exists('temp'): shutil.rmtree('temp')
            os.makedirs('temp')
            
            final_clips = []
            scene_durations = []  # тривалість кожної сцени в секундах

            for i, scene in enumerate(scenes):
                time.sleep(0.5)
                
                v_url = scene.get('video_url', scene.get('2', '')).replace('www.dropbox.com', 'dl.dropboxusercontent.com')
                a_url = scene.get('audio_url', scene.get('3', '')).replace('www.dropbox.com', 'dl.dropboxusercontent.com')
                
                if not v_url or not a_url: continue
                    
                v_path, a_path = f"temp/v_{i}.mp4", f"temp/a_{i}.mp3"
                
                with open(v_path, 'wb') as f: f.write(requests.get(v_url, timeout=60).content)
                with open(a_path, 'wb') as f: f.write(requests.get(a_url, timeout=60).content)
                
                v_size = os.path.getsize(v_path)
                print(f"Scene {i+1}: video={v_size}b - processing...")
                
                if v_size < 10000: continue

                try:
                    video = VideoFileClip(v_path, audio=False)
                    audio = AudioFileClip(a_path)
                    
                    # 1. ПІДГОНКА ШВИДКОСТІ: відео під довжину аудіо
                    speed_factor = video.duration / audio.duration
                    video = video.fx(vfx.speedx, speed_factor)
                    
                    # 2. ФІКСАЦІЯ ТРИВАЛОСТІ
                    video = video.set_duration(audio.duration)
                    
                    # 3. НАКЛАДАННЯ ЗВУКУ
                    clip = video.set_audio(audio)
                    
                    # 4. М'ЯКЕ ЗАТУХАННЯ
                    clip = clip.audio_fadeout(0.1)
                    
                    scene_durations.append(audio.duration)  # зберігаємо тривалість
                    final_clips.append(clip)
                    print(f"Scene {i+1}: OK - duration={audio.duration:.2f}s")
                    
                except Exception as e:
                    print(f"Scene {i+1}: ERROR - {str(e)}")
                    scene_durations.append(0)
                    continue

            print(f"Total clips ready: {len(final_clips)}. Starting final render...")

            if final_clips:
                final_video = concatenate_videoclips(final_clips, method="compose")

                # ====== ФОНОВА МУЗИКА ======
                if music_segments:
                    try:
                        print("Building music track...")
                        music_track = build_music_track(music_segments, scene_durations)

                        if music_track:
                            # Підганяємо під точну довжину відео
                            if music_track.duration > final_video.duration:
                                music_track = music_track.subclip(0, final_video.duration)

                            # Міксуємо голос + музику
                            original_audio = final_video.audio
                            mixed_audio = CompositeAudioClip([original_audio, music_track])
                            final_video = final_video.set_audio(mixed_audio)
                            print("Music mixed successfully!")
                    except Exception as e:
                        print(f"Music error (continuing without music): {str(e)}")
                # ===========================
                
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
            scenes,
            data.get('title', 'movie'),
            token,
            data.get('music_segments')  # ← нове поле з Make.com
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
