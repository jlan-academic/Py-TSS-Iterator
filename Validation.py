## EXPECTED FORMAT OF INPUT DATA // INPUT A // MATERIAL DATA
# CSV file that was the output of the IFD script.
# Columns are: Index (blank label), Exp Tot Strain [-], Exp Plastic Strain [-], Exp Force [N], Starting Stress [Pa],
#	Est Displacement [m], True Stress [Pa], FEA Strain [-], FEA Force [N], FEA Displacement [m], Force Error [N], Strain Error %
# First row is yield and last row is failure.

## EXPECTED FORMAT OF INPUT DATA // INPUT B // EXPERIMENTAL FORCE-DISPLACEMENT DATA
# CSV file with columns: Index (blank label), Exp Force [N], Exp Displacement [m]
# Where the first row is non-zero, and the final row is failure.
# With ideally 30-40 total rows.

## INSTRUCTIONS, USEFUL WHEN RUNNING FROM COMMANDLINE
print('Use CTRL+C at any time to interrupt and terminate this script.')
print('If Ansys is running when the script is interrupted, you will have to wait for it to finish.')

## IMPORT
import os
import subprocess
import getpass
from shutil import copy2, copytree, rmtree
from datetime import datetime
import time
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from CommonFunctions import *
from UserFunctions import *

# ESTABLISH OUTPUT DIRECTORY AND LOGGING FILE
output_dir = dirPath('Input directory to save output data to. Note, this will overwrite any previously saved file from this script.')
log = LoggingFile(output_dir + '/Val-log.txt')
log.diagnostic('Script started at '+str(datetime.now()))

# SETUP OUTPUT FOLDERS
validation_dir = createFolder(output_dir, 'validation', log)
ansys_dir = createFolder(output_dir, 'ansys_validation', log)

## PART 1 - PLOT AND REVIEW ERRORS FROM THE IFD PROCESS
# READ IFD OUTPUT FILE (INPUT A)
dir_a = dirPath('Input directory of CSV file containing IFD output')
input_file_a = (dir_a + '/results.csv')
df_ifd = pd.read_csv(input_file_a)
log.toconsole('IFD input file read.')

df_error = df_ifd.drop([df_ifd.index.values[0], df_ifd.index.values[-1]])

# PLOT FORCE CONVERGENCE ERROR
plot1 = plt.figure()
ax = plot1.add_subplot(1,1,1)
ax.plot(df_error['Exp Tot Strain [-]'], df_error['Force Error [N]'])
ax.set_xlabel('Equivalent True Strain [-]')
ax.set_ylabel('Force Error [N]')
plot1_path = (validation_dir+'/1_ForceError.png')
plot1.savefig(plot1_path)
log.diagnostic('Plot saved to: '+str(plot1_path))

# PLOT STRAIN CONVERGENCE ERROR
plot2 = plt.figure()
ax = plot2.add_subplot(1,1,1)
ax.plot(df_error['Exp Tot Strain [-]'], df_error['Strain Error %'])
ax.set_xlabel('Equivalent True Strain [-]')
ax.set_ylabel('Strain Error %')
plot2_path = (validation_dir+'/2_StrainError.png')
plot2.savefig(plot2_path)
log.diagnostic('Plot saved to: '+str(plot2_path))

# CHECK FOR ERRORS OUTSIDE TOLERANCE
# FORCE CONVERGENCE TOLERANCE
A0 = getValue('For calculation of the force convergene tolerance, input area (excluding symmetries, in m^2).')
force_criterion = A0 * 0.5e6
strain_criterion = 0.25
if any(abs(x) > force_criterion for x in df_error['Force Error [N]'].tolist()):
	log.toconsole('For at least one datapoint, the force convergence criterion was not met. Check the diagnostic files for details.')
if any(abs(x) > strain_criterion for x in df_error['Strain Error %'].tolist()):
	log.toconsole('For at least one datapoint, the strain convergence criterion was not met. Check the diagnostic files for details.')

## PART 2 - RUN THE VALIDATION CASE
# READ EXPERIMENTAL DATA FILE (INPUT B)
input_file_b = filePath('Input directory of input CSV file for force-displacement data', 'Input name of input CSV file e.g. data_1.csv')
df_exp = pd.read_csv(input_file_b, skiprows=1, names = ['Exp Force [N]', 'Exp Displacement [m]'], usecols = [1,2])
log.toconsole('Experimental force-displacement data file read.')

# SET UP ELASTIC MATERIAL PROPERTIES
elastic_modulus = round(getValue('Input elastic modulus [GPa]')*10**9, 1)
poissons_ratio = round(getValue("Input Poisson's ratio"), 2)
elasticfile = ansys_dir+"/Youngs.csv"
write_elastic(elastic_modulus, poissons_ratio, elasticfile, log)

