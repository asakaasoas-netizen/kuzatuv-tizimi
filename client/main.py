from kivy.app import App
from kivy.uix.label import Label

class StealthApp(App):
    def build(self):
        return Label(text="Ishlayapti! ✅")

if __name__ == '__main__':
    StealthApp().run()
