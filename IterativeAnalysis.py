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
log = LoggingFile(output_dir + '/IFD-log.txt')
log.diagnostic('Script started at '+str(datetime.now()))

# SETUP OUTPUT FOLDERS
diagnostic_dir = createFolder(output_dir, 'diagnostic', log)
ansys_dir = createFolder(output_dir, 'ansys', log)
results_dir = createFolder(output_dir, 'results', log)

# SET UP DATAFRAME FOR ITERATIVE ANALYSIS
input_file = filePath('Input directory of input CSV file', 'Input name of input CSV file e.g. data_1.csv')
df_input = pd.read_csv(input_file, skiprows=1, names = ['Exp Tot Strain [-]', 'Exp Plastic Strain [-]', 'Exp Force [N]', 'Starting Stress [Pa]', 'Est Displacement [m]'], usecols = [1,2,3,4,5])
log.toconsole('Input file read.')

# SET UP ELASTIC MATERIAL PROPERTIES
elastic_modulus = round(getValue('Input elastic modulus [GPa]')*10**9, 1)
poissons_ratio = round(getValue("Input Poisson's ratio"), 2)
elasticfile = ansys_dir+"/Youngs.csv"
write_elastic(elastic_modulus, poissons_ratio, elasticfile, log)

# SET UP OUTPUT DATAFRAME
df_output = df_input
df_output['True Stress [Pa]'] = df_output['Starting Stress [Pa]']
df_output['FEA Strain [-]'] = np.NaN
df_output['FEA Force [N]'] = np.NaN
df_output['FEA Displacement [m]'] = np.NaN

# SET UP PLASTICITY DATAFRAME (FOR INPUT TO ANSYS)
df_matl = pd.DataFrame(data=None,columns=['temp','strain','stress'])
plasticfile = ansys_dir + '/data_points.csv'

# MANUALLY POPULATE YIELD ROW (i=0)
matl_row = {'temp':22, 'strain':df_output.at[0, 'Exp Plastic Strain [-]'] , 'stress':df_output.at[0, 'True Stress [Pa]']}
df_matl = df_matl.append(matl_row, ignore_index=True)
log.toconsole('Material dataset in Ansys is now:')
log.toconsole(str(df_matl))
df_matl.to_csv(plasticfile, index=False, header=True)
log.toconsole('Yield parameters entered for i=0')

# PREPARE THE ITERATOR
index = list(df_output.index)
index.pop(0)
iterations = 0
timeout = 'default'

# SET UP ANSYS REFERENCES
proj_direc = dirPath('Input directory of Workbench skeleton project')
proj_file = getString('Input name of workbench skeleton project e.g. myproject (EXCLUDE file extension)')
skeleton_project = copy_project(proj_direc, proj_file, ansys_dir, log)
exportfile = (ansys_dir+"/Ansys_Export.csv")
ansys_script_path = (ansys_dir+"/Ansys_script.wbjn")

# FORCE CONVERGENCE TOLERANCE
A0 = getValue('For calculation of the force convergene tolerance, input area (excluding symmetries, in m^2).')
P_tol = A0 * 0.5e6

# ADMIN CREDENTIALS FOR ACCESSING ADMIN COMMANDLINE
uname = str(input('Input admin windows username'))
pword = getpass.getpass("Enter your password: ")

