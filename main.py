__version__ = "1.0.0"

import os
from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.checkbox import CheckBox

from jnius import autoclass
from android import activity

# Android intents open the phone's installed camera and document picker.
# The camera app handles its own camera permission, avoiding Plyer camera support.

RANGES = [
    (90, 100, 1250),
    (85, 89, 1000),
    (80, 84, 750),
    (75, 79, 500),
    (70, 74, 400),
    (60, 69, 150),
]

FIRST_TEAM = [
    ("CF", 75), ("LMF", 82), ("AMF", 68), ("RMF", 84),
    ("DMF", 78), ("DMF", 84), ("LB", 84), ("CB", 87),
    ("CB", 79), ("RB", 87), ("GK", 85),
]
SUBS = [88, 87, 80, 82, 86, 76, 94, 94, 96, 93, 95, 94]


def fee(rating):
    for low, high, amount in RANGES:
        if low <= rating <= high:
            return amount
    return 0


def initial_players():
    items = []
    for pos, rating in FIRST_TEAM:
        items.append({"name": pos, "rating": rating, "selected": True, "group": "FIRST TEAM"})
    for n, rating in enumerate(SUBS, 1):
        items.append({"name": "Sub {}".format(n), "rating": rating, "selected": True, "group": "SUBSTITUTES"})
    return items


