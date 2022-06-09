import matplotlib.pyplot as plt
import numpy as np
from numpy import FPE_DIVIDEBYZERO, array, linalg, ndarray
import rt1plotpy
from typing import Optional, Union,Tuple,Callable,List
import time 
import math
from tqdm import tqdm
import scipy.linalg as linalg
from numba import jit
import warnings
from dataclasses import dataclass
import itertools
import scipy.sparse as sparse
import pandas as pd
import os
from rt1plotpy import frame

__all__ = ['Kernel2D_scatter', 'Kernel2D_grid', 'Kernel1D']

class Kernel2D_scatter(rt1plotpy.frame.Frame):
    def __init__(self,
        dxf_file  :str,
        show_print:bool=False
        ) -> None:
        
        """
        import dxf file

        Parameters
        ----------
        dxf_file : str
            Path of the desired file.
        show_print : bool=True,
            print property of frames
        Note
        ----
        dxf_file is required to have units of (mm).
        """

        super().__init__(dxf_file,show_print)
        self.im_shape: Union[Tuple[int,int],None] = None
        print('you have to "create_induced_point()" or "set_induced_point()" next.')

    def create_induced_point(self,
        z_grid: np.ndarray,
        r_grid: np.ndarray,
        length_sq_fuction: Callable[[float,float],None],
        ) -> Tuple[np.ndarray,np.ndarray]:     
        """
        create induced point based on length scale function

        Parameters
        ----------
        z_grid: np.ndarray,
        r_grid: np.ndarray,
        length_sq_fuction: Callable[[float,float],None],

        Reuturns
        ----------
        zI: np.ndarray,
        rI: np.ndarray,  
        """
        
        if not 'r_bound'  in dir(self):
            print('set_bound() is to be done in advance!')
            return
        
        rr,zz = np.meshgrid(r_grid,z_grid)
        length_sq = length_sq_fuction(rr,zz)
        mask, _ = self.grid_input(R=r_grid, Z=z_grid)
        mask = (np.nan_to_num(mask) == 1)

        rI, zI = np.zeros(1),np.zeros(1)
        rI[0], zI[0] = r_grid[0],z_grid[0]
        is_short = True
        for i, zi in enumerate(tqdm(z_grid)):
            for j, ri in enumerate(r_grid):
                if mask[i,j]:
                    db_min = d2min(ri,zi,self.r_bound, self.z_bound)

                    if rI.size < 500:
                        d2_min = d2min(ri,zi,rI,zI)
                    else:
                        d2_min = d2min(ri,zi,rI[-500:],zI[-500:])

                    if length_sq[i,j] > min(db_min,d2_min):
                        is_short = True
                    elif is_short:
                        is_short = False
                        rI = np.append(rI,ri)
                        zI = np.append(zI,zi)                    

        rI,zI = rI[1:], zI[1:]

        self.zI, self.rI = zI, rI
        self.nI = rI.size
        self.length_scale_sq: Callable[[float,float],float] = length_sq_fuction 
        return zI, rI

    def set_induced_point(self,
        zI: np.ndarray,
        rI: np.ndarray,
        length_sq_fuction: Callable[[float,float],float],
        ) :     
        """
        set induced point by input existing data

        Parameters
        ----------
        zI: np.ndarray,
        rI: np.ndarray,
        length_sq_fuction: Callable[[float,float],None]
        """
        self.zI, self.rI = zI, rI
        self.nI = rI.size
        self.length_scale_sq: Callable[[float,float],float] = length_sq_fuction 
    
    def length_scale(self,r,z):
        return np.sqrt(self.length_scale_sq(r,z))
    
    def set_grid_interface(self,
        z_plot   : np.ndarray,
        r_plot   : np.ndarray,
        z_plot_HD: np.ndarray=[None],
        r_plot_HD: np.ndarray=[None],
        scale    :int = 1
        )  :
        
        if not 'rI'  in dir(self):
            print('set_induced_point() or create_induced_point() is to be done in advance')
            return
        s = scale
        lI = self.length_scale(self.rI,self.zI)
        KII = GibbsKer(x0=self.rI, x1=self.rI, y0=self.zI, y1=self.zI, lx0=lI*s, lx1=lI*s, isotropy=True)
        self.KII_inv = np.linalg.inv(KII+1e-5*np.eye(self.nI))
        
        self.mask1,self.extent1 = self.grid_input(r_plot,z_plot,isnt_print=True)

        Z_plot,R_plot  = np.meshgrid(z_plot, r_plot, indexing='ij')

        lp = self.length_scale(R_plot.flatten(), Z_plot.flatten())
        lp = np.nan_to_num(lp,nan=1)
        self.Kps = GibbsKer(x0 = R_plot.flatten(),x1 = self.rI, y0 = Z_plot.flatten(), y1 =self.zI, lx0=lp*s, lx1=lI*s, isotropy=True)
        
        if z_plot_HD[0] == None:
            return 
        else:
            dr, dz = r_plot[1]-r_plot[0],   z_plot[1]-z_plot[0]

            Kr1r1 = SEKer(x0=r_plot ,x1=r_plot, y0=0, y1=0, lx=dr, ly=1)
            Kz1z1 = SEKer(x0=z_plot ,x1=z_plot, y0=0, y1=0, lx=dz, ly=1)
            
            λ_r1, self.Q_r1 = np.linalg.eigh(Kr1r1)
            λ_z1, self.Q_z1 = np.linalg.eigh(Kz1z1)

            self.mask_HD,self.extent_HD = self.grid_input(r_plot_HD,z_plot_HD)

            self.KrHDr1 = SEKer(x0=r_plot_HD,x1=r_plot, y0=0, y1=0, lx=dr, ly=1)
            self.KzHDz1 = SEKer(x0=z_plot_HD,x1=z_plot, y0=0, y1=0, lx=dz, ly=1)

            self.Λ_z1r1_inv = 1 / np.einsum('i,j->ij',λ_z1,λ_r1)