# ITERATIVE ANALYSIS
for i in index:
	# "The i Loop"
	# The i loop runs for each row in the dataframe.
	# The i loop records results in df_output (final results).
	log.toconsole('\n************************\n'+str(datetime.now())+' i= ' + str(i) + ' of ' + str(index[-1]))

	# Check initial stress guesses don't decrease (not allowed) and correct
	for a in range(len(df_output['True Stress [Pa]'])):
		if a == 0:
			pass
		else:
			if df_output.at[a, 'True Stress [Pa]'] < df_output.at[int(a-1), 'True Stress [Pa]']:
				df_output.at[a, 'True Stress [Pa]'] = df_output.at[int(a-1), 'True Stress [Pa]']
				log.diagnostic('Amended initial stress value for row ' + str(a) + ' because it was lower than the previous point.')
			else:
				pass

	# Set starting parameters for row i
	target_strain = round(df_output.at[i, 'Exp Tot Strain [-]'], 6)
	log.diagnostic('Strain target is ' + str(target_strain))
	P_FEA = 0.1 # Dummy value to enter the next while loop.
	P_EXP = df_output.at[i, 'Exp Force [N]']

	# Prep for j loop
	j_criteria = False
	j = 0
	df_i = pd.DataFrame(data=None,columns=['i','j','iteration','try stress','FEA load','FEA strain','FEA disp','dE %', 'dP'])
	while j_criteria == False:
		# "The j Loop"
		# The j loop tries stress values, checks j criteria, and revises stress value if required.
		# The j criteria checks if the force convergence (FEA vs EXP) has been met.
		# The j loop records results in dfi(i) for diagnostic purposes.
		j += 1
		log.toconsole('\n***************\n'+str(datetime.now())+' j= ' + str(j))

		# Set stress value to try
		if i == 1 and j == 1:
			try_stress = df_output.at[i, 'True Stress [Pa]'] # Use the initial stress guess
			matl_row = {'temp':22, 'strain':df_output.at[i, 'Exp Plastic Strain [-]'] , 'stress': try_stress}
			df_matl = df_matl.append(matl_row, ignore_index=True)
			extrap_strain = df_output.at[i, 'Exp Plastic Strain [-]'] * 1.5
			extrap_stress = extrapolate(df_matl.at[i-1, 'strain'],df_matl.at[i, 'strain'],df_matl.at[i-1, 'stress'],df_matl.at[i, 'stress'],extrap_strain)
			matl_extrap_row = {'temp':22, 'strain':extrap_strain , 'stress':extrap_stress}
			df_matl = df_matl.append(matl_extrap_row, ignore_index=True)
			log.toconsole(str(df_matl))
			df_matl.to_csv(plasticfile, index=False, header=True)
		elif i != 1 and j == 1:
			try_stress = df_output.at[i, 'True Stress [Pa]'] # Use the initial stress guess
			df_matl = df_matl.drop(df_matl.tail(1).index)
			matl_row = {'temp':22, 'strain':df_output.at[i, 'Exp Plastic Strain [-]'] , 'stress': try_stress}
			df_matl = df_matl.append(matl_row, ignore_index=True)
			extrap_strain = df_output.at[i, 'Exp Plastic Strain [-]'] * 1.5
			extrap_stress = extrapolate(df_matl.at[i-1, 'strain'],df_matl.at[i, 'strain'],df_matl.at[i-1, 'stress'],df_matl.at[i, 'stress'],extrap_strain)
			matl_extrap_row = {'temp':22, 'strain':extrap_strain , 'stress':extrap_stress}
			df_matl = df_matl.append(matl_extrap_row, ignore_index=True)
			log.toconsole(str(df_matl))
			df_matl.to_csv(plasticfile, index=False, header=True)
		else:
			pass

		log.toconsole('Try stress @ ' + str(round(try_stress/1e6,3)) + ' MPa')

		# Prep for k loop
		k_criteria = False
		k = 0
		df_j = pd.DataFrame(data=None, columns =['i', 'j', 'k', 'iteration', 'try stress', 'FEA load', 'FEA disp', 'FEA strain', 'dE %'])
		while k_criteria == False:
			# "The k Loop"
			# The k loop provides a displacement value as input to FEM, and receives the FEA load and strain (in ROI) as output.
			# The displacement value is varied until the FEA strain is within the target strain criteria (k criteria).
			# The k loop records results in dfi(i)_j(j) for diagnostic purposes.
			k += 1
			log.toconsole('\n*********\n'+str(datetime.now())+' k= ' + str(k))

			# Set displacement to try
			if (i==1) and (j==1) and (k==1):
				disp = df_output.at[i, 'Est Displacement [m]']
			else:
				# Use the last calculated displacement value
				pass
			log.toconsole('Try displacement at ' + str(disp) + '[m]')

			# Run ansys and read data
			create_ansys_script(disp, log, elasticfile, plasticfile, exportfile, ansys_script_path)
			log.diagnostic('Ansys script created successfully.')
			log.toconsole(str(datetime.now())+' Running Ansys... 5s delay to start...')
			time.sleep(5) # Delay to allow ghost processes to end
			t = run_ansys(log, ansys_dir, ansys_script_path, skeleton_project, uname, pword, proj_direc, proj_file, timeout)
			timeout = t*3
			iterations += 1
			FEA_strain, P_FEA, FEA_disp, max_strain = read_ansys(log, exportfile)

			# Export data for diagnostics
			temp_data_j = {'i':[i], 'j':[j], 'k':[k], 'iteration':[iterations], 'try stress':[try_stress], 'FEA load':[P_FEA], 'FEA disp':[FEA_disp], 'FEA strain':[FEA_strain], 'dE %':[((FEA_strain - target_strain)/target_strain)*100]}
			temp_df_j = pd.DataFrame(temp_data_j)
			df_j = df_j.append(temp_df_j, ignore_index = True)
			df_j_path = diagnostic_dir + '/dfi' + str(i) + '_j' + str(j) + '.csv'
			df_j.to_csv(df_j_path, index=True, header=True)

			# Check k criteria, amend displacement if required
			if (target_strain * 0.9975) < FEA_strain < (target_strain * 1.0025):
				k_criteria = True
				log.toconsole('FEM displacement accepted, strain target and tolerance met.')
			elif k >19:
				k_criteria = True
				log.toconsole('There was an issue achieving the strain tolerance. Review data after run for point i=' + str(i) + ' j=' + str(j))
			else:
				# k_criteria = False (doesn't change)
				# Make a more intelligent guess of the displacement
				j_strain_list = df_j['FEA strain'].tolist()
				if len(j_strain_list) == 1:
					disp = disp * 1.2
				else:
					strain_status = point_check(target_strain, j_strain_list, log)
					log.diagnostic('strain_status = ' + str(strain_status))
					if strain_status == 'greater': #All FEA strain values are greater than target strain value.
						status_df = df_j.iloc[(df_j['FEA strain'] - target_strain).abs().argsort()[:2]]
						status_df = status_df.sort_values(by=['FEA strain'], inplace=False)
						status_df = status_df.reset_index(drop=True, inplace=False)
						x1 = status_df.at[0, 'FEA strain']
						x2 = status_df.at[1, 'FEA strain']
						y1 = status_df.at[0, 'FEA disp']
						y2 = status_df.at[1, 'FEA disp']
						x = target_strain
						disp = round(extrapolate(x1,x2,y1,y2,x), 10)
						log.diagnostic('Extrapolated for displacement value.')
					elif strain_status == 'lesser': #All FEA strain values are lower than target strain value.
						status_df = df_j.iloc[(df_j['FEA strain'] - target_strain).abs().argsort()[:2]]
						status_df = status_df.sort_values(by=['FEA strain'], inplace=False)
						status_df = status_df.reset_index(drop=True, inplace=False)
						x1 = status_df.at[0, 'FEA strain']
						x2 = status_df.at[1, 'FEA strain']
						y1 = status_df.at[0, 'FEA disp']
						y2 = status_df.at[1, 'FEA disp']
						x = target_strain
						disp = round(extrapolate(x1,x2,y1,y2,x), 10)
						log.diagnostic('Extrapolated for displacement value.')
					elif strain_status == 'between': #Target strain value falls between FEA strain values.
						status_drop_lo = df_j[df_j['FEA strain'] < target_strain].index
						status_df_hi = df_j.drop(status_drop_lo)
						ind2 = status_df_hi['FEA strain'].idxmin()
						status_drop_hi = df_j[df_j['FEA strain'] > target_strain].index
						status_df_lo = df_j.drop(status_drop_hi)
						ind1 = status_df_lo['FEA strain'].idxmax()
						x1 = df_j.at[ind1, 'FEA strain']
						x2 = df_j.at[ind2, 'FEA strain']
						y1 = df_j.at[ind1, 'FEA disp']
						y2 = df_j.at[ind2, 'FEA disp']
						x = target_strain
						disp = round(interpolate(x1,x2,y1,y2,x), 10)
						log.diagnostic('Interpolated for displacement value.')
					else:
						log.toconsole('The check of FEA strain vs EXP strain failed. Check last recorded data.')
			# End k loop
		# Export data for diagnostics
		temp_data_i = {'i':[i], 'j':[j],'iteration':[iterations], 'try stress':[try_stress], 'FEA load':[P_FEA], 'FEA strain':[FEA_strain],
			'FEA disp':[FEA_disp], 'dE %':[((FEA_strain - target_strain)/target_strain)*100],
			'dP':[P_FEA-P_EXP]}
		temp_df_i = pd.DataFrame(temp_data_i)
		df_i = df_i.append(temp_df_i, ignore_index = True)
		df_i_path = diagnostic_dir + '/dfi' + str(i) + '.csv'
		df_i.to_csv(df_i_path, index=True, header=True)

		# Check j criteria
		if abs(P_FEA - P_EXP) < P_tol: # Force convergence criteria
			j_criteria = True
			df_output.at[i, 'True Stress [Pa]'] = try_stress
			log.toconsole('Stress value accepted, force tolerance met.')
		else:
			#j_criteria == False (doesn't change)
			# Make a more intelligent guess of the stress
			P_FEA_list = df_i['FEA load'].tolist()
			last_stress = df_i.at[j-1, 'try stress']
			if len (P_FEA_list) == 1:
				try_stress = round((P_EXP/P_FEA_list[0])*last_stress, 3)
			else:
				P_status = point_check(P_EXP, P_FEA_list, log)
				log.diagnostic('P_status = ' + str(P_status))
				if P_status == 'greater': #All P_FEA values are greater than P_EXP
					status_df = df_i.iloc[(df_i['FEA load'] - P_EXP).abs().argsort()[:2]]
					status_df = status_df.sort_values(by=['FEA load'], inplace=False)
					status_df = status_df.reset_index(drop=True, inplace=False)
					x1 = status_df.at[0, 'FEA load']
					x2 = status_df.at[1, 'FEA load']
					y1 = status_df.at[0, 'try stress']
					y2 = status_df.at[1, 'try stress']
					x = P_EXP
					try_stress = round(extrapolate(x1,x2,y1,y2,x), 3)
					log.diagnostic('Extrapolated for displacement value.')
				elif P_status == 'lesser': #All P_FEA values are lesser than P_EXP
					status_df = df_i.iloc[(df_i['FEA load'] - P_EXP).abs().argsort()[:2]]
					status_df = status_df.sort_values(by=['FEA load'], inplace=False)
					status_df = status_df.reset_index(drop=True, inplace=False)
					x1 = status_df.at[0, 'FEA load']
					x2 = status_df.at[1, 'FEA load']
					y1 = status_df.at[0, 'try stress']
					y2 = status_df.at[1, 'try stress']
					x = P_EXP
					try_stress = round(extrapolate(x1,x2,y1,y2,x), 3)
					log.diagnostic('Extrapolated for displacement value.')
				elif P_status == 'between': #P_EXP falls between two P_FEA values
					status_drop_lo = df_i[df_i['FEA load'] < P_EXP].index
					status_df_hi = df_i.drop(status_drop_lo)
					ind2 = status_df_hi['FEA load'].idxmin()
					status_drop_hi = df_i[df_i['FEA load'] > P_EXP].index
					status_df_lo = df_i.drop(status_drop_hi)
					ind1 = status_df_lo['FEA load'].idxmax()
					x1 = df_i.at[ind1, 'FEA load']
					x2 = df_i.at[ind2, 'FEA load']
					y1 = df_i.at[ind1, 'try stress']
					y2 = df_i.at[ind2, 'try stress']
					x = P_EXP
					try_stress = round(interpolate(x1,x2,y1,y2,x), 3)
					log.diagnostic('Interpolated for displacement value.')
				else:
					log.toconsole('The check of P_FEA vs P_EXP failed. Check last recorded data.')
			# Check if the revised stress value went lower than stress(i-1)
			if try_stress < df_output.at[int(i-1), 'True Stress [Pa]']:
				try_stress = df_output.at[int(i-1), 'True Stress [Pa]']
				log.diagnostic('Reject changing of stress value to lower than the previous point.')

			# Change the test stress value in the Ansys material data CSV
			df_matl.drop(df_matl.tail(2).index, inplace=True)
			matl_row = {'temp':22, 'strain':df_output.at[i, 'Exp Plastic Strain [-]'] , 'stress': try_stress}
			df_matl = df_matl.append(matl_row, ignore_index=True)
			extrap_strain = df_output.at[i, 'Exp Plastic Strain [-]'] * 1.5
			extrap_stress = extrapolate(df_matl.at[i-1, 'strain'],df_matl.at[i, 'strain'],df_matl.at[i-1, 'stress'],df_matl.at[i, 'stress'],extrap_strain)
			matl_extrap_row = {'temp':22, 'strain':extrap_strain , 'stress':extrap_stress}
			df_matl = df_matl.append(matl_extrap_row, ignore_index=True)
			log.toconsole(str(df_matl))
			df_matl.to_csv(plasticfile, index=False, header=True)

			# Check if this stress value has been tested before
			stress_list = df_i['try stress'].tolist()
			if try_stress in  stress_list:
				# This is an exit route from j loop if the stress tried to be revised lower than the previous point,
				# but the load criteria still hasn't been met, and this lowest allowable stress has been tested already.
				log.toconsole('Already tried that stress value, and it is the lowest allowable. Load criterion not met, but moving to next point. Review error manually later.')
				df_output.at[i, 'True Stress [Pa]'] = try_stress
				j_criteria = True
		# End j loop
	df_output.at[i, 'FEA Strain [-]'] = FEA_strain
	df_output.at[i, 'FEA Force [N]'] = P_FEA
	df_output.at[i, 'FEA Displacement [m]'] = FEA_disp
	# End i loop