class RatingMoneyApp(App):
    CAMERA_REQUEST = 4101
    GALLERY_REQUEST = 4102

    def build(self):
        self.title = "Rating Money Calculator"
        self.players = initial_players()
        self.rows = []
        self.pending_camera_uri = None
        self.last_photo_path = None

        root = BoxLayout(orientation="vertical", padding=dp(9), spacing=dp(7))
        root.add_widget(Label(
            text="[b]RATING MONEY CALCULATOR[/b]",
            markup=True, size_hint_y=None, height=dp(42), font_size="21sp"
        ))

        top = GridLayout(cols=2, spacing=dp(6), size_hint_y=None, height=dp(94))
        self.add_button(top, "TAKE PHOTO", self.take_photo)
        self.add_button(top, "IMPORT IMAGE", self.pick_image)
        self.add_button(top, "SELECT ALL", self.select_all)
        self.add_button(top, "DESELECT ALL", self.deselect_all)
        root.add_widget(top)

        self.status = Label(
            text="Starting squad loaded from your first photo. Camera uses the Android camera app.",
            size_hint_y=None, height=dp(48), font_size="12sp",
            halign="center", valign="middle"
        )
        self.status.bind(size=lambda w, s: setattr(w, "text_size", (s[0]-dp(8), None)))
        root.add_widget(self.status)

        scroll = ScrollView(do_scroll_x=False)
        self.list_box = BoxLayout(orientation="vertical", spacing=dp(4), size_hint_y=None)
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        scroll.add_widget(self.list_box)
        root.add_widget(scroll)

        self.total_label = Label(
            text="", markup=True, size_hint_y=None, height=dp(105),
            halign="left", valign="middle", font_size="13sp"
        )
        self.total_label.bind(size=lambda w, s: setattr(w, "text_size", (s[0]-dp(8), None)))
        root.add_widget(self.total_label)

        self.rebuild()
        self.recalculate()
        return root

    def add_button(self, parent, text, callback):
        btn = Button(text=text, font_size="14sp")
        btn.bind(on_release=callback)
        parent.add_widget(btn)

    # -------- Android camera intent --------
    def take_photo(self, *_):
        try:
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            MediaStoreImages = autoclass("android.provider.MediaStore$Images$Media")
            ContentValues = autoclass("android.content.ContentValues")
            Intent = autoclass("android.content.Intent")

            activity_obj = PythonActivity.mActivity
            resolver = activity_obj.getContentResolver()
            values = ContentValues()
            values.put("_display_name", "rating_squad_capture.jpg")
            values.put("mime_type", "image/jpeg")
            # MediaStore handles the actual shared photo location on modern Android.
            uri = resolver.insert(MediaStoreImages.EXTERNAL_CONTENT_URI, values)
            if uri is None:
                raise RuntimeError("Android could not create a photo destination.")

            intent = Intent(Intent.ACTION_IMAGE_CAPTURE)
            intent.putExtra(MediaStoreImages.MEDIA, uri)
            # EXTRA_OUTPUT is the standard camera output contract.
            intent.putExtra("output", uri)
            intent.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)

            self.pending_camera_uri = uri
            self.status.text = "Opening your Android camera..."
            activity_obj.startActivityForResult(intent, self.CAMERA_REQUEST)
        except Exception as exc:
            self.status.text = "Could not launch Android camera: {}".format(exc)

    # -------- Android document/gallery picker --------
    def pick_image(self, *_):
        try:
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Intent = autoclass("android.content.Intent")
            intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
            intent.addCategory(Intent.CATEGORY_OPENABLE)
            intent.setType("image/*")
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            self.status.text = "Choose a squad photo or screenshot..."
            PythonActivity.mActivity.startActivityForResult(intent, self.GALLERY_REQUEST)
        except Exception as exc:
            self.status.text = "Could not open image picker: {}".format(exc)

    def on_start(self):
        activity.bind(on_activity_result=self.on_activity_result)

    def on_stop(self):
        try:
            activity.unbind(on_activity_result=self.on_activity_result)
        except Exception:
            pass

    def on_activity_result(self, request_code, result_code, intent):
        try:
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Activity = autoclass("android.app.Activity")
            if result_code != Activity.RESULT_OK:
                self.status.text = "No image selected."
                return

            if request_code == self.CAMERA_REQUEST:
                uri = self.pending_camera_uri
            elif request_code == self.GALLERY_REQUEST:
                uri = intent.getData() if intent is not None else None
            else:
                return

            if uri is None:
                self.status.text = "Android did not return an image."
                return

            self.status.text = "Image received. Copying it into the app..."
            Clock.schedule_once(lambda dt: self.copy_uri_to_private_file(uri), 0)
        except Exception as exc:
            self.status.text = "Image return error: {}".format(exc)

    def copy_uri_to_private_file(self, uri):
        try:
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            FileOutputStream = autoclass("java.io.FileOutputStream")
            activity_obj = PythonActivity.mActivity
            stream = activity_obj.getContentResolver().openInputStream(uri)
            if stream is None:
                raise RuntimeError("Android could not open the selected image.")

            output_path = os.path.join(self.user_data_dir, "latest_squad.jpg")
            out = FileOutputStream(output_path)
            while True:
                value = stream.read()
                if value == -1:
                    break
                out.write(value)
            out.flush()
            out.close()
            stream.close()

            self.last_photo_path = output_path
            self.status.text = (
                "Photo saved successfully. Automatic rating recognition is the next "
                "module; check/edit the squad list below for now."
            )
        except Exception as exc:
            self.status.text = "Could not read image: {}".format(exc)

    # -------- Player list and calculation --------
    def rebuild(self):
        self.list_box.clear_widgets()
        self.rows = []
        for group in ("FIRST TEAM", "SUBSTITUTES"):
            subset = [(i, p) for i, p in enumerate(self.players) if p["group"] == group]
            if not subset:
                continue
            heading = Label(
                text="[b]{}[/b]".format(group), markup=True,
                size_hint_y=None, height=dp(30), halign="left"
            )
            heading.bind(size=lambda w, s: setattr(w, "text_size", (s[0], None)))
            self.list_box.add_widget(heading)

            for i, player in subset:
                row = BoxLayout(size_hint_y=None, height=dp(47), spacing=dp(4))
                row.add_widget(Label(text=player["name"], size_hint_x=.27, font_size="13sp"))
                rating = TextInput(
                    text=str(player["rating"]), input_filter="int",
                    multiline=False, size_hint_x=.20, font_size="16sp",
                    halign="center"
                )
                rating.bind(text=lambda field, value, idx=i: self.rating_changed(idx, value))
                row.add_widget(rating)
                amount = Label(text="{} UGX".format(fee(player["rating"])),
                               size_hint_x=.32, font_size="12sp")
                row.add_widget(amount)
                check = CheckBox(active=player["selected"], size_hint_x=.16)
                check.bind(active=lambda box, value, idx=i: self.selection_changed(idx, value))
                row.add_widget(check)
                self.list_box.add_widget(row)
                self.rows.append((i, rating, amount, check))

    def rating_changed(self, idx, value):
        if value.isdigit() and 0 <= int(value) <= 100:
            self.players[idx]["rating"] = int(value)
            self.recalculate()

    def selection_changed(self, idx, value):
        self.players[idx]["selected"] = value
        self.recalculate()

    def select_all(self, *_):
        for p in self.players:
            p["selected"] = True
        self.rebuild()
        self.recalculate()

    def deselect_all(self, *_):
        for p in self.players:
            p["selected"] = False
        self.rebuild()
        self.recalculate()

    def recalculate(self):
        total = 0
        count = 0
        categories = {a: 0 for _, _, a in RANGES}
        for p in self.players:
            amount = fee(int(p["rating"]))
            if p["selected"]:
                total += amount
                count += 1
                if amount in categories:
                    categories[amount] += 1

        self.total_label.text = (
            "[b]TOTAL: {:,} UGX[/b]\n"
            "Selected: {} / {}\n"
            "90-100: {} | 85-89: {} | 80-84: {}\n"
            "75-79: {} | 70-74: {} | 60-69: {}"
        ).format(
            total, count, len(self.players),
            categories[1250], categories[1000], categories[750],
            categories[500], categories[400], categories[150]
        )
        for idx, rating, amount, check in self.rows:
            amount.text = "{} UGX".format(fee(int(self.players[idx]["rating"])))


if __name__ == "__main__":
    RatingMoneyApp().run()
