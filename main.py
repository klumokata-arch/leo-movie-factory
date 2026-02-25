import os, requests, json, threading, dropbox
from flask import Flask, request, jsonify
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips
from moviepy.video.fx.all import loop

app = Flask(__name__)

def background_render(scenes, movie_title, dbx_token):
    try:
        if not os.path.exists('temp'): os.makedirs('temp')
        final_clips = []
        output_name = f"{movie_title.replace(' ', '_')}.mp4"

        for i, scene in enumerate(scenes):
            v_url = scene.get('video_url', scene.get('2', '')).replace('www.dropbox.com', 'dl.dropboxusercontent.com')
            a_url = scene.get('audio_url', scene.get('3', '')).replace('www.dropbox.com', 'dl.dropboxusercontent.com')
            
            v_path, a_path = f"temp/v_{i}.mp4", f"temp/a_{i}.mp3"
            with open(v_path, 'wb') as f: f.write(requests.get(v_url).content)
            with open(a_path, 'wb') as f: f.write(requests.get(a_url).content)
                
            video = VideoFileClip(v_path, audio=False)
            audio = AudioFileClip(a_path)
            # Швидке зациклення
            video = loop(video, duration=audio.duration)
            final_clips.append(video.set_audio(audio))

        if final_clips:
            final_video = concatenate_videoclips(final_clips, method="compose")
            final_video.write_videofile(output_name, fps=24, codec="libx264", preset="ultrafast")
            
            # Завантаження в Dropbox
            dbx = dropbox.Dropbox(dbx_token)
            with open(output_name, "rb") as f:
                dbx.files_upload(f.read(), f"/{output_name}", mode=dropbox.files.WriteMode.overwrite)
            print(f"DONE: {output_name} uploaded to Dropbox")
            
    except Exception as e:
        print(f"ERROR: {str(e)}")

@app.route('/render', methods=['POST'])
def render_movie():
    data = request.get_json(force=True)
    scenes = data.get('scenes', [])
    if isinstance(scenes, str): scenes = json.loads(scenes)
    title = data.get('title', 'fairy_tale')
    token = os.environ.get('sl.u.AGVQsfS75sVZhCy6fIsUE_qWc3aqvs9yEg_yI5cyOXo3q2dSSfYN6T4cq6CB29YFVO3TgUcvSmJfM8tQtz-9Ga2PL3Bi-SkkrWPOAzvNT8G5_-zyNV5S2OlyEzanoYF6qnXSCJmrDIAGjH_qyeW5kddDV89fmETTx1JdEnUAD7lDURM7_zf-ABejyJ9b_4aBcVdcsY_bGyUtnnBHiVxi-jNW7_l0OeA6zXBWrRwrxNOB7reBG30Rqc_c5HzziFJ7Eu-RgpEyvIrxw6QWFaT0apevFBz1SnEStZb3IUacfv1f28EtSUxAJJMGf59RsfrkkQPh3-ouwwKqcHT2aA4WkBPMiiq0ENopM71pV5NPX8yoGgbF-HuS5Q7prEPx3UhT7gUJPDzVw1uFje0SXG_v9vmHcBXvdK7OmxiklYZuTl7R5vBJA2SWNGqc12JoyNa97GJIRl3Cds9IN0hrgrENnEncEuJUDkstNHl_0a9O6UHH_SJsT8dJtGnT9pfL465ZYuGwqNV-pCTViQpu71g267_74-9l2x4g_T58yqzMl_TC9gMHi8FdWZPe2cNDROnVXg4t5quJDjaEjNlsheBd1tO-0uEga-Ht0VgYJtwH7MWVjOI4Up3vunvyb2-40wDVPBIu-4SlBnK8AGo4byR-queb_dU8vpy2DMq3SMmwir6eDfszdJemoquxgDQKa7e9tNc1kVp4eUWrEJPxEHfoaYRrL1EpJBpOQPfE34K9HqtbqG1zIQaE-0N9AdZOErUYUSSvGOBkPK73ajifsQiS9nQE9jHeelBX2pUiNzgl4sFiomEq2yQFxsIL7dgVJEijHLxqps69d3R94wMnV22RUNmwgQKakpVkYoWQLiMeiim42H33I-gkkJh_iQbow7Y3mpuZk3ge3_ciywtPM6VyIgmAlXt_0KB6AXa0DM4_Oc8JLC-KwYF-xPJX9aOKbZ7o_5VhFPU3R-oM-CgfmI5VMgzEO-eI2qhby5lbCIE2NNwbX2Up5onHKfj5QduPVq6g-liqqdTExkPlaa1rPPJqPahpk1wOKCnq77nfx-wiOezTuVl8UTXWVFM-wbRDMiWc9avs_9NlHDildMFi_KKM4vp4XTWLinyxMLoECsqYxw8f0jxBtNv-XbeTDoe7i4BmcjIF9GAglP9Cty5E6Nxnid9AQQ1W6BI3zejx-YvJfRMtx37EViPYVjYwQ7EvQq785tTh32_vc6exECJ73ludMvh8QxReDnJODVvYFcWCWP2R4TFoqzhZT-XarVPqX7Xsn62FxFr-KXsnNdj7YKJKG8_MC7VepEgudmxHvTLrQg8dF4Ixiz-X8DQgfQtEV96SK3O-lIbmvbr7xpj5jXGyllGe')

    # Запускаємо рендер у фоновому потоці
    thread = threading.Thread(target=background_render, args=(scenes, title, token))
    thread.start()

    return jsonify({"status": "Accepted", "message": "Rendering started in background. Check your Dropbox in a few minutes."}), 202

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