log.toconsole('************************\nIterative procedure complete.')
log.toconsole('Total iterations by Python: ' + str(iterations))

# CLEAN UP VARIABLES AND FILES
pword='' # Clear the password at earliest opportunity, for security (password not retained).
rmtree(ansys_dir + '/copied-project_files')
os.remove(ansys_dir + '/copied-project.wbpj')

# CALCULATE FORCE AND STRAIN CONVERGENCE ERRORS
exp_forces = df_output['Exp Force [N]'].tolist()
FEA_forces = df_output['FEA Force [N]'].tolist()
force_error = [x - y for x,y in zip(FEA_forces, exp_forces)]
df_output['Force Error [N]'] = force_error

exp_strains = df_output['Exp Tot Strain [-]'].tolist()
FEA_strains = df_output['FEA Strain [-]'].tolist()
strain_error = [((x - y)/y)*100 for x,y in zip(FEA_strains, exp_strains)]
df_output['Strain Error %'] = strain_error

# EXTRAPOLATE RESULTS TO MAXIMUM STRAIN IN THE MODEL
df_output['dS'] = df_output['True Stress [Pa]'].diff(1)
df_output['de'] = df_output['Exp Tot Strain [-]'].diff(1)
grad_1 = df_output.at[df_output.index.values[-1], 'dS']/df_output.at[df_output.index.values[-1], 'de']
grad_2 = df_output.at[df_output.index.values[-2], 'dS']/df_output.at[df_output.index.values[-2], 'de']
grad_3 = df_output.at[df_output.index.values[-2], 'dS']/df_output.at[df_output.index.values[-2], 'de']
grad_av = (grad_1 + grad_2 + grad_3)/3
max_stress = grad_av*df_output.at[df_output.index.values[-1], 'de'] + df_output.at[df_output.index.values[-1], 'True Stress [Pa]']
df_output = df_output.drop(axis=1, labels=['dS', 'de'])
max_plas_strain = max_strain - df_output.at[0, 'Exp Tot Strain [-]']
extrap_row = {'Exp Tot Strain [-]':max_strain, 'Exp Plastic Strain [-]':max_plas_strain, 'Exp Force [N]':np.NaN, 'Starting Stress [Pa]':np.NaN, 'Est Displacement [m]':np.NaN,
	'True Stress [Pa]':max_stress, 'FEA Strain [-]':max_strain, 'FEA Force [N]':np.NaN, 'FEA Displacement [m]':np.NaN, 'Force Error [N]':np.NaN, 'Strain Error %':np.NaN}
