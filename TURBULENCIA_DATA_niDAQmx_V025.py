"""
# Instituto Superior Tecnico, University of Lisbon
## Laboratory data acquisition script <Version 0.24 2021/11/22>
___
Copyright (C) 2018-2022 by Joao C. C. Henriques <joaochenriques@tecnico.pt>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
<http://www.gnu.org/licenses/>
___
"""

#~################################################################################################
#~  
#~################################################################################################

import nidaqmx, sys, h5py, datetime, os
from nidaqmx.constants import Edge, AcquisitionType, TerminalConfiguration, VoltageUnits
from nidaqmx.stream_readers import AnalogMultiChannelReader
import numpy as np

#~################################################################################################
#~  
#~################################################################################################

import matplotlib.pyplot as plt
import matplotlib.animation as animation

plt.matplotlib.style.use('classic')
plt.matplotlib.rcParams['figure.facecolor'] = '1.0'
plt.matplotlib.rcParams['mathtext.fontset'] = 'stix'
plt.matplotlib.rcParams['font.family'] = 'STIXGeneral'
plt.matplotlib.rcParams['xtick.labelsize'] = 'medium'
plt.matplotlib.rcParams['ytick.labelsize'] = 'medium'
plt.matplotlib.rcParams['legend.fontsize'] = 'medium'

#~################################################################################################
#~  
#~################################################################################################
plt.switch_backend('Qt5Agg')
print( plt.get_backend() )

MsgBox = plt.get_backend() == 'Qt5Agg'
if MsgBox:
    from matplotlib.backends.qt_compat import QtWidgets
    qApp = QtWidgets.QApplication(sys.argv)
    plt.matplotlib.rcParams['figure.dpi'] = qApp.desktop().physicalDpiX()

#~################################################################################################
#~
#~################################################################################################

class ChData:
    def __init__( self, DevChName, SignalName, Units, V_min, V_max, Coeffs, ClipVoltage ):
        self.DevChName = DevChName
        self.SignalName = SignalName
        self.Units = Units
        self.V_min = V_min
        self.V_max = V_max
        self.Coeffs = Coeffs
        self.ClipVoltage = ClipVoltage
        return

#~################################################################################################
#~ BEGIN User config & input 
#~################################################################################################

DAQ_Prefix    = 'Turbulence_Lab_Group_01'   # Name
DAQ_Test_Name = 'Central_Readings'

# NI 6008 Maximum sample rate, fs = 10 kHz
DAQ_fs         = 10000   # Hz sampling frequency
DAQ_total_time = 4*60    # total time of experiment in seconds

#~################################################################################################
#~ END User config & input 
#~################################################################################################
CalibPoly = ( 335.55807, -1009.82047, 1227.90020, -646.40401, 121.36738, 0.0 )

DAQ_Chs = [ ChData( DevChName='Dev1/ai0', SignalName='hotwire', Units='[m/s]',
                    V_min=0.0,  V_max=1.0, Coeffs=CalibPoly, ClipVoltage=(0.0,1.0) ), ]

DAQ_H5_FileName = '%s_Tests.h5' % DAQ_Prefix

#~================================================================================================
DAQ_event_time = 1  # time between plot update in seconds
DAQ_timeout = 2

#~################################################################################################
#~ END User config & input 
#~################################################################################################

if os.path.exists( DAQ_H5_FileName ):
    hf = h5py.File( DAQ_H5_FileName, 'r' )
    Error = DAQ_Test_Name in list( hf.keys() )
    hf.close()

    if Error:
        ErrorStr = 'DAQ_Test_Name \'%s\' already performed!' % DAQ_Test_Name
        if MsgBox:
            QtWidgets.QMessageBox.critical( None, 'LAB_niDAQmx', ErrorStr )
        else:
            print( ErrorStr )
        exit(1)

#~################################################################################################
#~ 
#~################################################################################################

print()
print( DAQ_Test_Name )
print()

if MsgBox:
    QtWidgets.QMessageBox.about( None, 'LAB_niDAQmx', 'Ready to start!' )

#~################################################################################################
#~ 
#~################################################################################################

SamplesPerEvent = int( DAQ_fs * DAQ_event_time )
NumChs = len( DAQ_Chs )
BufferSizePerCh = int( DAQ_fs * DAQ_total_time )
Buffers = np.zeros( ( NumChs, BufferSizePerCh ) )
EventBuffers = np.zeros( ( NumChs, SamplesPerEvent ), dtype = np.float64 )

ts = np.linspace( 0, DAQ_total_time, BufferSizePerCh, endpoint=False )
PltLines = [None]*NumChs

#~################################################################################################
#~ 
#~################################################################################################
#
# Create figure for plotting
fig = plt.figure( 1 )
plt.ylim( (-10.0, 50.0 ) )
plt.xlabel( 'Time [s]')

