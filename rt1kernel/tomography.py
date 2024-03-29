from pkgutil import extend_path
import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
from numpy import FPE_DIVIDEBYZERO, array, linalg, ndarray
import rt1plotpy
from typing import Optional, Union,Tuple,Callable,List,TypeAlias
import time 
import math
from tqdm import tqdm
import scipy.linalg as linalg
from numba import jit
import warnings
from dataclasses import dataclass
import itertools
import scipy.sparse as sps
import pandas as pd
import os,sys
from .plot_utils import *  

from . import rt1kernel
from . import reflection

sys.path.insert(0,os.path.join(os.path.dirname(__file__),os.pardir))
try:
    from .. import rt1raytrace
except:
    import rt1raytrace

import sparse_dot_mkl
sys.path.pop(0)




__all__ = ['GPT_lin', 
           'GPT_av',  
           'GPT_av_dense',  
           'GPT_cis', 
           'GPT_cis_dense', 
           'GPT_log', 
           'GPT_log_grid',
           'Diag']

csr  = sps.csr_matrix


class Diag(np.ndarray):
    def __new__(cls, input_array):
        obj = np.asarray(input_array).view(cls)
        return obj

    def __matmul__(self, other):
        result = (other.T).__mul__(self)
        # 計算結果を MyMatrix インスタンスとして返す
        return (result.T).view(np.ndarray)
        
    def __rmatmul__(self, other):
        #print("カスタム行列乗算演算を実行2")
        result = other.__mul__(self)
        # 計算結果を MyMatrix インスタンスとして返す
        return (result).view(np.ndarray)
    
    
    def __array_ufunc__(self, ufunc, method, *inputs, **kwargs):
        # inputs 内の MyMatrix インスタンスを np.ndarray に変換
        inputs = tuple(x.view(np.ndarray) if isinstance(x,Diag) else x for x in inputs)
        # ufunc 演算を実行
        result = getattr(ufunc, method)(*inputs, **kwargs)
        
        if type(inputs[0])  == float or type(inputs[0])  == int or type(inputs[1])  == int or type(inputs[1])  == float:
            return result.view(Diag)
        
        if method == 'reduce':
            return np.asarray(result)
        return result



def csr_cos(A ,Exist)->csr:
    """
 
    """
    data = np.array( np.cos(A[Exist==True]) ).flatten() # type: ignore
    return sps.csr_array( (data, Exist.indices, Exist.indptr),shape=Exist.shape)

__all__ = []