# SET UP PLASTICITY DATAFRAME (FOR INPUT TO ANSYS)
df_matl = df_ifd.drop(axis=1, labels=['Exp Tot Strain [-]', 'Exp Force [N]', 'Starting Stress [Pa]', 'Est Displacement [m]', 'FEA Strain [-]', 'FEA Force [N]', 'FEA Displacement [m]', 'Force Error [N]', 'Strain Error %'])
df_matl = df_matl.drop(0)
df_matl = df_matl.reset_index(drop=True, inplace=False)
df_matl['Temperature'] = 22
cols = ['Temperature', 'Exp Plastic Strain [-]', 'True Stress [Pa]']
df_matl = df_matl[cols]
plasticfile = (ansys_dir + '/data_points.csv')
df_matl.to_csv(plasticfile, index=False, header=True)

# SET UP ANSYS REFERENCES
proj_direc = dirPath('Input directory of Workbench skeleton project')
proj_file = getString('Input name of workbench skeleton project e.g. myproject (EXCLUDE file extension)')
skeleton_project = copy_project(proj_direc, proj_file, ansys_dir, log)
exportfile = (ansys_dir+"/Ansys_Export.csv")
ansys_script_path = (ansys_dir+"/Ansys_script.wbjn")

# ADMIN CREDENTIALS FOR ACCESSING ADMIN COMMANDLINE
uname = str(input('Input admin windows username'))
pword = getpass.getpass("Enter your password: ")

# SET UP OUTPUT DATAFRAME
df_output = df_exp
df_output['FEA Force [N]'] = np.NaN

# PREPARE THE ITERATOR
index = list(df_exp.index)
iterations = 0
timeout = 'default'

# RUN SIMULATION POINTS FOR F-D CURVE
timeout = 'default'
for i in index:
	#Set up variables
	log.toconsole('\n************************\n'+str(datetime.now())+' i= ' + str(i) + ' of ' + str(index[-1]))
	disp = df_exp.at[i, 'Exp Displacement [m]']
	# Run ansys and read data
	create_ansys_script(disp, log, elasticfile, plasticfile, exportfile, ansys_script_path)
	log.diagnostic('Ansys script created successfully.')
	log.toconsole(str(datetime.now())+' Running Ansys... 5s delay to start...')
	time.sleep(5) # Delay to allow ghost processes to end
	t = run_ansys(log, ansys_dir, ansys_script_path, skeleton_project, uname, pword, proj_direc, proj_file, timeout)
	timeout = t*3
	iterations += 1
	FEA_strain, P_FEA, FEA_disp, max_strain = read_ansys(log, exportfile)
	df_output.at[i, 'FEA Force [N]'] = P_FEA
log.toconsole('************************\nFEA runs complete.')

# CLEAN UP VARIABLESE AND FILES
pword='' # Clear the password at earliest opportunity, for security (password not retained).
rmtree(ansys_dir + '/copied-project_files')
os.remove(ansys_dir + '/copied-project.wbpj')

## PART 3 - PLOT DATA OF INTEREST FROM THE TEST
#INSERT ZERO ROW
zero_row = {'Exp Force [N]':0, 'Exp Displacement [m]':0, 'FEA Force [N]':0}
df_output = df_output.append(zero_row, ignore_index=True)
df_output = df_output.sort_values(by=['Exp Displacement [m]'], inplace=False)
df_output = df_output.reset_index(drop=True, inplace=False)
log.diagnostic('Created zero row in final force-displacement dataset.')

# OUTPUT RESULTS TO CSV
df_output_csv_path=(validation_dir+"/validation_results.csv")
df_output.to_csv(df_output_csv_path, index=True, header=True)
log.toconsole('Results CSV file saved as: ' + str(df_output_csv_path))

# PLOT TRUE STRESS STRAIN CURVE WITH STARTING CURVE
plot3 = plt.figure()
ax = plot3.add_subplot(1,1,1)
ax.plot(df_output['Exp Displacement [m]'], df_output['Exp Force [N]'], 'ro-', label='Experiment')
ax.plot(df_output['Exp Displacement [m]'], df_output['FEA Force [N]'], 'bo-', label='FEM')
ax.legend()
ax.set_xlabel('Displacement [m]')
ax.set_ylabel('Force [N]')
plot3_path = (validation_dir+'/3_ForceDisplacement.png')
plot3.savefig(plot3_path)
log.diagnostic('Plot saved to: '+str(plot3_path))

# TERMINATE SCRIPT
log.toconsole('IFD script finished successfully at '+str(datetime.now()))