@jit
def d2min(x,y,xs,ys):
    x_tau2 = (x- xs)**2
    y_tau2 = (y- ys)**2
    d2_min = np.min(x_tau2 + y_tau2)
    return d2_min

def SEKer(x0,x1,y0,y1,lx,ly):
    X = np.meshgrid(x0,x1,indexing='ij')
    Y = np.meshgrid(y0,y1,indexing='ij')
    return np.exp(- 0.5*( ((X[0]-X[1])/lx)**2 + ((Y[0]-Y[1])/ly)**2) )

def GibbsKer(
    x0 : np.ndarray,
    x1 : np.ndarray,
    y0 : np.ndarray,
    y1 : np.ndarray,
    lx0: np.ndarray,
    lx1: np.ndarray,
    ly0: Union[np.ndarray,bool]=None,
    ly1: Union[np.ndarray,bool]=None,
    isotropy: bool = False
    ) -> np.ndarray:  

    X  = np.meshgrid(x0,x1,indexing='ij')
    Y  = np.meshgrid(y0,y1,indexing='ij')
    Lx = np.meshgrid(lx0,lx1,indexing='ij')
    Lxsq = Lx[0]**2+Lx[1]**2 

    if isotropy:
        return 2*Lx[0]*Lx[1]/Lxsq *np.exp( -   ((X[0]-X[1])**2  +(Y[0]-Y[1])**2 )/ Lxsq )

    else:        
        Ly = np.meshgrid(ly0,ly1,indexing='ij')
        Lysq = Ly[0]**2+Ly[1]**2 
        return np.sqrt(2*Lx[0]*Lx[1]/Lxsq)*np.sqrt(2*Ly[0]*Ly[1]/Lysq)*np.exp( -   (X[0]-X[1])**2 / Lxsq  - (Y[0]-Y[1])**2 / Lysq )

@jit
def GibbsKer_fast(
    x0 : np.ndarray,
    x1 : np.ndarray,
    y0 : np.ndarray,
    y1 : np.ndarray,
    lx0: np.ndarray,
    lx1: np.ndarray,
    ) -> np.ndarray:  

    X  = np.meshgrid(x0,x1,indexing='ij')
    Y  = np.meshgrid(y0,y1,indexing='ij')
    Lx = np.meshgrid(lx0,lx1,indexing='ij')
    Lxsq = Lx[0]**2+Lx[1]**2 

    return 2*Lx[0]*Lx[1]/Lxsq *np.exp( -   ((X[0]-X[1])**2  +(Y[0]-Y[1])**2 )/ Lxsq )

class Kernel1D():
    pass 

class Kernel2D_grid():
    pass 