"""
class GPT_av_old:
    def __init__(self,
        Obs: rt1kernel.Observation_Matrix_integral,
        Kernel: rt1kernel.Kernel2D_scatter,
        ) -> None:
        self.Obs = Obs
        self.rI = Obs.rI 
        self.zI = Obs.zI 
        self.nI = Obs.zI.size  
        self.Kernel = Kernel
        pass

    def set_kernel(self,
        K_a :np.ndarray,
        K_v :np.ndarray,
        a_pri:np.ndarray |float = 0,
        v_pri:np.ndarray |float = 0,
        regularization:float = 1e-5,
        ):
        K_a += regularization*np.eye(self.nI)
        K_v += regularization*np.eye(self.nI)

        self.K_a = 0.5*(K_a + K_a.T)
        self.K_v = 0.5*(K_v + K_v.T)
        K_a_inv = np.linalg.inv(self.K_a)
        K_v_inv = np.linalg.inv(self.K_v)
        self.K_a_inv = 0.5*(K_a_inv+K_a_inv.T)
        self.K_v_inv = 0.5*(K_v_inv+K_v_inv.T)
        self.a_pri = a_pri
        self.v_pri = v_pri

        pass 

    def set_sig(self,
        sigma:np.ndarray,
        A_cos:np.ndarray,
        A_sin:np.ndarray,
        num:int=0,
        ):
        sigma = sigma.flatten()
        A_cos = A_cos.flatten()
        A_sin = A_sin.flatten()
        self.sig_inv = 1/sigma
        self.sig2_inv = 1/sigma**2
        Dcos = self.Obs.Hs[num].Dcos
        H    = self.Obs.Hs[num].H

        self.sigiH   :sps.csr_matrix =  sps.diags(self.sig_inv) @ H  
        self.sigiHT  :sps.csr_matrix = self.sigiH.multiply(Dcos)  # type: ignore
        self.sigiHT2 :sps.csr_matrix = self.sigiHT.multiply(Dcos)
        self.SiA = self.sig_inv*(A_cos + A_sin*1.j)
        
    def set_sig2(self,
        sigma:np.ndarray,
        A_cos:np.ndarray,
        A_sin:np.ndarray,
        num:int=0,
        ):
        sigma = sigma.flatten()
        A_cos = A_cos.flatten()
        A_sin = A_sin.flatten()
        self.sig_inv = 1/sigma
        self.sig2_inv = 1/sigma**2
        Dcos  = 1.j*self.Obs.Hs[num].Dcos
        #Dcos  = 1.j*self.Obs.Hs[num].Exist
        H    = self.Obs.Hs[num].H

        self.sigiH =  sps.csr_matrix( sps.diags(self.sig_inv) @ H )
        self.sigiHT  :sps.csr_matrix = self.sigiH.multiply(Dcos) 
        self.sigiHT2 :sps.csr_matrix = self.sigiHT.multiply(Dcos)
        self.SiA = self.sig_inv*(A_cos + A_sin*1.j)

    def calc_core2(self,
        a:np.ndarray,
        v:np.ndarray,
        num:int=0
        ):
        r_a = a - self.a_pri
        r_v = v - self.v_pri
        Exp = self.Obs.Hs[num].Exp(a,v)

        SiHE  :sps.csr_matrix = self.sigiH.multiply(Exp) # m*n 
        SiHTE :sps.csr_matrix = self.sigiHT.multiply(Exp)
        SiHT2E:sps.csr_matrix = self.sigiHT2.multiply(Exp)

        SiHE_conj = SiHE.conjugate()
        SiHTE_conj= SiHTE.conjugate()
        SiR = np.asarray(SiHE.sum(axis=1)).flatten()- self.SiA 
        
        #fig,ax=plt.subplots(1,2,figsize=(10,5))
        #imshow_cbar(fig,ax[0],(np.sum(SiHE,axis=1).real).reshape(200,200))
        #imshow_cbar(fig,ax[1],(np.sum(SiHE,axis=1).imag).reshape(200,200))
        #plt.show()
        
        #fig,ax=plt.subplots(1,2,figsize=(10,5))
        #imshow_cbar(fig,ax[0],(SiR.real).reshape(200,200))
        #imshow_cbar(fig,ax[1],(SiR.imag).reshape(200,200))
        #plt.show()
        SiR_conj = np.conj(SiR)
        c1 = (SiHE.T   @ SiR_conj).real 
        c2 = (SiHTE.T  @ SiR_conj).real
        c3 = (SiHT2E.T @ SiR_conj).real

        C1 = ((SiHE_conj.T  @ SiHE ).real).toarray()

        C2 = ((SiHTE_conj.T @ SiHTE).real).toarray()

        C3 = ((SiHTE_conj.T @ SiHE ).real).toarray()


        Psi_da   = -c1 - self.K_a_inv @ r_a 
        Psi_dv   = -c2 - self.K_v_inv @ r_v
        Psi_dada = -C1 - np.diag(c1)*1 - self.K_a_inv
        Psi_dvdv = -C2*1 + np.diag(c3)*1- self.K_v_inv
        Psi_dadv = (-C3*1 + np.diag(c2)*0).T
        Psi_dvda =  Psi_dadv.T


        nI = self.nI
        
        NPsi      = np.zeros((2*nI))
        NPsi[:nI] = Psi_da[:]
        NPsi[nI:] = Psi_dv[:]
        #NPsi = np.concatenate([Psi_da,Psi_dv])

        DPsi = np.zeros((2*nI,2*nI))

        #plt.hist(((SiHE.T   @ SiR_conj).real).flatten(),bins=50)
        #plt.hist(((SiHE.T   @ SiR_conj).imag).flatten(),bins=50)
        #plt.hist(((SiHTE.T   @ SiR_conj).real).flatten(),bins=50)
        #plt.hist(((SiHTE.T   @ SiR_conj).imag).flatten(),bins=50)
        #plt.hist(Psi_da,bins=50)
        #plt.show()

        DPsi[:nI,:nI] = Psi_dada[:,:]
        DPsi[nI:,nI:] = Psi_dvdv[:,:]*1
        DPsi[:nI,nI:] = Psi_dvda[:,:]*1
        DPsi[nI:,:nI] = Psi_dadv[:,:]*1

        #plt.figure(figsize=(30,30))
        #c = plt.imshow(DPsi,cmap='turbo',vmax=abs(DPsi).max(),vmin=-abs(DPsi).max())
        #plt.colorbar(c)
        #plt.show()

        del Psi_dada,Psi_dvdv,Psi_dvda,Psi_dadv

        delta_av = - np.linalg.solve(DPsi+0*np.eye(self.nI*2),NPsi)
        
        delta_av[delta_av<-3] = -3
        delta_av[delta_av>+3] = +3
        delta_a = delta_av[:nI]
        delta_v = delta_av[nI:]

        return delta_a,delta_v

    def calc_core(self,
        a:np.ndarray,
        v:np.ndarray,
        num:int=0
        ):
        r_a = a - self.a_pri
        r_v = v - self.v_pri
        Exp = self.Obs.Hs[num].Exp(a,v)

        SiHE  :sps.csr_matrix = self.sigiH.multiply(Exp) # m*n 
        SiHTE :sps.csr_matrix = self.sigiHT.multiply(Exp)
        SiHT2E:sps.csr_matrix = self.sigiHT2.multiply(Exp)

        SiHE_conj = SiHE.conjugate()
        SiHTE_conj = SiHTE.conjugate()
        SiR = np.asarray(SiHE.sum(axis=1)).flatten()- self.SiA 
        SiR_conj = np.conj(SiR)
        c1 = (SiHE.T @ SiR_conj).real 
        c2 = (1.j*SiHTE.T @ SiR_conj).real
        c3 = (SiHT2E.T @ SiR_conj).real

        C1 = ((SiHE_conj.T @ SiHE).real).toarray()

        C1_2 = ((SiHE_conj.T @ SiHE).real).toarray()
        C2 = ((SiHTE_conj.T @ SiHTE).real).toarray()
        C3 = ((1.j*SiHTE_conj.T @ SiHE).real).toarray()

        Psi_da   = -c1 - self.K_a_inv @ r_a 
        Psi_dv   = -c2 - self.K_v_inv @ r_v
        Psi_dada = -C1 - np.diag(c1)*1 - self.K_a_inv
        Psi_dvdv = +C2*0 - np.diag(c3)*1- self.K_v_inv
        Psi_dadv = -C3*0 - np.diag(c2)*0 
        Psi_dvda = Psi_dadv.T 


        nI = self.nI
        DPsi = np.zeros((2*nI,2*nI))
        NPsi = np.concatenate([Psi_da,Psi_dv])

        DPsi[:nI,:nI] = Psi_dada[:,:]
        DPsi[nI:,nI:] = Psi_dvdv[:,:]
        DPsi[:nI,nI:] = Psi_dvda[:,:]*0
        DPsi[nI:,:nI] = Psi_dadv[:,:]*0

        print(abs((DPsi-DPsi.T)).max())
        #plt.figure(figsize=(30,30))
        #c = plt.imshow(DPsi,cmap='turbo',vmax=abs(DPsi).max(),vmin=-abs(DPsi).max())
        #plt.colorbar(c)
        #plt.show()

        del Psi_dada,Psi_dvdv,Psi_dvda,Psi_dadv

        delta_av = - np.linalg.solve(DPsi,NPsi)
        
        delta_av[delta_av<-3] = -3
        delta_av[delta_av>+3] = +3
        delta_a = delta_av[:nI]
        delta_v = delta_av[nI:]

        return delta_a,delta_v
        
    def check_diff(self,
        a:np.ndarray,
        v:np.ndarray):
            
        fig,ax = plt.subplots(1,2,figsize=(10,5))
        A = self.Obs.Hs[0].projection_A2(a,v)
        imshow_cbar(fig,ax[0],A.real)
        imshow_cbar(fig,ax[1],A.imag)
        
        plt.show()
"""

