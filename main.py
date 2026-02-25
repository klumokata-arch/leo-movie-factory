import shutil

def background_render(scenes, movie_title, dbx_token, app_key, app_secret):
    try:
        output_name = f"{movie_title.replace(' ', '_')}.mp4"
        
        # 1. Очищення та перевірка місця на диску
        if os.path.exists('temp'): 
            shutil.rmtree('temp') # Видаляємо старе, щоб звільнити місце
        os.makedirs('temp')
        
        total, used, free = shutil.disk_usage("/")
        print(f"DEBUG DISK: Free space before start: {free // (2**20)} MB")

        final_clips = []

        for i, scene in enumerate(scenes):
            v_url = scene.get('video_url', scene.get('2', '')).replace('www.dropbox.com', 'dl.dropboxusercontent.com')
            a_url = scene.get('audio_url', scene.get('3', '')).replace('www.dropbox.com', 'dl.dropboxusercontent.com')
            
            if not v_url or not a_url: continue
                
            v_path, a_path = f"temp/v_{i}.mp4", f"temp/a_{i}.mp3"
            
            # 2. Завантаження з перевіркою статус-коду
            print(f"DEBUG: Downloading scene {i}...")
            
            v_res = requests.get(v_url, timeout=30)
            if v_res.status_code != 200:
                print(f"ERROR: Failed to download video {i}. Status: {v_res.status_code}")
                continue
            with open(v_path, 'wb') as f: f.write(v_res.content)
            
            a_res = requests.get(a_url, timeout=30)
            if a_res.status_code != 200:
                print(f"ERROR: Failed to download audio {i}. Status: {a_res.status_code}")
                continue
            with open(a_path, 'wb') as f: f.write(a_res.content)

            # 3. Перевірка розміру файлу (якщо файл порожній - MoviePy "впаде")
            v_size = os.path.getsize(v_path)
            print(f"DEBUG: Scene {i} video size: {v_size // 1024} KB")
            
            if v_size < 1000: # Менше 1 КБ - це явно помилка
                print(f"ERROR: Video file v_{i}.mp4 is too small or corrupted.")
                continue

            try:
                # 4. Спроба відкрити відео
                video = VideoFileClip(v_path, audio=False)
                audio = AudioFileClip(a_path)
                
                speed_factor = video.duration / audio.duration
                video = video.fx(vfx.speedx, speed_factor)
                
                final_clips.append(video.set_audio(audio))
                print(f"DEBUG: Scene {i} added successfully.")
                
            except Exception as clip_e:
                print(f"ERROR reading scene {i}: {str(clip_e)}")
                # Якщо один кліп битий, ми йдемо далі, щоб не падав увесь рендер
                continue

        if final_clips:
            print(f"DEBUG: Starting final render of {len(final_clips)} clips...")
            final_video = concatenate_videoclips(final_clips, method="compose")
            
            # Перевірка місця перед фінальним рендером
            _, _, free_now = shutil.disk_usage("/")
            print(f"DEBUG DISK: Free space before render: {free_now // (2**20)} MB")
            
            final_video.write_videofile(output_name, fps=24, codec="libx264", preset="ultrafast")
            
            print(f"DEBUG: Uploading to Dropbox...")
            dbx = dropbox.Dropbox(dbx_token)
            with open(output_name, "rb") as f:
                dbx.files_upload(f.read(), f"/{output_name}", mode=dropbox.files.WriteMode.overwrite)
            print(f"DONE: {output_name} uploaded")
            
            # Очищення
            os.remove(output_name)
            shutil.rmtree('temp')
        else:
            print("ERROR: No clips were successfully processed.")
                
    except Exception as e:
        print(f"FATAL ERROR IN RENDER THREAD: {str(e)}")
