import customtkinter as ctk
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from datetime import date, datetime, timedelta
import requests, os, gzip, shutil
import urllib.request
from matplotlib.colors import Normalize
import matplotlib
from matplotlib.cm import ScalarMappable
from ctk_date_picker import CTkDatePicker
from tkintermapview import TkinterMapView
from pathlib import Path


def isNetrcExists():
    netrcPath = Path.home() / ".netrc"

    if not netrcPath.exists():
        username = "benbaron2004"
        password = "Jonbeneden1."
        content = f"""machine urs.earthdata.nasa.gov
login {username}
password {password}
"""

        try:
            with open(netrcPath, "w") as f:
                f.write(content)
            os.chmod(netrcPath, 0o600)
            print(f".netrc file created at {netrcPath}")
        except Exception as e:
            print(f"failed to create .netrc: {e}")
    else:
        print(".netrc file already exists")


isNetrcExists()


class Gui:
    def __init__(self):
        ctk.set_appearance_mode("dark")
        self.root = ctk.CTk()
        self.root.geometry(f"{self.root.winfo_screenwidth()}x{self.root.winfo_screenheight()}+0+0")
        self.root.title("Ionosphere maps")

        self.tecCanvas, self.kpIndexCanvas, self.klobucharCanvas, self.deltaCanvas = None, None, None, None
        self.animationRun, self.animationId = False, None
        self.day, self.year = None, None
        self.mapChoice = ctk.StringVar(value="IGS map")
        self.mapManuAdded = False

        self.downloadDir = os.path.join(os.getcwd(), "downloads")
        os.makedirs(self.downloadDir, exist_ok=True)

        self.buildWindow()
        self.root.mainloop()

    def buildWindow(self):
        self.root.grid_columnconfigure(0, weight=0)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=0)
        self.root.grid_rowconfigure(1, weight=0)
        self.root.grid_rowconfigure(2, weight=1)

        self.buttonsFrame = ctk.CTkFrame(self.root)
        self.buttonsFrame.grid(row=0, column=0, sticky="ns", pady=10, padx=10)

        self.startButton = ctk.CTkButton(self.buttonsFrame, text="show Maps", command=self.showMaps, height=100)
        self.startButton.grid(row=0, column=0, pady=10, sticky="ew")

        self.mapOption = ctk.CTkOptionMenu(
            self.buttonsFrame, variable=self.mapChoice, values=["IGS map", "UPC map", "ESA map"]
        )
        self.mapOption.grid(row=1, column=0, pady=5)

        self.date = CTkDatePicker(self.buttonsFrame)
        self.date.grid(row=3, column=0, pady=10)
        self.date.set_date_format("%Y-%m-%d")
        self.date.set_allow_manual_input(False)

        self.animationButton = ctk.CTkButton(
            self.buttonsFrame, text="start Animation", fg_color="green", command=self.animations, height=50
        )
        self.animationButton.grid(row=4, column=0, pady=30, sticky="ew")

        self.slider = ctk.CTkSlider(self.buttonsFrame, from_=0, to=95, command=self.updateMap, state="disabled")
        self.slider.grid(row=5, column=0, pady=20)

        self.time = ctk.CTkLabel(self.buttonsFrame, text=f"Time: 12:00")
        self.time.grid(row=6, column=0, pady=10)

        self.errorLabel = ctk.CTkLabel(self.buttonsFrame, text="", text_color="red", wraplength=180)
        self.errorLabel.grid(row=7, column=0, pady=10)

        self.tabView = ctk.CTkTabview(self.root)
        self.tabView.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        self.tecTab = self.tabView.add("TEC")
        self.kpindexTab = self.tabView.add("Kp Index")
        self.klobucharTab = self.tabView.add("Klobuchar")
        self.deltaTab = self.tabView.add("Delta TEC-klobuchar")

        self.tecFrame = ctk.CTkFrame(self.tecTab, fg_color="gray")
        self.tecFrame.pack(expand=True, fill="both", padx=10, pady=10)

        self.kpIndexFrame = ctk.CTkFrame(self.kpindexTab, fg_color="gray")
        self.kpIndexFrame.pack(expand=True, fill="both", padx=10, pady=10)

        self.klobucharFrame = ctk.CTkFrame(self.klobucharTab, fg_color="gray")
        self.klobucharFrame.pack(expand=True, fill="both", padx=10, pady=10)

        self.deltaFrame = ctk.CTkFrame(self.deltaTab, fg_color="gray")
        self.deltaFrame.pack(expand=True, fill="both", padx=10, pady=10)

        self.maplabel = ctk.CTkLabel(self.root, text="right click to choose location", text_color="white", anchor="w")
        self.maplabel.grid(row=1, column=1, sticky="w", padx=10, pady=(10, 0))

        self.mapWidget = TkinterMapView(self.root, width=400, height=200)
        self.mapWidget.grid(row=2, column=1, sticky="w", padx=10, pady=(0, 10))
        self.mapWidget.set_position(34, 35)
        self.mapWidget.set_zoom(2)
        self.mapWidget.canvas.bind("<Button-3>", self.mapWidget.mouse_right_click)
        self.mapWidget.set_tile_server("https://mt0.google.com/vt/lyrs=m&hl=en&x={x}&y={y}&z={z}&s=Ga")

    def showMaps(self):
        self.showTec()
        self.showKpindex()
        self.showKlobuchar()

        self.showDelta()

        self.mapWidget.delete_all_marker()
        if not self.mapManuAdded:
            self.mapWidget.add_right_click_menu_command(label="show this area", command=self.showArea, pass_coords=True)
        self.mapManuAdded = True

    def showTec(self):
        fileName = self.calcFileName()
        url = f"https://cddis.nasa.gov/archive/gnss/products/ionex/{self.year}/{self.day}/{fileName + ".gz"}"
        path = self.downloadAndExtract(url=url, saveFileName=fileName)
        self.tecMaps = self.getTecData(path)

        if self.tecCanvas is not None:
            self.tecCanvas.get_tk_widget().destroy()
            self.tecCanvas = None

        title = f"{self.mapChoice.get()} - {self.selectedDate}"
        self.tecCanvas, self.meshTec = self.createCanvas(
            self.tecFrame, title, [-180, 180, -90, 90], self.tecMaps[0] / 10
        )
        self.slider.configure(state="normal")

    def calcFileName(self):
        self.selectedDate = self.date.get_date()
        dateObj = datetime.strptime(self.selectedDate, "%Y-%m-%d")
        self.year = dateObj.year
        self.day = dateObj.timetuple().tm_yday
        self.day = f"{self.day:03d}"
        mapChoice = self.mapChoice.get().split()[0]
        fileName = f"{mapChoice}0OPSRAP_{self.year}{self.day}0000_01D_02H_GIM.INX"
        return fileName

    def downloadAndExtract(self, url, saveFileName):
        zipPath = os.path.join(self.downloadDir, saveFileName + ".gz")
        savePath = os.path.join(self.downloadDir, saveFileName)

        try:
            self.errorLabel.configure(text="")
            if os.path.exists(savePath):
                return savePath
            with requests.Session() as session:
                response = session.get(url, stream=True, timeout=5)
                if response.status_code != 200:
                    self.errorLabel.configure(text=f"No file for date {self.selectedDate}")
                    return None
                with open(zipPath, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
            with gzip.open(zipPath, "rb") as zipFile, open(savePath, "wb") as saveFile:
                shutil.copyfileobj(zipFile, saveFile)
            os.remove(zipPath)
            return savePath
        except Exception as e:
            print(f"Error downloading: {e}")
            return None

    def getTecData(self, fileNamePath):
        mapsData = []
        currentRow, currentMap = [], []

        with open(fileNamePath, "r") as file:
            inBlock = False
            for line in file:
                if "START OF TEC MAP" in line:
                    if currentMap:
                        mapsData.append(np.array(currentMap))
                    currentMap = []
                elif "END OF TEC MAP" in line:
                    if currentRow:
                        currentMap.append(currentRow)
                    currentRow = []
                elif "LAT/LON1/LON2/DLON/H" in line:
                    if currentRow:
                        currentMap.append(currentRow)
                    currentRow = []
                    inBlock = True
                elif inBlock:
                    try:
                        nums = [int(num) for num in line.split()]
                        currentRow.extend(nums)
                    except ValueError:
                        continue
            if currentMap:
                mapsData.append(np.array(currentMap))
                mapsData[12] = mapsData[12][:71, :73]
        return self.interpolate(mapsData)

    def interpolate(self, mapsData):
        allMaps = []
        for i in range(len(mapsData) - 1):
            allMaps.append(mapsData[i])
            for j in range(1, 8):
                alpha = j / 8
                interpolatedMap = (1 - alpha) * mapsData[i] + alpha * mapsData[i + 1]
                allMaps.append(interpolatedMap)
        return allMaps

    # animations
    def animations(self):
        if not self.animationRun:
            self.animationRun = True
            self.animationButton.configure(text="pause", fg_color="red")
            self.startAnimation(int(self.slider.get()))
        else:
            self.animationRun = False
            self.animationButton.configure(text="start", fg_color="green")
            self.stopAnimation()

    def startAnimation(self, index):
        if not self.animationRun:
            return
        if index > len(self.tecMaps) - 1:
            index = 0
        self.slider.set(index)
        self.updateMap(index)
        self.animationId = self.root.after(50, lambda: self.startAnimation(index + 1))

    def stopAnimation(self):
        if self.animationId is not None:
            self.root.after_cancel(self.animationId)
            self.animationId = None

    def updateMap(self, index):
        index = int(index)
        self.meshTec.set_array((self.tecMaps[index] / 10).flatten())
        self.tecCanvas.draw()
        self.meshKlobuchar.set_array((self.klobucharMaps[int(index - 1)]))
        self.klobucharCanvas.draw()
        self.meshDelta.set_array((self.deltaMaps[index] / 10).flatten())
        self.deltaCanvas.draw()

        hours, minutes = divmod(index * 15, 60)
        self.time.configure(text=f"Time: {hours:02}:{minutes:02}")

    def showKpindex(self):
        if self.kpIndexCanvas is not None:
            self.kpIndexCanvas.get_tk_widget().destroy()
            self.kpIndexCanvas = None
            figKPindex, axKpindex = None, None

        selectedDate = datetime.strptime(self.selectedDate, "%Y-%m-%d").date()
        startDate = selectedDate - timedelta(days=3)
        endDate = selectedDate + timedelta(days=3)
        dateRange = [startDate + timedelta(days=i) for i in range((endDate - startDate).days + 1)]

        matrixValues = self.downloadKpData(startDate, endDate)

        times = ["00:00", "03:00", "06:00", "09:00", "12:00", "15:00", "18:00", "21:00"]
        barWidth = 0.1

        figKPindex, axKpindex = plt.subplots(
            figsize=(self.kpIndexFrame.winfo_width() / 100, self.kpIndexFrame.winfo_height() / 100), dpi=100
        )
        br = np.arange(len(dateRange))
        norm = Normalize(vmin=0, vmax=9)
        cmap = matplotlib.colormaps["RdYlGn_r"]

        for i, hour in enumerate(times):
            barPositions = [x + barWidth * i for x in br]
            hoursValues = [matrixValues[day][i] for day in range(len(dateRange))]
            colors = [cmap(norm(v)) for v in hoursValues]
            axKpindex.bar(barPositions, hoursValues, color=colors, edgecolor="grey", width=barWidth, label=hour)

        axKpindex.set_ylabel("Kp Index")
        axKpindex.set_xticks([r + barWidth * 3.5 for r in br])
        axKpindex.set_xticklabels([d.strftime("%b %d") for d in dateRange])
        axKpindex.set_title(f"kp index - dates {startDate} to {endDate}")
        axKpindex.set_ylim(0, 9)
        axKpindex.legend(title="Hours", handlelength=0, handletextpad=1, loc="upper right", bbox_to_anchor=(1.35, 1.1))

        sm = ScalarMappable(norm=norm, cmap=cmap)
        figKPindex.colorbar(sm, ax=axKpindex, label="Kp Index")

        self.kpIndexCanvas = FigureCanvasTkAgg(figKPindex, master=self.kpIndexFrame)
        self.kpIndexCanvas.draw()
        self.kpIndexCanvas.get_tk_widget().pack(expand=True, fill="both")
        plt.close(figKPindex)

    def downloadKpData(self, startDate, endDate):
        weekValues = []
        dayValues = []
        url = f"https://kp.gfz.de/kpdata?startdate={startDate}&enddate={endDate}&format=kp2#kpdatadownload-143"
        try:
            with urllib.request.urlopen(url) as response:
                for line in response:
                    line = line.decode("utf-8").strip()
                    lineParts = line.split()
                    dayValues.append(float(lineParts[7]))

                    if len(dayValues) == 8:
                        weekValues.append(dayValues)
                        dayValues = []

            if endDate >= date.today():
                missingDays = (endDate - date.today()).days + 1
                forecast = self.calcforecastDates()
                for i in range(missingDays):
                    weekValues.append(forecast[i])
        except urllib.error.URLError:
            self.errorLabel.configure(text="error to get the data - no connection")
        return weekValues

    def calcforecastDates(self):
        day1, day2, day3 = [], [], []
        url = "https://services.swpc.noaa.gov/text/3-day-forecast.txt"

        with urllib.request.urlopen(url) as response:
            for line in response:
                line = line.decode("utf-8").strip()
                if line.startswith(
                    ("00-03UT", "03-06UT", "06-09UT", "09-12UT", "12-15UT", "15-18UT", "18-21UT", "21-00UT")
                ):
                    lineParts = line.split()
                    parts = [part for part in lineParts if part.replace(".", "").isdigit()]
                    [day.append(float(parts[i])) for i, day in enumerate([day1, day2, day3])]
                if "Rationale" in line:
                    break
        return [day1, day2, day3]

    def showKlobuchar(self):
        files = self.calcKlobucharFileNames()

        strYear = str(self.year)
        baseurl = f"https://cddis.nasa.gov/archive/gnss/data/daily/{self.year}/{self.day}/{strYear[2:]}n"
        for file in files:
            url = f"{baseurl}/{file}"
            saveFileName = file[:-3]

            path = self.downloadAndExtract(url=url, saveFileName=saveFileName)
            if path:
                break
        alpha, beta = self.readKlobucharData(path)
        times = self.gpsSeconesByDate(self.selectedDate)

        self.klobucharMaps = []
        for seconds in times:
            klobucharMap = self.calcKlobuchar(seconds, alpha, beta)
            self.klobucharMaps.append(klobucharMap / 0.16)

        self.showKlobucharMap(self.klobucharMaps[0])

    def calcKlobucharFileNames(self):
        fileStartNames = []
        with open("stationsName.txt", "r", encoding="utf-8") as r:
            fileStartNames = [line.strip() for line in r]

        files = []
        for filestart in fileStartNames:
            filename = f"{filestart}_R_{self.year}{self.day}0000_01D_GN.rnx.gz"
            files.append(filename)
        return files

    def readKlobucharData(self, fileNamePath):
        alpha, beta = [], []
        with open(fileNamePath, "r") as file:
            for line in file:
                values = line.split()
                if "GPSA" in line:
                    alpha = [float(v) for v in values[1:5]]
                elif "GPSB" in line:
                    beta = [float(v) for v in values[1:5]]
                if alpha and beta:
                    break
        return alpha, beta

    def gpsSeconesByDate(self, selectedDate):
        date = datetime.strptime(selectedDate, "%Y-%m-%d")
        gpsStart = datetime(1980, 1, 6)

        deltaDays = (date - gpsStart).days
        dayOfWeek = deltaDays % 7
        startSecondsOfDay = dayOfWeek * 86400
        return [startSecondsOfDay + i * 900 for i in range(96)]

    def createWorldPoints(self):
        lat = np.linspace(87.5, -87.5, 71) / 180
        lon = np.linspace(-180, 180, 73) / 180
        return np.meshgrid(lon, lat)

    def calcKlobuchar(self, seconds, alpha, beta):
        lonPoints, latPoints = self.createWorldPoints()
        elevation = np.radians(90)
        azimuth = np.radians(0)
        earthCentredAngle = (0.0137 / (elevation / np.pi + 0.11)) - 0.022
        latIPP = latPoints + earthCentredAngle * np.cos(azimuth)
        latIPP = np.clip(latIPP, -0.416, 0.416)
        lonIPP = lonPoints + (earthCentredAngle * np.sin(azimuth) / np.cos(np.radians(latIPP)))
        geomagneticLatIPP = latIPP + (0.064 * np.cos(lonIPP * np.pi - 1.617))
        localTimes = (43200 * lonIPP + seconds) % 86400
        A = sum(alpha[i] * geomagneticLatIPP**i for i in range(4))
        A = np.maximum(A, 0)
        P = sum(beta[i] * geomagneticLatIPP**i for i in range(4))
        P = np.maximum(P, 72000)
        Xi = (2 * np.pi * (localTimes - 50400)) / P
        F = 1.0 + 16.0 * (0.53 - (np.radians(elevation))) ** 3
        ionoDelay = np.where(np.abs(Xi) <= 1.57, (5e-9 + A * (1 - (Xi**2 / 2) + (Xi**4 / 24))) * F, 5e-9 * F)
        return ionoDelay * 299792458

    def showKlobucharMap(self, map):
        if self.klobucharCanvas is not None:
            self.klobucharCanvas.get_tk_widget().destroy()
            self.klobucharCanvas

        title = f"Klobuchar model - {self.selectedDate}"
        self.klobucharCanvas, self.meshKlobuchar = self.createCanvas(
            self.klobucharFrame, title, [-180, 180, -90, 90], map
        )

    def createCanvas(self, frame, title, extent, data, cmap="jet", label="tecu"):
        fig, ax = plt.subplots(
            figsize=(frame.winfo_width() / 100, frame.winfo_height() / 100),
            dpi=100,
            subplot_kw={"projection": ccrs.PlateCarree()},
        )
        ax.set_title(title)
        ax.set_extent(extent, crs=ccrs.PlateCarree())
        ax.add_feature(cfeature.BORDERS, edgecolor="black", linewidth=0.8)
        ax.add_feature(cfeature.COASTLINE, edgecolor="black", linewidth=0.6)
        mesh = ax.pcolormesh(
            np.linspace(-180, 180, 73), np.linspace(87.5, -87.5, 71), data, cmap=cmap, shading="gouraud", alpha=0.9
        )
        fig.colorbar(mesh, ax=ax, orientation="vertical", label=label, pad=0.080)
        ax.gridlines(draw_labels=True, color="black", linewidth=0.5, linestyle="--")
        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        plt.close(fig)
        return canvas, mesh

    def showArea(self, coords):
        lat, lon = coords
        self.mapWidget.delete_all_marker()
        self.mapWidget.set_marker(lat, lon, text="my choice")
        extent = [lon - 10, lon + 10, lat - 5, lat + 5]

        self.tecCanvas.get_tk_widget().destroy()
        title = f"{self.mapChoice.get()} - {self.selectedDate}"
        self.tecCanvas, self.meshTec = self.createCanvas(
            self.tecFrame, title=title, extent=extent, data=self.tecMaps[0] / 10
        )
        self.klobucharCanvas.get_tk_widget().destroy()
        title = f"klobuchar map - {self.selectedDate}"
        self.klobucharCanvas, self.meshKlobuchar = self.createCanvas(
            self.klobucharFrame, title=title, extent=extent, data=self.klobucharMaps[0]
        )
        self.deltaCanvas.get_tk_widget().destroy()
        title = f"delta between tec and klobuchar {self.mapChoice.get()} - {self.selectedDate}"
        self.deltaCanvas, self.meshDelta = self.createCanvas(
            self.deltaFrame, title=title, extent=extent, data=self.deltaMaps[0] / 10
        )

    def showDelta(self):
        self.deltaMaps = np.array(self.tecMaps) - np.array(self.klobucharMaps)
        if self.deltaCanvas is not None:
            self.deltaCanvas.get_tk_widget().destroy()
            self.deltaCanvas = None

        title = f"delta between tec and klobuchar {self.mapChoice.get()} - {self.selectedDate}"
        self.deltaCanvas, self.meshDelta = self.createCanvas(
            self.deltaFrame, title, [-180, 180, -90, 90], self.tecMaps[0] / 10
        )


if __name__ == "__main__":
    window = Gui()