class GPT_lin:
    def __init__(self,
        Obs: rt1kernel.Observation_Matrix_integral,
        Kernel: rt1kernel.Kernel2D_scatter,
        ) -> None:
        self.Obs = Obs
        self.rI = Obs.rI 
        self.zI = Obs.zI 
        self.nI = Obs.zI.size  
        self.Kernel = Kernel
        pass

    def set_prior(self,
        K :np.ndarray,
        f_pri :np.ndarray | float = 0,
        regularization:float = 1e-6,
        ):
        K += regularization*np.eye(self.nI)

        self.K_inv = np.linalg.inv(K)
        self.f_pri = f_pri

    def calc_core(self):
        self.K_pos = np.linalg.inv( self.Hsig2iH+self.K_inv )
        self.mu_f_pos = self.f_pri + self.K_pos @ (self.sigiH.T @ (self.Sigi_obs-self.sigiH @self.f_pri))

        return self.mu_f_pos,self.K_pos



    def set_sig(self,
        sig_array:np.ndarray,
        g_obs:np.ndarray,
        sig_scale:float=1.0,
        num:int=0,
        ):
        self.g_obs=g_obs.reshape(self.Obs.shape[:2])
        self.sig_scale = sig_scale
        sig_array = sig_array.flatten()
        g_obs = g_obs.flatten()
        self.sig_inv = 1/sig_array/self.sig_scale
        #self.sig2_inv = 1/sig_array**2
        H    = self.Obs.Hs[num].H

        self.Sigi_obs = self.sig_inv*(g_obs)
        self.sigiH = sps.csr_matrix(sps.diags(self.sig_inv) @ H )
        sigiH_t = sps.csr_matrix( self.sigiH.T )

        #self.Hsig2iH  = (self.sigiH.T @ self.sigiH).toarray() 
        # self.Hsig2iH = sparse_dot_mkl.gram_matrix_mkl(sigiH_t,transpose=True,dense=True)　#2時間溶かした戦犯
        self.Hsig2iH = sparse_dot_mkl.dot_product_mkl(sigiH_t,self.sigiH ,dense=True)

    
    def check_diff(self,
        f:np.ndarray):
            
        fig,ax = plt_subplots(1,3,figsize=(12,3.))
        ax = ax[0][:]
        g = self.Obs.Hs[0].projection(f)
        imshow_cbar(ax[0],g,origin='lower')
        ax[0].set_title('Hf')
        vmax = (abs(g-self.g_obs)).max()
        imshow_cbar(ax= ax[1],im0 = g-self.g_obs,vmin=-vmax,vmax=vmax,cmap='RdBu_r',origin='lower')
        ax[1].set_title('diff_im')
        
        ax[2].hist((g-self.g_obs).flatten(),bins=50)

        ax[2].tick_params( labelleft=False)
        plt.show()

import scipy.linalg

def log_det(A,scale=1):
    try:
        A = scipy.linalg.cholesky(A)
        return np.sum(np.log(np.diag(A)))*2 + A.shape[0]*np.log(scale)
    except:
        lam,_ = np.linalg.eigh(A)
        return np.sum(np.log(lam)) + A.shape[0]*np.log(scale)