df_output = df_output.append(extrap_row, ignore_index=True)
log.diagnostic('Extrapolated final TSS dataset to maximum strain in the FEM.')

# ADD ZERO ROW TO FINAL DATASET
zero_row = {'Exp Tot Strain [-]':0, 'Exp Plastic Strain [-]':np.NaN, 'Exp Force [N]':0, 'Starting Stress [Pa]':0, 'Est Displacement [m]':0,
	'True Stress [Pa]':0, 'FEA Strain [-]':0, 'FEA Force [N]':0, 'FEA Displacement [m]':0, 'Force Error [N]':np.NaN, 'Strain Error %':np.NaN}
df_output = df_output.append(zero_row, ignore_index=True)
df_output = df_output.sort_values(by=['Exp Tot Strain [-]'], inplace=False)
df_output = df_output.reset_index(drop=True, inplace=False)
log.diagnostic('Created zero row in final TSS dataset.')

# OUTPUT RESULTS TO CSV
df_output_csv_path=(results_dir+"/results.csv")
df_output.to_csv(df_output_csv_path, index=True, header=True)
log.diagnostic('Results CSV file saved as: ' + str(df_output_csv_path))

# PLOT TRUE STRESS STRAIN CURVE
plot1 = plt.figure()
ax = plot1.add_subplot(1,1,1)
ax.plot(df_output['Exp Tot Strain [-]'], df_output['True Stress [Pa]'])
ax.set_xlabel('Equivalent True Strain [-]')
ax.set_ylabel('Equivalent True Stress [Pa]')
plot1_path = (results_dir+'/1_TrueStressStrain.png')
plot1.savefig(plot1_path)
log.diagnostic('Plot saved to: '+str(plot1_path))

# PLOT TRUE STRESS STRAIN CURVE WITH STARTING CURVE
plot2 = plt.figure()
ax = plot2.add_subplot(1,1,1)
ax.plot(df_output['Exp Tot Strain [-]'], df_output['Starting Stress [Pa]'], label='Starting curve')
ax.plot(df_output['Exp Tot Strain [-]'], df_output['True Stress [Pa]'], label='IFD curve')
ax.legend()
ax.set_xlabel('Equivalent True Strain [-]')
ax.set_ylabel('Equivalent True Stress [Pa]')
plot2_path = (results_dir+'/2_TrueStressStrain.png')
plot2.savefig(plot2_path)
log.diagnostic('Plot saved to: '+str(plot2_path))

# TERMINATE SCRIPT
log.toconsole('IFD script finished successfully at '+str(datetime.now()))