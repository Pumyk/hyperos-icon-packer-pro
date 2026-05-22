import os
import sys
import threading
import zipfile
import shutil
from pathlib import Path
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, SlideTransition, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.progressbar import ProgressBar
from kivy.uix.scrollview import ScrollView
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.logger import Logger
from PIL import Image as PILImage
import struct
import re

Window.size = (540, 960)

# ============================================================================
# GLOBAL STATE
# ============================================================================
STATE = {
    'apk_path': '',
    'apk_filename': '',
    'work_dir': '',
    'copy_icon_dir': '',
    'rename_dir': '',
    'resize_dir': '',
    'final_dir': '',
    'appfilter_path': '',
    'appfilter_decoded': '',
    'icon_count': 0,
    'renamed_count': 0,
    'missing_count': 0,
    'resized_count': 0,
    'pack_name': 'MyIconPack',
    'output_zip_path': '',
    'target_width': 192,
    'target_height': 192,
    'mask_generated': False,
}

# ============================================================================
# UTIL: Android File Access
# ============================================================================
def get_files_dir():
    from jnius import autoclass
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    activity = PythonActivity.mActivity
    return str(activity.getFilesDir())


def open_file_picker():
    from jnius import autoclass, cast
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    Intent = autoclass('android.content.Intent')
    activity = PythonActivity.mActivity
    intent = Intent()
    intent.setAction(Intent.ACTION_GET_CONTENT)
    intent.setType('*/*')
    return None


def copy_file_from_fd(fd, dest_path, chunk_size=65536):
    try:
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, 'wb') as f:
            while True:
                chunk = os.read(fd, chunk_size)
                if not chunk:
                    break
                f.write(chunk)
        return True
    except Exception as e:
        Logger.error(f"Copy error: {e}")
        return False


# ============================================================================
# UTIL: ZIP & XML Handling
# ============================================================================
def is_valid_apk(path):
    return zipfile.is_zipfile(path)


def extract_apk(apk_path, extract_to):
    os.makedirs(extract_to, exist_ok=True)
    with zipfile.ZipFile(apk_path, 'r') as z:
        z.extractall(extract_to)


def find_appfilter(base_path):
    for root, dirs, files in os.walk(base_path):
        if 'appfilter.xml' in files:
            return os.path.join(root, 'appfilter.xml')
    return None


def decode_binary_xml(xml_path):
    try:
        with open(xml_path, 'rb') as f:
            data = f.read()
        if len(data) < 8 or data[0:2] != b'\x03\x00':
            return data.decode('utf-8', errors='ignore')
        strings = []
        try:
            result = data.decode('utf-8', errors='ignore')
            return result
        except:
            return '<error>Could not decode</error>'
    except Exception as e:
        Logger.error(f"XML decode error: {e}")
        return f'<error>{str(e)}</error>'


def find_icon_folders(base_path):
    folders = {}
    for root, dirs, files in os.walk(base_path):
        png_count = sum(1 for f in files if f.lower().endswith('.png'))
        if png_count > 0:
            if 'mipmap' not in root:
                folders[root] = png_count
    sorted_folders = sorted(folders.items(), key=lambda x: x[1], reverse=True)
    return sorted_folders


# ============================================================================
# SCREENS
# ============================================================================

class WelcomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=20, spacing=20)
        layout.add_widget(Label(text='HyperOS Icon Packer Pro', font_size='32sp', bold=True))
        layout.add_widget(Label(text='Automate icon pack injection pipeline', font_size='14sp', color=(0.5, 0.5, 0.5, 1)))
        layout.add_widget(Label(text=''))
        layout.add_widget(Button(text='Next', size_hint_y=0.15, on_press=self.go_next))
        self.add_widget(layout)

    def go_next(self, instance):
        self.manager.current = 'pick_apk'


class PickApkScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.selected_file = None
        self.layout = BoxLayout(orientation='vertical', padding=20, spacing=20)
        self.layout.add_widget(Label(text='Pick Icon Pack APK', font_size='24sp', bold=True))
        self.file_label = Label(text='No file selected', size_hint_y=0.2)
        self.layout.add_widget(self.file_label)
        self.layout.add_widget(Button(text='Browse', size_hint_y=0.15, on_press=self.show_file_picker))
        self.layout.add_widget(Label(text=''))
        self.next_btn = Button(text='Next', size_hint_y=0.15, disabled=True)
        self.next_btn.bind(on_press=self.go_next)
        self.layout.add_widget(self.next_btn)
        self.add_widget(self.layout)

    def show_file_picker(self, instance):
        content = BoxLayout(orientation='vertical')
        filechooser = FileChooserListView(filters=['*.apk', '*.zip'])
        content.add_widget(filechooser)
        btn_layout = BoxLayout(size_hint_y=0.1, spacing=10)
        btn_layout.add_widget(Button(text='Select', on_press=lambda x: self.select_file(filechooser.selection)))
        btn_layout.add_widget(Button(text='Cancel', on_press=lambda x: popup.dismiss()))
        content.add_widget(btn_layout)
        popup = Popup(title='Select APK', content=content, size_hint=(0.9, 0.9))
        popup.open()

    def select_file(self, selection):
        if selection and is_valid_apk(selection[0]):
            self.selected_file = selection[0]
            filename = os.path.basename(self.selected_file)
            STATE['apk_path'] = self.selected_file
            STATE['apk_filename'] = filename
            stem = filename.replace('.apk', '').replace('.zip', '')
            STATE['pack_name'] = stem
            try:
                files_dir = get_files_dir()
            except:
                files_dir = os.path.expanduser('~')
            STATE['work_dir'] = os.path.join(files_dir, f'HyperOS_IconPacker_{stem}')
            STATE['copy_icon_dir'] = os.path.join(STATE['work_dir'], 'copy_icon')
            STATE['rename_dir'] = os.path.join(STATE['work_dir'], 'icon_rename')
            STATE['resize_dir'] = os.path.join(STATE['work_dir'], 'icon_resize')
            STATE['final_dir'] = os.path.join(STATE['work_dir'], 'Final')
            self.file_label.text = f'Selected: {filename}'
            self.next_btn.disabled = False


class ExtractScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=20, spacing=20)
        self.layout.add_widget(Label(text='Extract & Decode', font_size='24sp', bold=True))
        self.progress = ProgressBar(max=100, value=0, size_hint_y=0.1)
        self.layout.add_widget(self.progress)
        scroll = ScrollView()
        self.log_label = Label(text='Waiting...', size_hint_y=None, markup=True)
        self.log_label.bind(texture_size=self.log_label.setter('size'))
        scroll.add_widget(self.log_label)
        self.layout.add_widget(scroll)
        self.next_btn = Button(text='Next', size_hint_y=0.15, disabled=True)
        self.next_btn.bind(on_press=self.go_next)
        self.layout.add_widget(self.next_btn)
        self.add_widget(self.layout)

    def on_enter(self):
        threading.Thread(target=self.run_extract, daemon=True).start()

    def run_extract(self):
        logs = []
        try:
            logs.append("[color=4caf50]Creating work directory...[/color]")
            self.update_log(logs)
            work_dir = STATE['work_dir']
            if os.path.exists(work_dir):
                shutil.rmtree(work_dir)
            os.makedirs(work_dir, exist_ok=True)

            logs.append("[color=4caf50]Extracting APK...[/color]")
            self.update_log(logs)
            base_extract = os.path.join(work_dir, 'base_extract')
            extract_apk(STATE['apk_path'], base_extract)

            logs.append("[color=4caf50]Finding icon folders...[/color]")
            self.update_log(logs)
            folders = find_icon_folders(base_extract)
            for folder, count in folders[:3]:
                logs.append(f"  {folder}: {count} PNGs")
            self.update_log(logs)

            logs.append("[color=ff9800]Finding appfilter.xml...[/color]")
            self.update_log(logs)
            appfilter_path = find_appfilter(base_extract)
            if appfilter_path:
                logs.append(f"Found: {appfilter_path}")
                STATE['appfilter_path'] = appfilter_path
                logs.append("[color=ff9800]Decoding binary XML...[/color]")
                self.update_log(logs)
                decoded = decode_binary_xml(appfilter_path)
                STATE['appfilter_decoded'] = decoded
                logs.append("[color=4caf50]Decoded successfully[/color]")
            else:
                logs.append("[color=f44336]appfilter.xml not found[/color]")

            logs.append("[color=4caf50]Copying icons to copy_icon/...[/color]")
            self.update_log(logs)
            if folders:
                icon_folder = folders[0][0]
                os.makedirs(STATE['copy_icon_dir'], exist_ok=True)
                png_count = 0
                for f in os.listdir(icon_folder):
                    if f.lower().endswith('.png'):
                        shutil.copy2(os.path.join(icon_folder, f), STATE['copy_icon_dir'])
                        png_count += 1
                STATE['icon_count'] = png_count
                logs.append(f"[color=4caf50]Copied {png_count} icons[/color]")

            self.update_log(logs)
            self.update_progress(100)
            Clock.schedule_once(lambda x: setattr(self.next_btn, 'disabled', False), 0.1)
        except Exception as e:
            logs.append(f"[color=f44336]Error: {str(e)}[/color]")
            self.update_log(logs)

    def update_log(self, logs):
        Clock.schedule_once(lambda x: self._set_log_text(logs), 0)

    def _set_log_text(self, logs):
        self.log_label.text = '\n'.join(logs)

    def update_progress(self, value):
        Clock.schedule_once(lambda x: setattr(self.progress, 'value', value), 0)

    def go_next(self, instance):
        self.manager.current = 'rename'


class RenameScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=20, spacing=20)
        self.layout.add_widget(Label(text='Rename Icons', font_size='24sp', bold=True))
        self.run_btn = Button(text='Run Rename', size_hint_y=0.15)
        self.run_btn.bind(on_press=self.run_rename)
        self.layout.add_widget(self.run_btn)
        self.progress = ProgressBar(max=100, value=0, size_hint_y=0.1)
        self.layout.add_widget(self.progress)
        scroll = ScrollView()
        self.log_label = Label(text='', size_hint_y=None, markup=True)
        self.log_label.bind(texture_size=self.log_label.setter('size'))
        scroll.add_widget(self.log_label)
        self.layout.add_widget(scroll)
        self.next_btn = Button(text='Next', size_hint_y=0.15, disabled=True)
        self.next_btn.bind(on_press=self.go_next)
        self.layout.add_widget(self.next_btn)
        self.add_widget(self.layout)

    def run_rename(self, instance):
        threading.Thread(target=self._run_rename_thread, daemon=True).start()

    def _run_rename_thread(self):
        logs = []
        os.makedirs(STATE['rename_dir'], exist_ok=True)
        logs.append("[color=4caf50]Parsing appfilter.xml...[/color]")
        self.update_log(logs)
        pattern = r'component="ComponentInfo\{([^/]+)/[^}]*\}"\s+drawable="([^"]+)"'
        matches = re.findall(pattern, STATE['appfilter_decoded'])
        logs.append(f"[color=4caf50]Found {len(matches)} component-drawable pairs[/color]")
        self.update_log(logs)
        icon_files = {f.lower(): f for f in os.listdir(STATE['copy_icon_dir']) if f.lower().endswith('.png')}
        renamed_count = 0
        missing_count = 0
        for package, drawable in matches:
            drawable_key = drawable.lower() + '.png'
            if drawable_key in icon_files:
                src = os.path.join(STATE['copy_icon_dir'], icon_files[drawable_key])
                dst = os.path.join(STATE['rename_dir'], f'{package}.png')
                shutil.copy2(src, dst)
                renamed_count += 1
                logs.append(f"[color=4caf50]{package} done[/color]")
            else:
                missing_count += 1
                logs.append(f"[color=ff9800]{package} missing[/color]")
            self.update_log(logs)
        STATE['renamed_count'] = renamed_count
        STATE['missing_count'] = missing_count
        logs.append(f"[color=4caf50]Renamed: {renamed_count}, Missing: {missing_count}[/color]")
        self.update_log(logs)
        self.update_progress(100)
        Clock.schedule_once(lambda x: setattr(self.next_btn, 'disabled', False), 0.1)

    def update_log(self, logs):
        Clock.schedule_once(lambda x: self._set_log_text(logs), 0)

    def _set_log_text(self, logs):
        self.log_label.text = '\n'.join(logs)

    def update_progress(self, value):
        Clock.schedule_once(lambda x: setattr(self.progress, 'value', value), 0)

    def go_next(self, instance):
        self.manager.current = 'resize'


class ResizeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=20, spacing=20)
        self.layout.add_widget(Label(text='Resize Icons', font_size='24sp', bold=True))
        size_layout = BoxLayout(size_hint_y=0.15, spacing=10)
        size_layout.add_widget(Label(text='W:', size_hint_x=0.1))
        self.width_input = TextInput(text='192', multiline=False, size_hint_x=0.4)
        size_layout.add_widget(self.width_input)
        size_layout.add_widget(Label(text='H:', size_hint_x=0.1))
        self.height_input = TextInput(text='192', multiline=False, size_hint_x=0.4))
        size_layout.add_widget(self.height_input)
        self.layout.add_widget(size_layout)
        self.run_btn = Button(text='Run Resize', size_hint_y=0.15)
        self.run_btn.bind(on_press=self.run_resize)
        self.layout.add_widget(self.run_btn)
        self.progress = ProgressBar(max=100, value=0, size_hint_y=0.1)
        self.layout.add_widget(self.progress)
        scroll = ScrollView()
        self.log_label = Label(text='', size_hint_y=None, markup=True)
        self.log_label.bind(texture_size=self.log_label.setter('size'))
        scroll.add_widget(self.log_label)
        self.layout.add_widget(scroll)
        self.next_btn = Button(text='Next', size_hint_y=0.15, disabled=True)
        self.next_btn.bind(on_press=self.go_next)
        self.layout.add_widget(self.next_btn)
        self.add_widget(self.layout)

    def run_resize(self, instance):
        try:
            w = int(self.width_input.text)
            h = int(self.height_input.text)
            STATE['target_width'] = w
            STATE['target_height'] = h
            threading.Thread(target=self._run_resize_thread, args=(w, h), daemon=True).start()
        except ValueError:
            self.log_label.text = "[color=f44336]Invalid dimensions[/color]"

    def _run_resize_thread(self, w, h):
        logs = []
        os.makedirs(STATE['resize_dir'], exist_ok=True)
        logs.append(f"[color=4caf50]Resizing to {w}x{h}...[/color]")
        self.update_log(logs)
        files = [f for f in os.listdir(STATE['rename_dir']) if f.lower().endswith('.png')]
        resized_count = 0
        for i, filename in enumerate(files):
            try:
                src = os.path.join(STATE['rename_dir'], filename)
                dst = os.path.join(STATE['resize_dir'], filename)
                img = PILImage.open(src).convert('RGBA')
                bbox = img.getbbox()
                if bbox:
                    img = img.crop(bbox)
                img = img.resize((w, h), PILImage.LANCZOS)
                img.save(dst, 'PNG')
                resized_count += 1
            except Exception as e:
                logs.append(f"[color=f44336]Error resizing {filename}: {e}[/color]")
            if (i + 1) % 10 == 0 or i == len(files) - 1:
                logs.append(f"[color=4caf50]Processed {i + 1}/{len(files)}[/color]")
                self.update_log(logs)
        STATE['resized_count'] = resized_count
        logs.append(f"[color=4caf50]Resized {resized_count} icons[/color]")
        self.update_log(logs)
        self.update_progress(100)
        Clock.schedule_once(lambda x: setattr(self.next_btn, 'disabled', False), 0.1)

    def update_log(self, logs):
        Clock.schedule_once(lambda x: self._set_log_text(logs), 0)

    def _set_log_text(self, logs):
        self.log_label.text = '\n'.join(logs)

    def update_progress(self, value):
        Clock.schedule_once(lambda x: setattr(self.progress, 'value', value), 0)

    def go_next(self, instance):
        self.manager.current = 'mask'


class MaskScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=20, spacing=20)
        self.layout.add_widget(Label(text='Generate Mask', font_size='24sp', bold=True))
        self.layout.add_widget(Label(text='Auto-detect icon shape and generate mask assets'))
        self.detect_btn = Button(text='Auto-detect Shape', size_hint_y=0.15)
        self.detect_btn.bind(on_press=self.detect_shape)
        self.layout.add_widget(self.detect_btn)
        self.progress = ProgressBar(max=100, value=0, size_hint_y=0.1)
        self.layout.add_widget(self.progress)
        scroll = ScrollView()
        self.log_label = Label(text='', size_hint_y=None, markup=True)
        self.log_label.bind(texture_size=self.log_label.setter('size'))
        scroll.add_widget(self.log_label)
        self.layout.add_widget(scroll)
        self.next_btn = Button(text='Next', size_hint_y=0.15, disabled=True)
        self.next_btn.bind(on_press=self.go_next)
        self.layout.add_widget(self.next_btn)
        self.add_widget(self.layout)

    def detect_shape(self, instance):
        threading.Thread(target=self._detect_shape_thread, daemon=True).start()

    def _detect_shape_thread(self):
        logs = []
        try:
            logs.append("[color=4caf50]Loading first icon...[/color]")
            self.update_log(logs)
            files = [f for f in os.listdir(STATE['resize_dir']) if f.lower().endswith('.png')]
            if not files:
                logs.append("[color=f44336]No icons found[/color]")
                self.update_log(logs)
                return
            first_icon_path = os.path.join(STATE['resize_dir'], files[0])
            img = PILImage.open(first_icon_path).convert('RGBA')
            logs.append("[color=4caf50]Extracting alpha channel...[/color]")
            self.update_log(logs)
            alpha = img.split()[3]
            logs.append("[color=4caf50]Computing shape and average color...[/color]")
            self.update_log(logs)
            pixels = img.load()
            w, h = img.size
            total_r = total_g = total_b = count = 0
            for y in range(h):
                for x in range(w):
                    r, g, b, a = pixels[x, y]
                    if a > 128:
                        total_r += r
                        total_g += g
                        total_b += b
                        count += 1
            avg_color = (total_r // count, total_g // count, total_b // count) if count > 0 else (100, 100, 100)
            logs.append("[color=4caf50]Generating iconback.png...[/color]")
            self.update_log(logs)
            iconback = PILImage.new('RGBA', (w, h), avg_color + (255,))
            iconback_path = os.path.join(STATE['resize_dir'], 'iconback.png')
            iconback.save(iconback_path)
            logs.append("[color=4caf50]Generating iconmask.png...[/color]")
            self.update_log(logs)
            iconmask = PILImage.new('RGB', (w, h), (0, 0, 0))
            mask_pixels = iconmask.load()
            for y in range(h):
                for x in range(w):
                    if alpha.getpixel((x, y)) > 128:
                        mask_pixels[x, y] = (255, 255, 255)
            iconmask_path = os.path.join(STATE['resize_dir'], 'iconmask.png')
            iconmask.save(iconmask_path)
            logs.append("[color=4caf50]Generating iconupon.png...[/color]")
            self.update_log(logs)
            iconupon = PILImage.new('RGBA', (w, h), (0, 0, 0, 0))
            iconupon_path = os.path.join(STATE['resize_dir'], 'iconupon.png')
            iconupon.save(iconupon_path)
            logs.append("[color=4caf50]Updating appfilter.xml...[/color]")
            self.update_log(logs)
            mask_tags = '\n<iconback img1="iconback"/>\n<iconmask img1="iconmask"/>\n<iconupon img1="iconupon"/>'
            STATE['appfilter_decoded'] += mask_tags
            STATE['mask_generated'] = True
            logs.append("[color=4caf50]Mask generation complete[/color]")
            self.update_log(logs)
            self.update_progress(100)
            Clock.schedule_once(lambda x: setattr(self.next_btn, 'disabled', False), 0.1)
        except Exception as e:
            logs.append(f"[color=f44336]Error: {str(e)}[/color]")
            self.update_log(logs)

    def update_log(self, logs):
        Clock.schedule_once(lambda x: self._set_log_text(logs), 0)

    def _set_log_text(self, logs):
        self.log_label.text = '\n'.join(logs)

    def update_progress(self, value):
        Clock.schedule_once(lambda x: setattr(self.progress, 'value', value), 0)

    def go_next(self, instance):
        self.manager.current = 'build'


class BuildScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=20, spacing=20)
        self.layout.add_widget(Label(text='Build ZIP Pack', font_size='24sp', bold=True))
        self.run_btn = Button(text='Build ZIP Pack', size_hint_y=0.15)
        self.run_btn.bind(on_press=self.run_build)
        self.layout.add_widget(self.run_btn)
        self.progress = ProgressBar(max=100, value=0, size_hint_y=0.1)
        self.layout.add_widget(self.progress)
        scroll = ScrollView()
        self.log_label = Label(text='', size_hint_y=None, markup=True)
        self.log_label.bind(texture_size=self.log_label.setter('size'))
        scroll.add_widget(self.log_label)
        self.layout.add_widget(scroll)
        self.next_btn = Button(text='Finish', size_hint_y=0.15, disabled=True)
        self.next_btn.bind(on_press=self.go_next)
        self.layout.add_widget(self.next_btn)
        self.add_widget(self.layout)

    def run_build(self, instance):
        threading.Thread(target=self._run_build_thread, daemon=True).start()

    def _run_build_thread(self):
        logs = []
        try:
            logs.append("[color=4caf50]Creating Final/ structure...[/color]")
            self.update_log(logs)
            drawable_dir = os.path.join(STATE['final_dir'], 'res', 'drawable-xxhdpi')
            xml_dir = os.path.join(STATE['final_dir'], 'res', 'xml')
            os.makedirs(drawable_dir, exist_ok=True)
            os.makedirs(xml_dir, exist_ok=True)
            logs.append("[color=4caf50]Copying PNGs...[/color]")
            self.update_log(logs)
            for f in os.listdir(STATE['resize_dir']):
                if f.lower().endswith('.png'):
                    src = os.path.join(STATE['resize_dir'], f)
                    dst = os.path.join(drawable_dir, f)
                    shutil.copy2(src, dst)
            logs.append("[color=4caf50]Saving appfilter.xml...[/color]")
            self.update_log(logs)
            appfilter_dst = os.path.join(xml_dir, 'appfilter.xml')
            with open(appfilter_dst, 'w') as f:
                f.write(STATE['appfilter_decoded'])
            logs.append("[color=4caf50]Creating ZIP...[/color]")
            self.update_log(logs)
            try:
                from jnius import autoclass
                Environment = autoclass('android.os.Environment')
                downloads_dir = str(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS))
            except:
                downloads_dir = os.path.expanduser('~/Downloads')
            zip_path = os.path.join(downloads_dir, f'HyperOS_{STATE["pack_name"]}.zip')

            def zipdir(path, ziph):
                for root, dirs, files in os.walk(path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, os.path.dirname(path))
                        ziph.write(file_path, arcname)

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipdir(STATE['final_dir'], zipf)
            STATE['output_zip_path'] = zip_path
            logs.append(f"[color=4caf50]Saved to: {zip_path}[/color]")
            self.update_log(logs)
            self.update_progress(100)
            Clock.schedule_once(lambda x: setattr(self.next_btn, 'disabled', False), 0.1)
        except Exception as e:
            logs.append(f"[color=f44336]Error: {str(e)}[/color]")
            self.update_log(logs)

    def update_log(self, logs):
        Clock.schedule_once(lambda x: self._set_log_text(logs), 0)

    def _set_log_text(self, logs):
        self.log_label.text = '\n'.join(logs)

    def update_progress(self, value):
        Clock.schedule_once(lambda x: setattr(self.progress, 'value', value), 0)

    def go_next(self, instance):
        self.manager.current = 'done'


class DoneScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=20, spacing=20)
        self.layout.add_widget(Label(text='Pack Built Successfully!', font_size='28sp', bold=True, color=(0.29, 0.79, 0.29, 1)))
        self.layout.add_widget(Label(text=''))
        self.path_label = Label(text='', size_hint_y=0.2)
        self.layout.add_widget(self.path_label)
        self.copy_btn = Button(text='Copy Path to Clipboard', size_hint_y=0.15)
        self.copy_btn.bind(on_press=self.copy_path)
        self.layout.add_widget(self.copy_btn)
        self.layout.add_widget(Label(text=''))
        self.reset_btn = Button(text='Process Another APK', size_hint_y=0.15)
        self.reset_btn.bind(on_press=self.reset_app)
        self.layout.add_widget(self.reset_btn)
        self.add_widget(self.layout)

    def on_enter(self):
        self.path_label.text = STATE['output_zip_path']

    def copy_path(self, instance):
        from kivy.core.clipboard import Clipboard
        Clipboard.copy(STATE['output_zip_path'])
        self.copy_btn.text = 'Copied!'

    def reset_app(self, instance):
        global STATE
        STATE = {
            'apk_path': '',
            'apk_filename': '',
            'work_dir': '',
            'copy_icon_dir': '',
            'rename_dir': '',
            'resize_dir': '',
            'final_dir': '',
            'appfilter_path': '',
            'appfilter_decoded': '',
            'icon_count': 0,
            'renamed_count': 0,
            'missing_count': 0,
            'resized_count': 0,
            'pack_name': 'MyIconPack',
            'output_zip_path': '',
            'target_width': 192,
            'target_height': 192,
            'mask_generated': False,
        }
        self.manager.current = 'welcome'


# ============================================================================
# MAIN APP
# ============================================================================
class HyperOSIconPackerApp(App):
    def build(self):
        sm = ScreenManager(transition=SlideTransition())
        sm.add_widget(WelcomeScreen(name='welcome'))
        sm.add_widget(PickApkScreen(name='pick_apk'))
        sm.add_widget(ExtractScreen(name='extract'))
        sm.add_widget(RenameScreen(name='rename'))
        sm.add_widget(ResizeScreen(name='resize'))
        sm.add_widget(MaskScreen(name='mask'))
        sm.add_widget(BuildScreen(name='build'))
        sm.add_widget(DoneScreen(name='done'))
        return sm

if __name__ == '__main__':
    HyperOSIconPackerApp().run()