class GPT_av:
    def __init__(self,
        Obs: rt1kernel.Observation_Matrix_integral,
        Kernel: rt1kernel.Kernel2D_scatter,
        ) -> None:
        self.Obs = Obs
        self.rI = Obs.rI 
        self.zI = Obs.zI 
        self.nI = Obs.zI.size  
        self.Kernel = Kernel
        self.H   = Obs.Hs[0].H
        self.Dec = Obs.Hs[0].Dcos
        self.Exist = Obs.Hs[0].Exist
        self.mask = Obs.mask
        pass

    def set_kernel(self,
        K_a :np.ndarray,
        K_v :np.ndarray,
        a_pri:np.ndarray | float = 0,
        v_pri:np.ndarray | float = 0,
        regularization:float = 1e-5,
        ):
        K_a += regularization*np.eye(self.nI)
        K_v += regularization*np.eye(self.nI)

        self.K_a = 0.5*(K_a + K_a.T)
        self.K_v = 0.5*(K_v + K_v.T)
        K_a_inv = np.linalg.inv(self.K_a)
        K_v_inv = np.linalg.inv(self.K_v)
        self.K_a_inv = 0.5*(K_a_inv+K_a_inv.T)
        self.K_v_inv = 0.5*(K_v_inv+K_v_inv.T)
        self.a_pri = a_pri
        self.v_pri = v_pri

        self.K_f_inv = np.zeros((2*self.nI,2*self.nI))
        self.K_f_inv[:self.nI ,:self.nI ] = self.K_a_inv[:,:]
        self.K_f_inv[ self.nI:, self.nI:] = self.K_v_inv[:,:]

        self.log_det_K_f = log_det(self.K_a)+log_det(self.K_v)
        pass 

        
    def set_sig(self,
        sig_im:np.ndarray,
        A_cos:np.ndarray,
        A_sin:np.ndarray,
        num:int=0,
        #sig_scale:float = 1.0,
        ):
        self.Acos_im = A_cos.reshape(*self.Obs.shape[:2])
        self.Asin_im = A_sin.reshape(*self.Obs.shape[:2])
        print(sig_im.shape)
        sigma = sig_im[~self.mask]
        A_cos = A_cos[~self.mask]
        A_sin = A_sin[~self.mask]
        self.sig_inv = 1/sigma
        self.sig2_inv = 1/sigma**2
        #Dcos  = 1.j*self.Obs.Hs[num].Dcos
        #H    = self.Obs.Hs[num].H
        H    = self.Obs.Hs_mask[0]
        self.sigiH   : sps.csr_matrix = sps.diags(self.sig_inv) @ H  
        self.sigiA = np.hstack((self.sig_inv*A_cos, self.sig_inv*A_sin))
        self.log_det_Sig = 2*np.sum(np.log(sig_im))
    

    def calc_core(self,
        a:np.ndarray,
        v:np.ndarray,
        num:int=0,
        sig_scale:float = 1.0
        ):
        r_a = a - self.a_pri
        r_v = v - self.v_pri

        self.r_a, self.r_v = r_a,r_v
        
        self.sig_scale = sig_scale
        sig_scale_inv = 1/sig_scale
        DecV = sps.csr_matrix(self.Dec @ sps.diags(v))
        Hc = self.sigiH.multiply(csr_cos(DecV,self.Exist))
        Hs = self.sigiH.multiply(DecV.sin())
        Exp_a = sps.diags(np.exp(a))
        self.Rc = sps.csr_matrix(Hc @ Exp_a )
        self.Rs = sps.csr_matrix(Hs @ Exp_a )
        Ac = np.asarray(self.Rc.sum(axis=1)).flatten()
        As = np.asarray(self.Rs.sum(axis=1)).flatten()
        sigi_g  = np.hstack((Ac,As))
        self.resA = sig_scale_inv *(sigi_g-self.sigiA)

        self.Rc_Dec = self.Rc.multiply(self.Dec)
        self.Rs_Dec = self.Rs.multiply(self.Dec)

        Jac = sps.vstack(
                (sps.hstack((self.Rc, -self.Rs_Dec)),
                 sps.hstack((self.Rs,  self.Rc_Dec)))
                ) *sig_scale_inv
        
        Jac_t = sps.csr_matrix(Jac.T)
        
        nabla_Phi = -np.array(Jac_t @ self.resA) - np.hstack((self.K_a_inv @r_a, self.K_v_inv @r_v)) #type: ignore

        #W1 = sparse_dot_mkl.gram_matrix_mkl( sps.csr_matrix(Jac.T),dense=True,transpose=True)
        #W1 = W1 + W1.T - np.diag(W1.diagonal())

        W1 = sparse_dot_mkl.dot_product_mkl( Jac_t ,Jac ,dense=True)
        loss = abs(nabla_Phi).mean()
        # W2 = self._W2()

        laplace_Phi = - W1  - self.K_f_inv # -W2*1
        self.laplace_Phi = laplace_Phi
        delta_f = - np.linalg.solve(laplace_Phi, nabla_Phi)
        delta_f[delta_f<-5] = -5
        delta_f[delta_f>+5] = +5 

        delta_a = delta_f[:self.nI]
        delta_v = delta_f[self.nI:]
        return delta_a, delta_v,loss
    
    
    def postprocess(self,
        consider_w2 :bool = True,
        ):
        if consider_w2:
            K_inv = -self.laplace_Phi+self._W2()
        else:
            K_inv = -self.laplace_Phi
        self.Kf_pos = np.linalg.inv(K_inv)
        self.log_det_Kpos = log_det(self.Kf_pos)
        loss_g = np.dot(self.resA,self.resA) 
        loss_f = self.r_a@ (self.K_a_inv @ self.r_a) + self.r_v @(self.K_v_inv @ self.r_v)  

        self.log_det_Sig2 = self.log_det_Sig + np.log(self.sig_scale)*self.H.shape[0]*2


        self.mll = -loss_g -loss_f -self.log_det_Sig2 - self.log_det_K_f + self.log_det_Kpos
        self.mll = 0.5*self.mll- 0.5*self.H.shape[0]*np.log(2*np.pi)

    
    def K_pos(self,
        consider_w2 :bool = True,
        ):
        if consider_w2:
            K_inv = -self.laplace_Phi+self._W2()
        else:
            K_inv = -self.laplace_Phi
        Kpos = np.linalg.inv(K_inv)
        log_det_Kpos = log_det(log_det_Kpos)
        return np.linalg.inv(K_inv)

    def _W2(self,
        ):

        Rc_Dec2 =  self.Rc_Dec.multiply(self.Dec)
        Rs_Dec2 =  self.Rs_Dec.multiply(self.Dec)

        d_aa = sps.hstack((  self.Rc.T, self.Rs.T )) @ self.resA
        d_vv = sps.hstack(( -Rc_Dec2.T, -Rs_Dec2.T )) @ self.resA
        d_av = sps.hstack((-self.Rs_Dec.T,  self.Rc_Dec.T))  @ self.resA
        
        W2 = np.zeros((2*self.nI, 2*self.nI))
        W2[:self.nI,  :self.nI ] = np.diag(d_aa)[:,:]
        W2[ self.nI:, :self.nI ] = np.diag(d_av)[:,:]
        W2[:self.nI ,  self.nI:] = np.diag(d_av)[:,:]
        W2[ self.nI:,  self.nI:] = np.diag(d_vv)[:,:]

        return W2



    def check_diff(self,
        a:np.ndarray,
        v:np.ndarray):
        m = self.H.shape[0]
        fig,axs = plt_subplots(2,2,figsize=(8,8),sharex=True,sharey=True)

        DecV = sps.csr_matrix(self.Dec @ sps.diags(v))
        Hc = self.Obs.Hs_mask[0].multiply(csr_cos(DecV,self.Exist))
        Hs = self.Obs.Hs_mask[0].multiply(DecV.sin())

        g_cos = np.zeros(self.Obs.shape[:2])
        g_cos[~self.mask] = Hc@np.exp(a)
        g_sin = np.zeros(self.Obs.shape[:2])
        g_sin[~self.mask] = Hs@np.exp(a)

        #g_cos,g_sin = A.real,A.imag
        
        y_cos = self.Acos_im
        y_sin = self.Asin_im
        #y = self.sigiA
        #y_cos = (1/self.sig_inv*y[:m]).reshape(*self.Obs.shape[:2])
        #y_sin = (1/self.sig_inv*y[m:]).reshape(*self.Obs.shape[:2])
        imshow_cbar(axs[0][0],g_cos,origin='lower')
        imshow_cbar(axs[1][0],g_sin,origin='lower')
        diff1 = (g_cos-y_cos)[~self.mask]
        diff2 = (g_sin-y_sin)[~self.mask]
        vmax = max(np.percentile(diff1,95),-np.percentile(diff1,5),np.percentile(diff2,95),-np.percentile(diff2,5)) #type: ignore
        imshow_cbar(axs[0][1],g_cos-y_cos,cmap='RdBu_r',vmax=vmax,vmin=-vmax,origin='lower')
        imshow_cbar(axs[1][1],g_sin-y_sin,cmap='RdBu_r',vmax=vmax,vmin=-vmax,origin='lower')
        
        axs[0][0].set_title(r'$g^{\cos}$')
        axs[1][0].set_title(r'$g^{\sin}$')
        axs[0][1].set_title(r'diff: $g^{\cos}-y^{\cos}$')
        axs[1][1].set_title(r'diff: $g^{\sin}-y^{\sin}$')
        plt.show()

GPT_cis = GPT_av




