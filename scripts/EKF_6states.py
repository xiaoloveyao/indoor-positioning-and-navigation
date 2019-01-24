"""
This python module contains 6-states EKF's pridict, update and measurement function
output is Euler angle.
"""

# import sys, getopt

# sys.path.append('.')
# import os.path
# import time
# import math
# import operator
# import socket
# import os
import numpy as np
from pyquaternion import Quaternion
from scipy import linalg as LA
from sklearn.preprocessing import normalize

class EKF_6states(object):
    """docstring for EKF_6states"""
    def __init__(self, timestemp):
        super(EKF_6states, self).__init__()
        self._d2r = np.pi/180
        self._r2d = 180/np.pi
        self._Mag = 45.488
        self._Angle_I = 1*37.45*self._d2r;
        self._Angle_D = 1*4.57*self._d2r;
        self._dt = timestemp

    def Predict(self, wxp, wyp, wzp, wx, wy, wz, bgx_h, bgy_h, bgz_h, QE_B_m, s6_xz_h, s6_P00_z, s6_Q_z):
        s6_F_z = np.zeros([6,6])

        DC_E_B_m, QE_B_m = self.DCM_calculate(wxp, wyp, wzp, wx, wy, wz, bgx_h, bgy_h, bgz_h, QE_B_m)

        s6_F_z[0,3] = -DC_E_B_m[0,0]
        s6_F_z[0,4] = -DC_E_B_m[1,0]
        s6_F_z[0,5] = -DC_E_B_m[2,0]

        s6_F_z[1,3] = -DC_E_B_m[0,1]
        s6_F_z[1,4] = -DC_E_B_m[1,1]
        s6_F_z[1,5] = -DC_E_B_m[2,1]

        s6_F_z[2,3] = -DC_E_B_m[0,2]
        s6_F_z[2,3] = -DC_E_B_m[1,2]
        s6_F_z[2,3] = -DC_E_B_m[2,2]

        s6_phi_z = LA.expm(s6_F_z*self._dt)
        s6_xz_h = s6_phi_z.dot(s6_xz_h)
        s6_P00_z = s6_phi_z.dot(s6_P00_z).dot(s6_phi_z.T) + s6_Q_z*self._dt

        return s6_P00_z, QE_B_m

    def Update(self, ax, ay, az, mx, my, mz, s6_P00_z, s6_H, s6_R):
        C_E_B_e = self.TRIAD(ax, ay, az, mx, my, mz)
        tmp = self.rotMat2euler(C_E_B_e.T)
        C_E_B_e = self.euler2rotMat(-tmp[1], tmp[0], tmp[2])
        Q_E_B_e = self.rotMat2quatern(C_E_B_e)
        Q_B_E_m = Q_E_B_e.conjugate
        dQ = Q_E_B_e.normalised * Q_B_E_m.normalised
        d_theta = self.quatern2euler(dQ.normalised)
        # Form the measurement residuals or mu
        s6_Mu_z = d_theta
        # Computer the Kalman filter gain matrix K
        s6_K_z = s6_P00_z.dot(s6_H.T).dot( LA.inv(s6_H.dot(s6_P00_z).dot(s6_H.T) + s6_R) )
        # Computer the correction vectors
        s6_z_update = s6_K_z.dot(s6_Mu_z.T)
        # Perform the Kalman filter error covariance matrix P updates
        s6_P00_z = (np.identity(6) - s6_K_z.dot(s6_H)).dot(s6_P00_z)

        return s6_P00_z, s6_z_update

    def Measurement(self, dtheda_xh, dtheda_yh, dtheda_zh, bgx_h, bgy_h, bgz_h, s6_z_update, w_EB_B_xm, w_EB_B_ym, w_EB_B_zm):

        dtheda_xh = dtheda_xh + s6_z_update[0]
        dtheda_yh = dtheda_yh + s6_z_update[1]
        dtheda_zh = dtheda_zh + s6_z_update[2]

        bgx_h = bgx_h + s6_z_update[3]
        bgy_h = bgy_h + s6_z_update[4]
        bgz_h = bgz_h + s6_z_update[5]

        w_EB_B_xm = w_EB_B_xm - bgx_h
        w_EB_B_ym = w_EB_B_ym - bgy_h
        w_EB_B_zm = w_EB_B_zm - bgz_h

        return dtheda_xh, dtheda_yh, dtheda_zh, bgx_h, bgy_h, bgz_h, w_EB_B_xm, w_EB_B_ym, w_EB_B_zm

    # get direction cosine matrix from gyroscopemeter
    def DCM_calculate(self, wxp, wyp, wzp, wx, wy, wz, bgx_h, bgy_h, bgz_h, QE_B_m):
        wx = wx - bgx_h
        wy = wy - bgy_h
        wz = wz - bgz_h

        d1 = wx * self._dt / 2
        d2 = wy * self._dt / 2
        d3 = wz * self._dt / 2

        d1p = wxp * self._dt / 2
        d2p = wyp * self._dt / 2
        d3p = wzp * self._dt / 2

        d0_s = np.square(d1) + np.square(d2) + np.square(d3)

        q1 = 1 - d0_s/2
        q2 = d1 - (d0_s*d1 + d3p*d2 + d2p*d3)/6
        q3 = d2 - (d0_s*d2 + d1p*d3 + d3p*d1)/6
        q4 = d3 - (d0_s*d3 + d2p*d1 + d1p*d2)/6

        delta_Q = Quaternion(q1, -q2, -q3, -q4)
        QE_B_m = delta_Q.normalised * QE_B_m.normalised
        DC_E_B_m = QE_B_m.rotation_matrix

        return DC_E_B_m, QE_B_m

    # Get Rotation matrix from euler angle in rad
    def euler2rotMat(self, phi, theta, psi):
        R = np.zeros([3,3])

        R[0,0] = np.cos(psi)*np.cos(theta)
        R[0,1] = -np.sin(psi)*np.cos(phi) + np.cos(psi)*np.sin(theta)*np.sin(phi)
        R[0,2] = np.sin(psi)*np.sin(phi) + np.cos(psi)*np.sin(theta)*np.cos(phi)

        R[1,0] = np.sin(psi)*np.cos(theta)
        R[1,1] = np.cos(psi)*np.cos(phi) + np.sin(psi)*np.sin(theta)*np.sin(phi)
        R[1,2] = -np.cos(psi)*np.sin(phi) + np.sin(psi)*np.sin(theta)*np.cos(phi)

        R[2,0] = -np.sin(theta)
        R[2,1] = np.cos(theta)*np.sin(phi)
        R[2,2] = np.cos(theta)*np.cos(phi)

        return R

    def rotMat2quatern(self, R):
        K = np.zeros([4,4])

        K[0,0] = (1/3)*( R[0,0] - R[1,1] - R[2,2] )
        K[0,1] = (1/3)*( R[1,0] + R[0,1] )
        K[0,2] = (1/3)*( R[2,0] + R[0,2] )
        K[0,3] = (1/3)*( R[1,2] - R[2,1] )

        K[1,0] = (1/3)*( R[1,0] + R[0,1] )
        K[1,1] = (1/3)*( R[1,1] - R[0,0] - R[2,2] )
        K[1,2] = (1/3)*( R[2,1] + R[1,2] )
        K[1,3] = (1/3)*( R[2,0] - R[0,2] )

        K[2,0] = (1/3)*( R[2,0] + R[0,2] )
        K[2,1] = (1/3)*( R[2,1] + R[1,2] )
        K[2,2] = (1/3)*( R[2,2] - R[0,0] - R[1,1] )
        K[2,3] = (1/3)*( R[0,1] - R[1,0] )

        K[3,0] = (1/3)*( R[1,2] - R[2,1] )
        K[3,1] = (1/3)*( R[2,0] - R[0,2] )
        K[3,2] = (1/3)*( R[0,1] - R[1,0] )
        K[3,3] = (1/3)*( R[0,0] + R[1,1] + R[2,2] )

        vals,vecs = LA.eigh(K)
        q = Quaternion([vecs[3,3], vecs[0,3], vecs[1,3], vecs[2,3]])
        return q

    def rotMat2euler(self, R):
        phi = np.arctan2(R[2,1], R[2,2])
        theta = -np.arctan( R[2,0]/np.sqrt( 1 - np.square(R[2,0]) ) )
        psi = np.arctan2(R[1,0], R[0,0])

        euler = np.array([phi, theta, psi])
        return euler

    def quatern2euler(self, q):
        R = self.quatern2rotMat(q)
        euler = self.rotMat2euler(R)
        return euler

    def quatern2rotMat(self, q):
        R = np.zeros([3,3])

        R[0,0] = 2*np.square(q[0])-1+2*np.square(q[1])
        R[0,1] = 2*(q[1]*q[2]+q[0]*q[3])
        R[0,2] = 2*(q[1]*q[3]-q[0]*q[2])

        R[1,0] = 2*(q[1]*q[2]-q[0]*q[3])
        R[1,1] = 2*np.square(q[0])-1+2*np.square(q[2])
        R[1,2] = 2*(q[2]*q[3]+q[0]*q[1])

        R[2,0] = 2*(q[1]*q[3]+q[0]*q[2])
        R[2,1] = 2*(q[2]*q[3]-q[0]*q[1])
        R[2,2] = 2*np.square(q[0])-1+2*np.square(q[3])

        return R

    def TRIAD(self, ax, ay, az, mx, my, mz):
        acc_g = np.array([0, 0, -9.8])
        mag_E = np.array([self._Mag*np.cos(self._Angle_I)*np.sin(self._Angle_D), self._Mag*np.cos(self._Angle_I)*np.cos(self._Angle_D), -self._Mag*np.sin(self._Angle_I)])

        a_B = np.array([ax, ay, az])
        #q_B = a_B/LA.norm(a_B)
        q_B = normalize(a_B)
        m_B = np.array([mx, my, mz])
        #m_B_u = m_B/LA.norm(m_B)
        m_B_u = normalize(m_B)
        r_B_n = np.cross(q_B, m_B_u)
        #r_B = r_B_n/LA.norm(r_B_n)
        r_B = normalize(r_B_n)
        s_B = np.cross(q_B, r_B)
        M_B = np.array([s_B, r_B, q_B])
        norm_M_B = M_B/LA.norm(M_B)

        q_E = acc_g/LA.norm(acc_g)
        mag_E_u = mag_E/LA.norm(mag_E)
        r_E_n = np.cross(q_E, mag_E_u)
        r_E = r_E_n/LA.norm(r_E_n)
        s_E = np.cross(q_E, r_E)
        M_E = np.array([s_E, r_E, q_E])
        norm_M_E = M_E/LA.norm(M_E)

        C_E_B_e = norm_M_B.dot(norm_M_E.T)
        return C_E_B_e
