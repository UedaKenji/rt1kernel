import matplotlib.pyplot as plt 
import numpy as np
import rt1plotpy

params = {
        'font.family'      : 'Times New Roman', # font familyの設定
        'mathtext.fontset' : 'stix'           , # math fontの設定
        "font.size"        : 15               , # 全体のフォントサイズが変更されます。
        'xtick.labelsize'  : 12                , # 軸だけ変更されます。
        'ytick.labelsize'  : 12               , # 軸だけ変更されます
        'xtick.direction'  : 'in'             , # x axis in
        'ytick.direction'  : 'in'             , # y axis in 
        'axes.linewidth'   : 1.0              , # axis line width
        'axes.grid'        : True             , # make grid
        }
        
plt.rcParams.update(**params)

rt1_ax_kwargs = {'xlim'  :(0,1.1),
                 'ylim'  :(-0.7,0.7), 
                 'aspect': 'equal'
                }

n0 = 2#25.99e16*0.8/2
a  = 1.348
b  = 0.5
rmax = 0.4577

def gaussian(r,z,n0=n0,a=a,b=b,rmax=rmax):
    psi = rt1plotpy.mag.psi(r,z)
    br, bz = rt1plotpy.mag.bvec(r,z)
    b_abs = np.sqrt(br**2+bz**2)
    psi_rmax = rt1plotpy.mag.psi(rmax,0)
    psi0 = rt1plotpy.mag.psi(1,0)
    b0 = rt1plotpy.mag.b0(r,z)
    return n0 * np.exp(-a*(psi-psi_rmax)**2/psi0**2)*(b_abs/b0)**(-b) 

def Length_scale_sq(r,z):
    return 0.0001/(gaussian(r,z)+ 0.05)

def Length_scale(r,z):
    return np.sqrt( Length_scale_sq(r,z))