class GPT_av_dense:
    def __init__(self,
        Obs: rt1kernel.Observation_Matrix_integral,
        Kernel: rt1kernel.Kernel2D_scatter,
        ) -> None:
        self.Obs = Obs
        self.rI = Obs.rI 
        self.zI = Obs.zI 
        self.nI = Obs.zI.size  
        self.Kernel = Kernel
        self.H   = Obs.Hs[0].H.toarray()
        self.Dec = Obs.Hs[0].Dcos.toarray()
        self.mask = Obs.mask
        pass

    def set_kernel(self,
        K_a :np.ndarray,
        K_v :np.ndarray,
        a_pri:np.ndarray | float = 0,
        v_pri:np.ndarray | float = 0,
        regularization:float = 1e-5,
        ):
        K_a += regularization*np.eye(self.nI)
        K_v += regularization*np.eye(self.nI)

        self.K_a = 0.5*(K_a + K_a.T)
        self.K_v = 0.5*(K_v + K_v.T)
        K_a_inv = np.linalg.inv(self.K_a)
        K_v_inv = np.linalg.inv(self.K_v)
        self.K_a_inv = 0.5*(K_a_inv+K_a_inv.T)
        self.K_v_inv = 0.5*(K_v_inv+K_v_inv.T)
        self.a_pri = a_pri
        self.v_pri = v_pri

        self.K_f_inv = np.zeros((2*self.nI,2*self.nI))
        self.K_f_inv[:self.nI ,:self.nI ] = self.K_a_inv[:,:]
        self.K_f_inv[ self.nI:, self.nI:] = self.K_v_inv[:,:]

        self.log_det_K_f = log_det(self.K_a)+log_det(self.K_v)
        pass 

        
    def set_sig(self,
        sig_im:np.ndarray,
        A_cos:np.ndarray,
        A_sin:np.ndarray,
        num:int=0,
        #sig_scale:float = 1.0,
        ):
        self.Acos_im = A_cos.reshape(*self.Obs.shape[:2])
        self.Asin_im = A_sin.reshape(*self.Obs.shape[:2])
        print(sig_im.shape)
        sigma = sig_im[~self.mask]
        A_cos = A_cos[~self.mask]
        A_sin = A_sin[~self.mask]
        self.sig_inv = 1/sigma
        self.sig2_inv = 1/sigma**2
        #Dcos  = 1.j*self.Obs.Hs[num].Dcos
        #H    = self.Obs.Hs[num].H
        H    = self.Obs.Hs_mask[0]
        #self.sigiH = np.einsum('i,ij->ij',self.sig_inv,H )  
        self.sigiH = Diag(self.sig_inv) @ H   
        self.sigiA = np.hstack((self.sig_inv*A_cos, self.sig_inv*A_sin))
        self.log_det_Sig = 2*np.sum(np.log(sig_im))
    

    def calc_core(self,
        a:np.ndarray,
        v:np.ndarray,
        num:int=0,
        sig_scale:float = 1.0
        ):
        r_a = a - self.a_pri
        r_v = v - self.v_pri

        self.r_a, self.r_v = r_a,r_v
        
        self.sig_scale = sig_scale
        sig_scale_inv = 1/sig_scale
        #DecV = sps.csr_matrix(self.Dec @ sps.diags(v))
        #DecV = np.einsum('ij,j->ij',self.Dec, v)
        DecV = self.Dec @ Diag(v) 
        #Hc = self.sigiH.multiply(csr_cos(DecV,self.Exist))
        #Hs = self.sigiH.multiply(DecV.sin())

        Hc = self.sigiH * np.cos(DecV)
        Hs = self.sigiH * np.sin(DecV)
        Diag_exp_a = Diag(np.exp(a))
        #self.Rc = sps.csr_matrix(Hc @ Exp_a )
        self.Rc = Hc @ Diag_exp_a
        #self.Rs = sps.csr_matrix(Hs @ Exp_a )
        self.Rs = Hs @ Diag_exp_a
        Ac = self.Rc.sum(axis=1)
        As = self.Rs.sum(axis=1)
        #Ac = np.asarray(self.Rc.sum(axis=1)).flatten()
        #As = np.asarray(self.Rs.sum(axis=1)).flatten()
        sigi_g  = np.hstack((Ac,As))
        self.resA = sig_scale_inv *(sigi_g-self.sigiA)


        self.Rc_Dec = self.Rc * self.Dec
        self.Rs_Dec = self.Rs * self.Dec
        #self.Rc_Dec = self.Rc.multiply(self.Dec)
        #self.Rs_Dec = self.Rs.multiply(self.Dec)

        Jac = np.vstack(
               (np.hstack((self.Rc, -self.Rs_Dec)),
                np.hstack((self.Rs,  self.Rc_Dec)))
                ) *sig_scale_inv
        
        Jac_t = Jac.T
        
        nabla_Phi = -Jac_t @ self.resA - np.hstack((self.K_a_inv @r_a, self.K_v_inv @r_v)) #type: ignore

        #W1 = sparse_dot_mkl.gram_matrix_mkl( sps.csr_matrix(Jac.T),dense=True,transpose=True)
        #W1 = W1 + W1.T - np.diag(W1.diagonal())

        W1 = Jac_t@Jac
        loss = abs(nabla_Phi).mean()
        # W2 = self._W2()

        laplace_Phi = - W1  - self.K_f_inv # -W2*1
        self.laplace_Phi = laplace_Phi
        delta_f = - np.linalg.solve(laplace_Phi, nabla_Phi)
        delta_f[delta_f<-5] = -5
        delta_f[delta_f>+5] = +5 

        delta_a = delta_f[:self.nI]
        delta_v = delta_f[self.nI:]
        return delta_a, delta_v,loss
    
    
    def postprocess(self,
        consider_w2 :bool = True,
        ):
        if consider_w2:
            K_inv = -self.laplace_Phi+self._W2()
        else:
            K_inv = -self.laplace_Phi
        self.Kf_pos = np.linalg.inv(K_inv)
        self.log_det_Kpos = log_det(self.Kf_pos)
        loss_g = np.dot(self.resA,self.resA) 
        loss_f = self.r_a@ (self.K_a_inv @ self.r_a) + self.r_v @(self.K_v_inv @ self.r_v)  

        self.log_det_Sig2 = self.log_det_Sig + np.log(self.sig_scale)*self.H.shape[0]*2


        self.mll = -loss_g -loss_f -self.log_det_Sig2 - self.log_det_K_f + self.log_det_Kpos
        self.mll = 0.5*self.mll- 0.5*self.H.shape[0]*np.log(2*np.pi)

    
    def K_pos(self,
        consider_w2 :bool = True,
        ):
        if consider_w2:
            K_inv = -self.laplace_Phi+self._W2()
        else:
            K_inv = -self.laplace_Phi
        Kpos = np.linalg.inv(K_inv)
        log_det_Kpos = log_det(log_det_Kpos)
        return np.linalg.inv(K_inv)

    def _W2(self,
        ):

        Rc_Dec2 =  self.Rc_Dec.multiply(self.Dec)
        Rs_Dec2 =  self.Rs_Dec.multiply(self.Dec)

        d_aa = sps.hstack((  self.Rc.T, self.Rs.T )) @ self.resA
        d_vv = sps.hstack(( -Rc_Dec2.T, -Rs_Dec2.T )) @ self.resA
        d_av = sps.hstack((-self.Rs_Dec.T,  self.Rc_Dec.T))  @ self.resA
        
        W2 = np.zeros((2*self.nI, 2*self.nI))
        W2[:self.nI,  :self.nI ] = np.diag(d_aa)[:,:]
        W2[ self.nI:, :self.nI ] = np.diag(d_av)[:,:]
        W2[:self.nI ,  self.nI:] = np.diag(d_av)[:,:]
        W2[ self.nI:,  self.nI:] = np.diag(d_vv)[:,:]

        return W2



    def check_diff(self,
        a:np.ndarray,
        v:np.ndarray):
        m = self.H.shape[0]
        fig,axs = plt_subplots(2,2,figsize=(8,8),sharex=True,sharey=True)

        DecV = sps.csr_matrix(self.Dec @ sps.diags(v))
        Hc = self.Obs.Hs_mask[0].multiply(csr_cos(DecV,self.Exist))
        Hs = self.Obs.Hs_mask[0].multiply(DecV.sin())

        g_cos = np.zeros(self.Obs.shape[:2])
        g_cos[~self.mask] = Hc@np.exp(a)
        g_sin = np.zeros(self.Obs.shape[:2])
        g_sin[~self.mask] = Hs@np.exp(a)

        #g_cos,g_sin = A.real,A.imag
        
        y_cos = self.Acos_im
        y_sin = self.Asin_im
        #y = self.sigiA
        #y_cos = (1/self.sig_inv*y[:m]).reshape(*self.Obs.shape[:2])
        #y_sin = (1/self.sig_inv*y[m:]).reshape(*self.Obs.shape[:2])
        imshow_cbar(axs[0][0],g_cos,origin='lower')
        imshow_cbar(axs[1][0],g_sin,origin='lower')
        diff1 = (g_cos-y_cos)[~self.mask]
        diff2 = (g_sin-y_sin)[~self.mask]
        vmax = max(np.percentile(diff1,95),-np.percentile(diff1,5),np.percentile(diff2,95),-np.percentile(diff2,5)) #type: ignore
        imshow_cbar(axs[0][1],g_cos-y_cos,cmap='RdBu_r',vmax=vmax,vmin=-vmax,origin='lower')
        imshow_cbar(axs[1][1],g_sin-y_sin,cmap='RdBu_r',vmax=vmax,vmin=-vmax,origin='lower')
        
        axs[0][0].set_title(r'$g^{\cos}$')
        axs[1][0].set_title(r'$g^{\sin}$')
        axs[0][1].set_title(r'diff: $g^{\cos}-y^{\cos}$')
        axs[1][1].set_title(r'diff: $g^{\sin}-y^{\sin}$')
        plt.show()

