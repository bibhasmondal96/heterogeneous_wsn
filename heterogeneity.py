import threading
import matplotlib
matplotlib.use("TkAgg")
import tkinter as tk
from tkinter import ttk
from PIL import ImageGrab
from network import Network
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk

class Heterogeneity(tk.Tk):

    initial_node_power = 20
    dist_range = [0,50]
    ip = '127.0.0.1'
    start_port = 8000
    print_func = print

    def __init__(self, *args, **kwargs):
        tk.Tk.__init__(self, *args, **kwargs)
        tk.Tk.iconbitmap(self, default="icon.ico")
        tk.Tk.wm_title(self, "Heterogeneity")
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.progress = ttk.Progressbar(self, orient="horizontal", mode="determinate" ,value="0")
        self.progress.pack(side="top",fill="x",padx=5,pady=5)
        self.progress.grid_rowconfigure(0, weight=1)
        self.progress.grid_columnconfigure(0, weight=1)
        # Create Tab Control
        tabControl = ttk.Notebook(self)
        # Create a tab
        container = ttk.Frame(tabControl)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        # Add the tab
        tabControl.add(container, text='Home')
        # Create a tab
        container = ttk.Frame(tabControl)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        # Add the tab
        tabControl.add(container, text='Logs')
        # Pack to make visible
        tabControl.pack(expand=2, fill="both")

        tabs = list(tabControl.children.values())
        self.frame1 = GraphView(tabs[0], self)
        self.frame1.grid(row=0, column=0,sticky="nsew")
        self.frame2 = ListView(tabs[0], self)
        self.frame2.grid(row=0, column=2,sticky="nsew")
        self.frame3 = ControlView(tabs[0],self)
        self.frame3.grid(row=0, column=3,sticky="nsew")

        self.frame4 = LogView(tabs[1],self)
        self.frame4.grid(row=0, column=0,sticky="nsew")

        self.networks = []
        self.print_func = self.frame4.print

    def on_closing(self):
        for network in self.networks:
            try:network.shutdown()
            except:pass
        self.destroy()

class ControlView(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self,parent)
        self.controller = controller
        pad = {'pady':5,'padx':5,'expand':1}

        var = tk.StringVar(self)
        var.set('RPL')
        option = tk.OptionMenu(self, var, "RPL", "AODV")
        option.pack(**pad)

        button1 = ttk.Button(self,text="Create netrork", command=lambda: self.network())
        button1.pack(**pad)

        button2 = ttk.Button(self, text="Start season", command=self.season)
        button2.pack(**pad)

        button3 = ttk.Button(self, text="Start session until first death", command=self.run_until_first_death)
        button3.pack(**pad)

        button4 = ttk.Button(self, text="Networks energy status", command=self.plot_netrorks_energy)
        button4.pack(**pad)

        button5 = ttk.Button(self, text="Neighbours connection", command=self.plt_neighbours_connection)
        button5.pack(**pad)

        button6 = ttk.Button(self, text="Destination connection", command=self.plt_dest_connection)
        button6.pack(**pad)

        button7 = ttk.Button(self, text="Lorentz curve", command=self.plt_lorentz_curve)
        button7.pack(**pad)

        button8 = ttk.Button(self, text="Max session status", command=self.plt_max_session)
        button8.pack(**pad)

        button9 = ttk.Button(self, text="Max session gini status", command=self.plt_max_gini_stat)
        button9.pack(**pad)

        button10 = ttk.Button(self, text="First death gini status", command=self.plt_death_gini_stat)
        button10.pack(**pad)

        button11 = ttk.Button(self, text="Max session energy status", command=self.plt_max_energy_stat)
        button11.pack(**pad)

        button12 = ttk.Button(self, text="First death energy status", command=self.plt_death_energy_stat)
        button12.pack(**pad)

        button13 = ttk.Button(self, text="Max session data transfer status", command=self.plt_max_msg_delivery_stat)
        button13.pack(**pad)

        button14 = ttk.Button(self, text="First death data transfer status", command=self.plt_death_msg_delivery_stat)
        button14.pack(**pad)

        button15 = ttk.Button(self, text="Reset", command=self.reset)
        button15.pack(**pad)

        button16 = ttk.Button(self, text="Screenshot", command=self.screenshot)
        button16.pack(**pad)

    def run_until_first_death(self):
        parent = self.controller.frame2
        listbox = parent.listbox
        inds = listbox.curselection()
        if inds:
            def job():
                self.controller.progress['value'] = 0
                for i in range(len(inds)):
                    network = self.controller.networks[inds[i]]
                    network.first_death()
                    self.controller.progress['value'] = (i+1)*100/len(inds)
            threading.Thread(target=job,args=()).start()
        else:
            tk.messagebox.showwarning("Warning","Please select a network from list")

    def network(self):
        self.controller.progress['value'] = 0
        parent = self.controller.frame2
        no = tk.simpledialog.askinteger("Node", "Enter the no of node.", parent=parent,initialvalue=20,minvalue=2, maxvalue=500)
        if no:parent.insert(no)
        self.controller.progress['value'] = 100


    def season(self):
        parent = self.controller.frame2
        listbox = parent.listbox
        inds = listbox.curselection()
        if inds:
            no = tk.simpledialog.askinteger("Season", "Enter the no of season.", parent=parent,initialvalue=1,minvalue=0, maxvalue=100)
            def job():
                self.controller.progress['value'] = 0
                for i in range(len(inds)):
                    for j in range(no):
                        network = self.controller.networks[inds[i]]
                        network.start_session(save_state=True)
                        self.controller.progress['value'] = (i*no+j+1)*100/(no*len(inds))
            if no:threading.Thread(target=job,args=()).start()
        else:
            tk.messagebox.showwarning("Warning","Please select a network from list")

    def plot_netrorks_energy(self):
        self.controller.progress['value'] = 0
        x = []
        y = []
        parent = self.controller.frame2
        listbox = parent.listbox
        inds = listbox.curselection()
        networks = sorted(map(self.controller.networks.__getitem__,inds),key = lambda x:len(x.nodes))
        for network in networks:
            eng_cons = [node.init_power-node.rem_power for node in network.nodes.values()]
            y.append(sum(eng_cons)/len(eng_cons))
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

    def plt_neighbours_connection(self):
        self.controller.frame1.draw("plt_neighbours_connection")

    def plt_dest_connection(self):
        self.controller.frame1.draw("plt_dest_connection")

    def plt_lorentz_curve(self):
        self.controller.frame1.draw("plt_lorentz_curve")

    def plt_max_session(self):
        self.controller.frame1.draw("plt_max_session")

    def plt_max_gini_stat(self):
        self.controller.frame1.draw("plt_gini_stat")

    def plt_death_gini_stat(self):
        self.controller.frame1.draw("plt_gini_stat",state = 'death_state')

    def plt_max_energy_stat(self):
        self.controller.frame1.draw("plt_energy_stat",projection ='3d')

    def plt_death_energy_stat(self):
        self.controller.frame1.draw("plt_energy_stat",projection ='3d',state = 'death_state')

    def plt_max_msg_delivery_stat(self):
        self.controller.frame1.draw("plt_msg_delivery_stat",projection ='3d')

    def plt_death_msg_delivery_stat(self):
        self.controller.frame1.draw("plt_msg_delivery_stat",projection ='3d',state = 'death_state')

    def reset(self):
        self.controller.progress['value'] = 0
        self.controller.frame1.fig.clear()
        self.controller.frame1.canvas.draw()
        self.controller.frame2.listbox.delete(0,'end')
        self.controller.progress['value'] = 100
        while self.controller.networks:
            network = self.controller.networks.pop(0)
            self.controller.start_port -= network.no_of_node
            try: network.shutdown()
            except: pass

    def screenshot(self):
        img = ImageGrab.grab()
        img.show()