for Ch in range( NumChs ):
    Buffer = np.polyval( DAQ_Chs[Ch].Coeffs, Buffers[Ch] )
    PltLines[Ch], = plt.plot( ts, Buffer, label= '%s %s' % ( DAQ_Chs[Ch].SignalName, DAQ_Chs[Ch].Units ) )
plt.legend( loc='upper right')

#~################################################################################################
#~ 
#~################################################################################################

def animate( i, xs, ys ):
    for Ch in range( NumChs ):
        ys_clip = np.clip( ys[Ch], DAQ_Chs[Ch].Clip[0], DAQ_Chs[Ch].Clip[1] )
        Buffer = np.polyval( DAQ_Chs[Ch].Coeffs, ys_clip )
        PltLines[Ch].set_ydata( Buffer )  

ani = animation.FuncAnimation( fig, animate, fargs = (ts,Buffers), interval = 1000 )

#~################################################################################################
#~ 
#~################################################################################################

def EveryNSamps( task_handle, every_n_samples_event_type,
                       num_samples, callback_data ):
    
    EveryNSamps.reader.read_many_sample( EveryNSamps.EventBuffers, 
                                number_of_samples_per_channel = num_samples,
                                timeout = DAQ_timeout )

    indx = EveryNSamps.next
    for Ch in range( NumChs ):
        EveryNSamps.Buffers[ Ch, indx: indx + num_samples ] = EveryNSamps.EventBuffers[Ch,:]

    EveryNSamps.next = EveryNSamps.next + num_samples 

    print( 'Acquired samples = %d' % ( EveryNSamps.next ) ) 
    return 0       

# 'kind of static variables of the function 'EveryNSamps'
EveryNSamps.Buffers = Buffers
EveryNSamps.EventBuffers = EventBuffers
EveryNSamps.reader = None
EveryNSamps.next = 0

#~################################################################################################
#~ 
#~################################################################################################

def EventDone( task_handle, status, callback_data ):
    print('DAQ done')
    EventDone.Done = True
    return 0
EventDone.Done = False

#~################################################################################################
#~ 
#~################################################################################################

with nidaqmx.Task() as ai_task, nidaqmx.Task() as do_task:  

    plt.pause( DAQ_event_time )

    for ChData in DAQ_Chs: 
        ai_task.ai_channels.add_ai_voltage_chan( ChData.DevChName, 
                                              terminal_config = TerminalConfiguration.BAL_DIFF, 
                                              min_val = ChData.V_min, max_val=ChData.V_max, 
                                              units = VoltageUnits.VOLTS)

    ai_task.timing.cfg_samp_clk_timing( DAQ_fs, 
                                        active_edge = Edge.RISING, 
                                        sample_mode = AcquisitionType.FINITE, 
                                     samps_per_chan = BufferSizePerCh )

    EveryNSamps.reader = AnalogMultiChannelReader( ai_task.in_stream )    

    ai_task.register_every_n_samples_acquired_into_buffer_event( SamplesPerEvent, EveryNSamps )
    ai_task.register_done_event( EventDone )
    ai_task.start()

    while EventDone.Done == False:
        plt.pause( DAQ_event_time )

    ai_task.stop()

#~################################################################################################
#~ 
#~################################################################################################

if MsgBox:
    QtWidgets.QMessageBox.about( None, 'LAB_niDAQmx', 'End of data acquisition' )

plt.show()

#~################################################################################################
#~ 
#~###############################################################################################

now = str( datetime.datetime.now().replace(microsecond=0) )
now = now.replace( ' ', '_' )
now = now.replace( ':', '' )
now = now.replace( '-', '' )

hf = h5py.File( DAQ_H5_FileName, 'a' )

grp = hf.create_group( DAQ_Test_Name )

# writing strings requires conversion to arrays of bytes
dt_str = h5py.special_dtype( vlen = bytes )
when = np.array( str(now), dtype = dt_str )

dset = hf.create_dataset( DAQ_Test_Name + '/TimeStamp', data = when )
dset = hf.create_dataset( DAQ_Test_Name + '/time', data = ts )
dset = hf.create_dataset( DAQ_Test_Name + '/fsample', data = DAQ_fs )

for Ch in range( NumChs ):
    DataName = DAQ_Test_Name + '/' + DAQ_Chs[Ch].SignalName 
    dset = hf.create_dataset( DataName + '_UNITS', data = DAQ_Chs[Ch].Units )
    dset = hf.create_dataset( DataName + '_VOLTS', data = Buffers[Ch] )
    DataUnits = np.clip( np.polyval( DAQ_Chs[Ch].Coeffs, Buffers[Ch] ), DAQ_Chs[Ch].Clip[0], DAQ_Chs[Ch].Clip[1] )
    dset = hf.create_dataset( DataName, data = DataUnits )

hf.close()

print( 'END of case:', DAQ_Test_Name )