GPT_cis_dense = GPT_av_dense

class GPT_log:
    def __init__(self,
        Obs: rt1kernel.Observation_Matrix_integral,
        Kernel: rt1kernel.Kernel2D_scatter,
        H_diff: reflection.Diffusion_kernel = None
        ) -> None:
        self.Obs = Obs
        self.rI = Obs.rI 
        self.zI = Obs.zI 
        self.nI = Obs.zI.size  
        self.Kernel = Kernel
        self.mask = self.Obs.mask
        self.H_diff =  H_diff
        pass

    def set_kernel(self,
        K :np.ndarray,
        f_pri :np.ndarray | float = 0,
        regularization:float = 1e-6,
        ):
        K += regularization*np.eye(self.nI)

        self.K_inv = np.linalg.inv(K)
        self.f_pri = f_pri

    def set_sig(self,
        sig_im  :np.ndarray,
        g_obs   :np.ndarray,
        sig_scale:float=1.0,
        num:int=0,
        out_scaling :bool =False,
        ):

        self.g_obs=g_obs.reshape(self.Obs.shape[:2])

        
        if out_scaling:
            self.H_scale = self.Obs.projection(np.ones(self.nI),reshape=False).mean()
            self.g_scale = self.g_obs[~self.mask].mean()
            self.g_obs = 1/self.g_scale * self.g_obs
        else :
            self.H_scale = 1
            self.g_scale = 1
            
        g_obs =  self.g_obs[~self.mask]
        sig_im = sig_im[~self.mask]

        self.sig_scale = sig_scale
        self.sig_inv = 1/sig_im
        #self.sig2_inv = 1/sig_array**2

        #H    = self.Obs.Hs[num].H
        H    = self.Obs.H_sum /self.H_scale

        self.Sigi_obs = self.sig_inv* ( g_obs )
        self.sigiH = sps.csr_matrix(sps.diags(self.sig_inv) @ H )
        sigiH_t = sps.csr_matrix( self.sigiH.T )

        #self.Hsig2iH  = (self.sigiH.T @ self.sigiH).toarray() 
        # self.Hsig2iH = sparse_dot_mkl.gram_matrix_mkl(sigiH_t,transpose=True,dense=True)　#2時間溶かした戦犯
        self.Hsig2iH = sparse_dot_mkl.dot_product_mkl(sigiH_t,self.sigiH ,dense=True)

        if self.H_diff is not None:
            self.H_diff.H_diff_I
            Hd_interp_m = self.H_diff.Interp[~self.mask.flatten(),:]
            self.sigiHd_intp = sps.diags(self.sig_inv) @ Hd_interp_m 
            self.Hd_sig2i_Hd = self.H_diff.H_diff_I.T @(self.sigiHd_intp.T@self.sigiHd_intp) @ self.H_diff.H_diff_I
            self.Hd_sig2i_H = self.H_diff.H_diff_I.T @ (self.sigiHd_intp.T @self.sigiH )


    
    def check_diff(self,
        f:np.ndarray):
            
        fig,ax = plt_subplots(1,3,figsize=(10,4))
        ax = ax[0][:]
        g = self.Obs.projection(np.exp(f)) /self.H_scale

        if self.H_diff is not None :
            g += (self.H_diff@np.exp(f)).reshape(*self.Obs.shape[:2]) *  self.alpha_d
        imshow_cbar(ax[0],g,origin='lower')
        ax[0].set_title(r'Hf')
        vmax = np.percentile((abs(g-self.g_obs )[~self.mask]),95)
        imshow_cbar(ax= ax[1],im0 = g-self.g_obs   ,vmin=-vmax,vmax=vmax,cmap='RdBu_r',origin='lower')
        ax[1].set_title('diff_im')
        
        ax[2].hist((g-self.g_obs)[~self.mask],bins=50)
        ax[2].tick_params( labelleft=False)


        plt.show()

    
    def calc_core_fast(self,
        f:np.ndarray,
        num:int=0,
        alpha_d:float = 0,
        sig_scale :Optional[float] = None 
        ):
        if sig_scale is not None:
            self.sig_scale = sig_scale
        r_f = f - self.f_pri
        exp_f = np.exp(f)
        fxf = np.einsum('i,j->ij',exp_f,exp_f)
        
        if self.H_diff is None:
            SiR = self.sigiH @ exp_f - self.Sigi_obs
            c1 = 1/self.sig_scale**2 *(self.sigiH.T @ SiR) * exp_f #self.sigiH.T @ SiR =  self.Hsig2iH  @ exp_f -  self.sigiH.T@ self.Sigi_obs
            C1 = 1/self.sig_scale**2 *self.Hsig2iH * fxf 
        else:
            d = alpha_d
            H_diff_I = self.H_diff.H_diff_I
            SiR = self.sigiH @ exp_f + d* (self.sigiHd_intp @ (H_diff_I @ exp_f))- self.Sigi_obs
            c1 = 1/self.sig_scale**2 *(self.sigiH.T @ SiR+ d *H_diff_I.T @ (self.sigiHd_intp.T @SiR)) * exp_f
            C1 = 1/self.sig_scale**2 *(self.Hsig2iH+ d**2 *self.Hd_sig2i_Hd + d *self.Hd_sig2i_H +d *self.Hd_sig2i_H.T )* fxf 
            self.alpha_d =d 

        Psi_df   = -c1 - self.K_inv @ r_f 

        Psi_dfdf = -C1 - np.diag(c1) - self.K_inv

        DPsi = Psi_dfdf
        NPsi = Psi_df
        loss = abs(NPsi).mean()

        delta_f = - np.linalg.solve(DPsi,NPsi)

        delta_f[delta_f<-3] = -3
        delta_f[delta_f>+3] = +3

        return delta_f,loss
    
    def set_postprocess(self,
        f:npt.NDArray[np.float64],
        ):
        exp_f = np.exp(f)
        fxf = np.einsum('i,j->ij',exp_f,exp_f)
        
        
        if self.H_diff is None:
            SiR = self.sigiH @ exp_f - self.Sigi_obs
            c1 = 1/self.sig_scale**2 *(self.sigiH.T @ SiR) * exp_f #self.sigiH.T @ SiR =  self.Hsig2iH  @ exp_f -  self.sigiH.T@ self.Sigi_obs
            C1 = 1/self.sig_scale**2 *self.Hsig2iH * fxf 
        else:
            d = self.alpha_d 
            H_diff_I = self.H_diff.H_diff_I
            SiR = self.sigiH @ exp_f + d* (self.sigiHd_intp @ (H_diff_I @ exp_f))- self.Sigi_obs
            c1 = 1/self.sig_scale**2 *(self.sigiH.T @ SiR+ d *H_diff_I.T @ (self.sigiHd_intp.T @SiR)) * exp_f
            C1 = 1/self.sig_scale**2 *(self.Hsig2iH+ d**2 *self.Hd_sig2i_Hd + d *self.Hd_sig2i_H +d *self.Hd_sig2i_H.T )* fxf 



        Psi_dfdf = -C1 - np.diag(c1) - self.K_inv

        DPsi = Psi_dfdf
        self.Kf_pos_inv = -DPsi
        self.Kf_pos     = np.linalg.inv(self.Kf_pos_inv)
        self.sigf_pos = np.sqrt(np.diag(self.Kf_pos))

        pass
    