class LogView(tk.Frame):
    def __init__(self, parent,controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        self.parent = parent
        self.vbar = ttk.Scrollbar(self)
        self.vbar.pack(side='right', fill='y')

        self.textbox = tk.Text(self,yscrollcommand = self.vbar.set)
        self.textbox.pack(side="left", fill="both", expand=True)
        self.textbox.config(state='disabled')

        self.vbar['command'] = self.textbox.yview

    def print(self,text):
        self.textbox.config(state='normal')
        self.textbox.insert('end',text)
        self.textbox.yview('end')
        self.textbox.config(state='disabled')

class ListView(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        self.listbox = tk.Listbox(self,selectbackground="green",selectmode='extended')
        self.listbox.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True,padx=10,pady=10)
    def insert(self,value):
        self.controller.networks.append(Network(value,self.controller.initial_node_power,self.controller.dist_range,self.controller.ip,self.controller.start_port,self.controller.print_func))
        self.listbox.insert(self.listbox.size(),"Network (%s)"%value)
        self.controller.start_port += value

class GraphView(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        self.fig = Figure(dpi=60)

        self.canvas = FigureCanvasTkAgg(self.fig, self)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH,expand=True,padx=10,pady=10)

        toolbar = NavigationToolbar2Tk(self.canvas, self)
        toolbar.update()
        self.canvas._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.fig.canvas.mpl_connect('pick_event', self.onPick)

    def draw(self,plt_func_name,**kwargs):
        self.controller.progress['value'] = 0
        self.fig.clear()
        plt = self.fig.add_subplot(111,projection = kwargs.pop('projection',None))
        parent = self.controller.frame2
        listbox = parent.listbox
        ind = listbox.curselection()
        if ind:
            if len(ind)==1:
                getattr(self.controller.networks[ind[0]],plt_func_name)(plt,**kwargs)
                self.canvas.draw()
            else:
                tk.messagebox.showwarning("Warning","Please select one item")
        else:
            tk.messagebox.showwarning("Warning","Please select a network from list")
        self.controller.progress['value'] = 100

    def onPick(self,event):
        self.draw("plt_node_neighbour",node_index = event.ind[0])

app = Heterogeneity()
app.mainloop()
