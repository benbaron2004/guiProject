import tkinter as tk
import customtkinter as ctk
from datetime import datetime
import calendar


class CTkDatePicker(ctk.CTkFrame):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)

        self.date_entry = ctk.CTkEntry(self)
        self.date_entry.grid(row=0, column=0, sticky="ew", padx=5, pady=5)

        self.calendar_button = ctk.CTkButton(self, text="▼", width=20, command=self.open_calendar)
        self.calendar_button.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

        self.popup = None
        self.selected_date = None
        self.date_format = "%m/%d/%Y"
        self.allow_manual_input = True
        self.allow_change_month = True
        self.add_months = 0
        self.subtract_months = 0
        self.max_date = datetime.now().date()

    def set_date_format(self, date_format):
        self.date_format = date_format

    def set_localization(self, localization):
        import locale

        locale.setlocale(locale.LC_ALL, localization)
        locale.setlocale(locale.LC_NUMERIC, "C")

    def open_calendar(self):
        if self.popup is not None:
            self.popup.destroy()
        self.popup = ctk.CTkToplevel(self)
        self.popup.title("Select Date")
        self.popup.geometry("+%d+%d" % (self.winfo_rootx(), self.winfo_rooty() + self.winfo_height()))
        self.popup.resizable(False, False)
        self.popup.after(500, lambda: self.popup.focus())
        self.current_year = datetime.now().year
        self.current_month = datetime.now().month
        self.build_calendar()

    def build_calendar(self):
        if hasattr(self, "calendar_frame"):
            self.calendar_frame.destroy()

        self.calendar_frame = ctk.CTkFrame(self.popup)
        self.calendar_frame.grid(row=0, column=0)

        for i in range(self.add_months):
            if self.current_month == 12:
                self.current_month = 1
                self.current_year += 1
            else:
                self.current_month += 1

        for i in range(self.subtract_months):
            if self.current_month == 1:
                self.current_month = 12
                self.current_year -= 1
            else:
                self.current_month -= 1

        month_label = ctk.CTkLabel(
            self.calendar_frame, text=f"{calendar.month_name[self.current_month].capitalize()}, {self.current_year}"
        )
        month_label.grid(row=0, column=1, columnspan=5)

        if self.allow_change_month:
            prev_month_button = ctk.CTkButton(self.calendar_frame, text="<", width=5, command=self.prev_month)
            prev_month_button.grid(row=0, column=0)

            next_month_button = ctk.CTkButton(self.calendar_frame, text=">", width=5, command=self.next_month)
            next_month_button.grid(row=0, column=6)

        days = [calendar.day_name[i][:3].capitalize() for i in range(7)]
        for i, day in enumerate(days):
            lbl = ctk.CTkLabel(self.calendar_frame, text=day)
            lbl.grid(row=1, column=i)

        month_days = calendar.monthrange(self.current_year, self.current_month)[1]
        start_day = calendar.monthrange(self.current_year, self.current_month)[0]
        day = 1
        for week in range(2, 8):
            for day_col in range(7):
                if week == 2 and day_col < start_day:
                    lbl = ctk.CTkLabel(self.calendar_frame, text="")
                    lbl.grid(row=week, column=day_col)
                elif day > month_days:
                    lbl = ctk.CTkLabel(self.calendar_frame, text="")
                    lbl.grid(row=week, column=day_col)
                else:
                    candidate_date = datetime(self.current_year, self.current_month, day).date()
                    if candidate_date > self.max_date:
                        btn = ctk.CTkButton(self.calendar_frame, text=str(day), width=3, state="disabled")
                    else:
                        if ctk.get_appearance_mode() == "Light":
                            btn = ctk.CTkButton(
                                self.calendar_frame,
                                text=str(day),
                                width=3,
                                command=lambda day=day: self.select_date(day),
                                fg_color="transparent",
                                text_color="black",
                            )
                        else:
                            btn = ctk.CTkButton(
                                self.calendar_frame,
                                text=str(day),
                                width=3,
                                command=lambda day=day: self.select_date(day),
                                fg_color="transparent",
                            )
                    btn.grid(row=week, column=day_col)
                    day += 1

    def prev_month(self):
        if self.current_month == 1:
            self.current_month = 12
            self.current_year -= 1
        else:
            self.current_month -= 1
        self.build_calendar()

    def next_month(self):
        if self.current_month == 12:
            self.current_month = 1
            self.current_year += 1
        else:
            self.current_month += 1
        self.build_calendar()

    def select_date(self, day):
        candidate_date = datetime(self.current_year, self.current_month, day).date()
        if candidate_date > self.max_date:
            return  # אל תאפשר בחירה של תאריך גדול מדי

        self.selected_date = datetime(self.current_year, self.current_month, day)
        self.date_entry.configure(state="normal")
        self.date_entry.delete(0, tk.END)
        self.date_entry.insert(0, self.selected_date.strftime(self.date_format))
        if not self.allow_manual_input:
            self.date_entry.configure(state="disabled")
        self.popup.destroy()
        self.popup = None

    def get_date(self):
        return self.date_entry.get()

    def set_allow_manual_input(self, value):
        self.allow_manual_input = value
        if not value:
            self.date_entry.configure(state="disabled")
        else:
            self.date_entry.configure(state="normal")

    def set_allow_change_month(self, value):
        self.allow_change_month = value

    def set_change_months(self, add_or_sub, value):
        if add_or_sub == "add":
            self.add_months = value
        elif add_or_sub == "sub":
            self.subtract_months = value
        else:
            raise ValueError("Invalid value for add_or_sub. Must be 'add' or 'sub'")

    def set_max_date(self, max_date):
        self.max_date = max_date