class GPT_log_grid:
    def __init__(self,
        H: sps.csr_matrix,
        ray:rt1raytrace.Ray,
        Kernel: rt1kernel.Kernel2D_grid,
        ) -> None:
        self.H = H  
        self.Kernel = Kernel
        self.ng = Kernel.R_grid.size
        self.im_shape = ray.shape
        pass

    def set_priori(self,
        K :np.ndarray,
        f_pri :np.ndarray | float = 0,
        regularization:float = 1e-6,
        ):
        K += regularization*np.eye(self.ng)

        self.K_inv = np.linalg.inv(K)
        self.f_pri = f_pri

    def set_sig(self,
        sig_array:np.ndarray,
        g_obs:np.ndarray,
        sig_scale:float=1.0,
        num:int=0,
        ):
        self.g_obs=g_obs.reshape(*self.im_shape)
        self.sig_scale = sig_scale
        sig_array = sig_array.flatten()
        g_obs = g_obs.flatten()
        self.sig_inv = 1/sig_array
        #self.sig2_inv = 1/sig_array**2
        H    = self.H

        self.Sigi_obs = self.sig_inv*(g_obs)
        self.sigiH = sps.csr_matrix(sps.diags(self.sig_inv) @ H )
        sigiH_t = sps.csr_matrix( self.sigiH.T )

        #self.Hsig2iH  = (self.sigiH.T @ self.sigiH).toarray() 
        # self.Hsig2iH = sparse_dot_mkl.gram_matrix_mkl(sigiH_t,transpose=True,dense=True)　#2時間溶かした戦犯
        self.Hsig2iH = sparse_dot_mkl.dot_product_mkl(sigiH_t,self.sigiH ,dense=True)

    
    def check_diff(self,
        f:np.ndarray):
            
        fig,ax = plt_subplots(1,3,figsize=(10,4))
        ax = ax[0][:]
        g = self.H @ np.exp(f.flatten())

        g = g.reshape(*self.im_shape)
        imshow_cbar(ax[0],g,origin='lower')
        ax[0].set_title('Hf')
        vmax = (abs(g-self.g_obs)).max()
        imshow_cbar(ax= ax[1],im0 = g-self.g_obs,vmin=-vmax,vmax=vmax,cmap='RdBu_r',origin='lower')
        ax[1].set_title('diff_im')
        
        ax[2].hist((g-self.g_obs).flatten(),bins=50)
        ax[2].tick_params( labelleft=False)
        plt.show()

    
    def calc_core_fast(self,
        f:np.ndarray,
        num:int=0,
        ):
        r_f = f - self.f_pri
        exp_f = np.exp(f)
        fxf = np.einsum('i,j->ij',exp_f,exp_f)
        
        SiR = self.sigiH @ exp_f - self.Sigi_obs

        c1 = 1/self.sig_scale**2 *(self.sigiH.T @ SiR) * exp_f #self.sigiH.T @ SiR =  self.Hsig2iH  @ exp_f -  self.sigiH.T@ self.Sigi_obs
        C1 = 1/self.sig_scale**2 *self.Hsig2iH * fxf 

        Psi_df   = -c1 - self.K_inv @ r_f 

        Psi_dfdf = -C1 - np.diag(c1) - self.K_inv

        DPsi = Psi_dfdf
        NPsi = Psi_df
        loss = abs(NPsi).mean()

        delta_f = - np.linalg.solve(DPsi,NPsi)

        delta_f[delta_f<-3] = -3
        delta_f[delta_f>+3] = +3

        return delta_f,loss
    
    def set_postprocess(self,
        f:npt.NDArray[np.float64],
        ):
        exp_f = np.exp(f)
        fxf = np.einsum('i,j->ij',exp_f,exp_f)
        
        SiR = self.sigiH @ exp_f - self.Sigi_obs

        c1 = 1/self.sig_scale**2 *(self.sigiH.T @ SiR) * exp_f #self.sigiH.T @ SiR =  self.Hsig2iH  @ exp_f -  self.sigiH.T@ self.Sigi_obs
        C1 = 1/self.sig_scale**2 *self.Hsig2iH * fxf 

        Psi_dfdf = -C1 - np.diag(c1) - self.K_inv

        DPsi = Psi_dfdf
        self.Kf_pos_inv = -DPsi
        self.Kf_pos     = np.linalg.inv(self.Kf_pos_inv)
        self.sigf_pos = np.sqrt(np.diag(self.Kf_pos))

        pass
