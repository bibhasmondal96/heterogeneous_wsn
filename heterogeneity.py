import threading

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

import tkinter as tk
from tkinter import ttk
from tkinter import simpledialog,messagebox,Listbox

from PIL import ImageGrab

from network import Network

class Heterogeneity(tk.Tk):

    def __init__(self, *args, **kwargs):
        tk.Tk.__init__(self, *args, **kwargs)
        tk.Tk.iconbitmap(self, default="icon.ico")
        tk.Tk.wm_title(self, "Heterogeneity")

        self.progress = ttk.Progressbar(self, orient="horizontal", mode="determinate" ,value="0")
        self.progress.pack(side="top",fill="x",padx=5,pady=5)
        self.progress.grid_rowconfigure(0, weight=1)
        self.progress.grid_columnconfigure(0, weight=1)

        container = tk.Frame(self)
        container.pack(side="left", fill="both", expand = True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frame1 = GraphView(container, self)
        self.frame1.grid(row=0, column=0,sticky="nsew")
        self.frame2 = ListView(container, self)
        self.frame2.grid(row=0, column=2,sticky="nsew")
        self.frame3 = ControlView(container,self)
        self.frame3.grid(row=0, column=3,sticky="nsew")

        self.networks = []

class ControlView(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self,parent)
        self.controller = controller
        button1 = ttk.Button(self, text="Create netrork", command=lambda: self.network())
        button1.pack(pady=10,padx=10)

        button2 = ttk.Button(self, text="Start season", command=self.season)
        button2.pack(pady=10,padx=10)

        button3 = ttk.Button(self, text="Energy Stat", command=self.allNetworkStatus)
        button3.pack(pady=10,padx=10)

        button4 = ttk.Button(self, text="Network Structure", command=self.networkStruct)
        button4.pack(pady=10,padx=10)

        button5 = ttk.Button(self, text="Neighbour Stat", command=self.neighbourStat)
        button5.pack(pady=10,padx=10)

        button6 = ttk.Button(self, text="Lorentz Curve", command=self.lorentzCureve)
        button6.pack(pady=10,padx=10)

        button7 = ttk.Button(self, text="Reset", command=self.reset)
        button7.pack(pady=10,padx=10)

        button8 = ttk.Button(self, text="Screenshots", command=self.screenshot)
        button8.pack(pady=10,padx=10)

    def screenshot(self):
        img = ImageGrab.grab()
        img.show()

    def reset(self):
        self.controller.progress['value'] = 0
        self.controller.frame1.fig.clear()
        self.controller.frame1.canvas.draw()
        self.controller.networks = []
        self.controller.frame2.listbox.delete(0,'end')
        self.controller.progress['value'] = 100

    def allNetworkStatus(self):
        self.controller.progress['value'] = 0
        x = []
        y = []
        parent = self.controller.frame2
        listbox = parent.listbox
        inds = listbox.curselection()
        networks = sorted(map(self.controller.networks.__getitem__,inds),key = lambda x:len(x.nodes))
        for network in networks:
            y.append(network.avgPowConsumedPerSeason)
            x.append(len(network.nodes))
        fig = self.controller.frame1.fig
        fig.clear()
        plt = fig.add_subplot(111)
        plt.plot(x,y)
        plt.set_xlabel('Nodes')
        plt.set_ylabel('Energy Consumed(%)')
        plt.set_title("Energy Consumed vs Nodes", fontsize='large')
        plt.set_xticks(x,x)
        plt.grid(True)
        self.controller.frame1.canvas.draw()
        self.controller.progress['value'] = 100

    def networkStruct(self):
        self.controller.frame1.draw("scatterPlot")

    def neighbourStat(self):
        self.controller.frame1.draw("neighboursStatusStackPlot")

    def lorentzCureve(self):
        self.controller.frame1.draw("lorentzCurve")


    def network(self):
        self.controller.progress['value'] = 0
        parent = self.controller.frame2
        no = simpledialog.askinteger("Node", "Enter the no of node.", parent=parent,initialvalue=20,minvalue=2, maxvalue=500)
        if no:parent.insert(no)
        self.controller.progress['value'] = 100


    def season(self):
        parent = self.controller.frame2
        listbox = parent.listbox
        inds = listbox.curselection()
        if inds:
            no = simpledialog.askinteger("Season", "Enter the no of season.", parent=parent,initialvalue=1,minvalue=0, maxvalue=100)
            def job():
                self.controller.progress['value'] = 0
                for i in range(len(inds)):
                    for j in range(no):
                        self.controller.networks[inds[i]].startSeason(1,int(listbox.get(inds[i])[9:-1]))
                        self.controller.progress['value'] = (i*no+j+1)*100/(no*len(inds))
            if no:threading.Thread(target=job,args=()).start()
        else:
            messagebox.showwarning("Warning","Please select a network from list")


class ListView(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        self.listbox = Listbox(self,selectbackground="green",selectmode='extended')
        self.listbox.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True,padx=10,pady=10)
    def insert(self,value):
        self.controller.networks.append(Network(value))
        self.listbox.insert(self.listbox.size(),"Network (%s)"%value)


class GraphView(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        self.fig = Figure(figsize=(5,5), dpi=100)

        self.canvas = FigureCanvasTkAgg(self.fig, self)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH,expand=True,padx=10,pady=10)

        toolbar = NavigationToolbar2Tk(self.canvas, self)
        toolbar.update()
        self.canvas._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.fig.canvas.mpl_connect('pick_event', self.onPick)

    def draw(self,plotFuncName,**kwargs):
        self.controller.progress['value'] = 0
        self.fig.clear()
        plt = self.fig.add_subplot(111)
        parent = self.controller.frame2
        listbox = parent.listbox
        ind = listbox.curselection()
        if ind:
            if len(ind)==1:
                getattr(self.controller.networks[ind[0]],plotFuncName)(plt,**kwargs)
                self.canvas.draw()
            else:
                messagebox.showwarning("Warning","Please select one item")
        else:
            messagebox.showwarning("Warning","Please select a network from list")
        self.controller.progress['value'] = 100

    def onPick(self,event):
        self.draw("neighbourPlot",node = event.ind[0]+1)

app = Heterogeneity()
app.mainloop()
