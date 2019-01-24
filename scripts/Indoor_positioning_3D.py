"""
This python module is used to positioning in indoor environment based on UWB and IMU
"""
import sys, getopt

sys.path.append('.')
import RTIMU
import os.path
import threading
import time
import math
import operator
import socket
import os
import numpy as np
from pyquaternion import Quaternion
from numpy import linalg as LA
import EKF_6states as EKF6
from Queue import Queue

acc = np.zeros([1,3])
gro = np.zeros([1,3])
grop = np.zeros([1,3])
mag = np.zeros([1,3])

# Initialize EKF 6-states parameters 0.01s
ekf6 = EKF6.EKF_6states(0.01)

# IMU Initialization
SETTINGS_FILE = "RTIMULib"
s = RTIMU.Settings(SETTINGS_FILE)
imu = RTIMU.RTIMU(s)
if (not imu.IMUInit()):
	print ("IMU Initialize Failed.")
imu.setGyroEnable(True)
imu.setAccelEnable(True)
imu.setCompassEnable(True)

gyro_err_flag = 1
gyro_bias_flag = 1

# EKF Initial params
r2d = 180/np.pi
d2r = np.pi/180
# Euler error in deg
phierr = 0*0.5
thetaerr = -0*0.5
psierr = 0*0.5

dtheda_xh = phierr*d2r
dtheda_yh = thetaerr*d2r
dtheda_zh = psierr*d2r

bgx_h = 0
bgy_h = 0
bgz_h = 0

dq11 = 0
dq21 =0 
dq31 = 0
q1 = np.sqrt(1-np.square(dq11)-np.square(dq21)-np.square(dq31))
q2 = -dq11
q3 = -dq21
q4 = -dq31
dQerr = Quaternion(q1, q2, q3, q4)
Q_E_B = Quaternion(1, 0, 0, 0)
QE_B_m = dQerr.normalised * Q_E_B.normalised

bgx0=gyro_bias_flag*0.05*d2r
bgy0=gyro_bias_flag*(-0.05)*d2r
bgz0=gyro_bias_flag*0.05*d2r

s6_xz_h = np.zeros([6,1])
s6_xz_h[0,0] = phierr*d2r
s6_xz_h[1,0] = thetaerr*d2r
s6_xz_h[2,0] = psierr*d2r
s6_xz_h[3,0] = bgx0
s6_xz_h[4,0] = bgy0
s6_xz_h[5,0] = bgz0

s6_P00_z = np.zeros([6,6])
s6_P00_z[0,0] = np.square(phierr*d2r)
s6_P00_z[1,1] = np.square(thetaerr*d2r)
s6_P00_z[2,2] = np.square(psierr*d2r)
s6_P00_z[3,3] = np.square(bgx0)
s6_P00_z[4,4] = np.square(bgy0)
s6_P00_z[5,5] = np.square(bgz0)

sig_x_arw = gyro_err_flag*0.02
sig_y_arw = gyro_err_flag*0.02
sig_z_arw = gyro_err_flag*0.02
sig_x_rrw = gyro_err_flag*0.02/3600
sig_y_rrw = gyro_err_flag*0.02/3600
sig_z_rrw = gyro_err_flag*0.02/3600

s6_Q_z = np.zeros([6,6])
s6_Q_z[0,0] = np.square(sig_x_arw)
s6_Q_z[1,1] = np.square(sig_y_arw)
s6_Q_z[2,2] = np.square(sig_z_arw)
s6_Q_z[3,3] = np.square(sig_x_rrw)
s6_Q_z[4,4] = np.square(sig_y_rrw)
s6_Q_z[5,5] = np.square(sig_z_rrw)

# IMU Thread
class Get_IMU_Data(threading.Thread):
	def __init__(self, t_name, queue):
		threading.Thread.__init__(self, name = t_name)
		self.data = queue
	def run(self):
		while True:
			if imu.IMURead():
				data = imu.getIMUData()
				acc = data["accel"]
				# save last gyro data
				grop = gro
				gro = data["gyro"]
				mag = data["compass"]
			time.sleep(0.01)

# DWM Thread
class Get_UWB_Data(threading.Thread):
	def __init__(self, t_name, queue):
		threading.Thread.__init__(self, name = t_name)
		self.data = queue
	def run(self):
		while True:
			#print ("task-UWB")
			time.sleep(1)

# 6-states EKF thread
class EKF_Cal_Euler(threading.Thread):
	def __init__(self, t_name, queue):
		threading.Thread.__init__(self, name = t_name)
		self.data = queue
	def run(self):
		while True:
			# predict
			s6_P00_z = ekf6.Predict(grop[0], grop[1], grop[2], gro[0], gro[1], gro[2], bgx_h, bgy_h, bgz_h, QE_B_m, s6_xz_h, s6_P00_z, s6_Q_z)
			# update
			s6_P00_z, s6_z_update = ekf6.Update(acc[0], acc[1], acc[2], mag[0], mag[1], mag[2], )
			# measurement

			time.sleep(0.01)

# main Thread
def main():
	queue = Queue()
	imu = Get_IMU_Data('IMU.', queue)
	uwb = Get_UWB_Data('UWB.', queue)
	euler = EKF_Cal_Euler('Euler.',queue)
	imu.start()
	uwb.start()
	euler.start()
	imu.join()
	uwb.join()
	euler.join()
	print ('All threads terminate!')


if __name__ == '__main__':
	main()