"""

class GPT_log_torch:
    import torch
    def __init__(self,
        Obs: rt1kernel.Observation_Matrix_integral,
        Kernel: rt1kernel.Kernel2D_scatter,
        ) -> None:
        self.Obs = Obs
        self.rI = Obs.rI 
        self.zI = Obs.zI 
        self.nI = Obs.zI.size  
        self.Kernel = Kernel
        pass

    def set_kernel(self,
        K :np.ndarray,
        f_pri :np.ndarray = 0,
        regularization:float = 1e-6,
        ):
        K += regularization*np.eye(self.nI)

        self.K_inv = np.linalg.inv(K)
        self.f_pri = f_pri

    def set_sig(self,
        sigma:np.ndarray,
        g_obs:np.ndarray,
        num:int=0,
        ):
        self.g_obs=g_obs
        sigma = sigma.flatten()
        g_obs = g_obs.flatten()
        self.sig_inv = 1/sigma
        self.sig2_inv = 1/sigma**2
        H    = self.Obs.Hs[num].H

        self.Sigi_obs = self.sig_inv*(g_obs)
        self.sigiH = sps.csr_matrix(sps.diags(self.sig_inv) @ H )

        self.Hsig2iH = (self.sigiH.T @ self.sigiH).toarray() 
        

    def calc_core(self,
        f:np.ndarray,
        num:int=0
        ):
        Exist = self.Obs.Hs[num].Exist
        E = sps.csr_matrix(Exist@sps.diags(f))
        Exp =  E.expm1() + Exist
        
        SiHE  :sps.csr_matrix = self.sigiH.multiply(Exp)
        SiR = np.array(SiHE.sum(axis=1)).flatten() - self.Sigi_obs
        r_f = f - self.f_pri

        c1 = (SiHE.T @ SiR) 

        C1 = (SiHE.T @ SiHE)

        Psi_df   = -c1 - self.K_inv @ r_f 

        Psi_dfdf = -C1 - np.diag(c1) - self.K_inv

        DPsi = Psi_dfdf
        NPsi = Psi_df

        delta_f = - np.linalg.solve(DPsi,NPsi)

        delta_f[delta_f<-3] = -3
        delta_f[delta_f>+3] = +3

        return delta_f
    
    def check_diff(self,
        f:np.ndarray):
            
        fig,ax = plt.subplots(1,3,figsize=(10,4))
        g = self.Obs.Hs[0].projection(np.exp(f))
        imshow_cbar(fig,ax[0],g)
        ax[0].set_title('Hf')
        vmax = (abs(g-self.g_obs)).max()
        imshow_cbar(fig,ax[1],g-self.g_obs,vmin=-vmax,vmax=vmax,cmap='turbo')
        ax[1].set_title('diff_im')
        
        ax[2].hist((g-self.g_obs).flatten(),bins=50)
        plt.show()

    
    def calc_core_fast(self,
        f:np.ndarray,
        num:int=0
        ):
        r_f = f - self.f_pri
        exp_f = np.exp(f)
        fxf = np.einsum('i,j->ij',exp_f,exp_f)
        
        SiR = self.sigiH @ exp_f - self.Sigi_obs

        c1 = (self.sigiH.T @ SiR) * exp_f
        C1 = self.Hsig2iH * fxf 

        Psi_df   = -c1 - self.K_inv @ r_f 

        Psi_dfdf = -C1 - np.diag(c1) - self.K_inv

        DPsi = Psi_dfdf
        NPsi = Psi_df

        delta_f = - np.linalg.solve(DPsi,NPsi)

        delta_f[delta_f<-3] = -3
        delta_f[delta_f>+3] = +3

        return delta_f

"""
        