# IMPORTS
import os
import subprocess
from shutil import copy2, copytree, rmtree
import pandas as pd
from CommonFunctions import *
import time

def run_ansys(log, ansys_dir, ansys_script_path, skeleton_project, uname, pword, proj_direc, proj_file, timeout):
	# Runs Ansys Workbench from Windows commandline.
	log.diagnostic('Attempting to run Ansys from commandline.')
	command_ansys = [r'C:\PSTools\psexec.exe', '-u', uname, '-p', pword, # Ensure the PS Exec location is correct when using on a new computer.
			r'C:\Program Files\ANSYS Inc\ANSYS Student\v211\Framework\bin\Win64\runwb2.bat', #Ensure the Workbench executable location is correct when using a new computer.
			'-F',
			skeleton_project,
			'-B',
			'-R',
			ansys_script_path]
	if timeout == 'default':
		timeout = 600
	tries = 0
	while tries < 4:
		tries += 1
		try:
			process_ansys = subprocess.Popen(command_ansys, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
			log.toconsole('Ansys command has been sent.')
			t = 0
			while process_ansys.poll() != 0:
				if t > timeout:
					raise RuntimeError('Timeout')
					break
				time.sleep(1)
				t+=1
			log.toconsole('Subprocess (Ansys) successful, t = ' + str(t))
			successful = True
		except RuntimeError:
			log.toconsole('Subprocess taking too long, initiating timeout procedure.')
			kill = subprocess.Popen("TASKKILL /F /PID {pid} /T".format(pid=process_ansys.pid))
			t2 = 0
			log.diagnostic('Waiting for subprocess (Ansys) to be killed.')
			while kill.poll() != 0:
				time.sleep(1)
				t2 += 1
				if t2 > 30:
					log.diagnostic('Waited 30 seconds for subprocess (Ansys) to be killed without response. Continuing anyway.')
					break
			log.toconsole('Subprocess (Ansys) killed due to timeout, t = ' + str(t))
			if tries == 4:
				raise ValueError('')
			rmtree(ansys_dir + '/copied-project_files')
			os.remove(ansys_dir + '/copied-project.wbpj')
			log.diagnostic('Locked Ansys files deleted.')
			copy_project(proj_direc, proj_file, ansys_dir, log)
			log.diagnostic('New ansys project copied.')
			successful = False
		except ValueError:
			log.toconsole('The command sent to Ansys failed 3 times. This is most likely an issue with the Workbench file. Review the last used workbench file at: ' + str(ansys_dir) + '/copied-project.wbpj')
			exit()
		if successful == True:
			log.toconsole('Ansys was run via commandline successfully.')
			break
	return t

def read_ansys(log, exportfile):
	# Reads the results from Ansys (CSV file)
	export_df = pd.read_csv(exportfile, delimiter = ',', names=['displacement','ifd force', 'ansys max strain', 'ansys strain ROI'],
		usecols=[1,2,3,4], skiprows=[0,1,2,3,4,5,6]) # Amend this dataframe constructor to match your CSV file
	strain_roi = export_df.at[0,'ansys strain ROI']
	force = 4*export_df.at[0,'ifd force'] # Set the multiplier correctly depending on the number of symmetries in the Ansys model
	disp = export_df.at[0,'displacement']	
	max_strain = export_df.at[0,'ansys max strain']
	log.toconsole('Ansys results were read successfully.')
	return strain_roi, force, disp, max_strain

def create_ansys_script(disp, log, elasticfile, plasticfile, exportfile, ansys_script_path):
	#Create script to drive Ansys project
	#This will be specific to your Workbench skeleton project due to changes inside Workbench (e.g. parameter names)
	#Creating a new script is easy - just record a journal in Workbench, and go through these steps manually
	#Then take the recorded journal file, and paste the lines into the script creator below. Note where variables need to be referenced.
	#Keep file names the same to avoid problems elsewhere in this script.
	script = []


	script.append('﻿# encoding: utf-8')
	script.append('# 2021 R1')
	script.append('SetScriptVersion(Version="21.1.216")')
	script.append('system1 = GetSystem(Name="SYS 6")')
	script.append('engineeringData1 = system1.GetContainer(ComponentName="Engineering Data")')
	script.append('material1 = engineeringData1.GetMaterial(Name="P91-Plas")')
	script.append('matlProp1 = material1.GetProperty(Name="Elasticity")')
	script.append('materialPropertyData1 = matlProp1.GetPropertyData(')
	script.append('    Name="Elasticity",')
	script.append("""    Qualifiers={"Definition": "", "Behavior": "Isotropic", "Derive from": "Young's Modulus and Poisson's Ratio"})""")
	script.append('dataProvider1 = materialPropertyData1.CreateDataProvider(Format="Delimited Text")')
	script.append('dataProvider1.FileName = r"'+elasticfile+'"') ##Pick up elasticity material file
	script.append('dataProvider1.ReadLine = 2')
	script.append('dataProvider1.Columns = [1, 2, 3]')
	script.append('dataProvider1.Delimiter = ","')
	script.append("""dataProvider1.VariableNames = ["Young's Modulus", "Temperature", "Poisson's Ratio"]""")
	script.append('dataProvider1.VariableUnits = ["Pa", "C", ""]')
	script.append('dataProvider1.Import()')
	script.append('matlProp2 = material1.GetProperty(Name="Isotropic Hardening")')
	script.append('materialPropertyData2 = matlProp2.GetPropertyData(')
	script.append('    Name="Isotropic Hardening",')
	script.append('    Qualifiers={"Definition": "Multilinear", "Behavior": ""})')
	script.append('dataProvider2 = materialPropertyData2.CreateDataProvider(Format="Delimited Text")')
	script.append('dataProvider2.FileName = r"'+plasticfile+'"') ##Pick up plasticity material file
	script.append('dataProvider2.ReadLine = 2')
	script.append('dataProvider2.Columns = [1, 2, 3]')
	script.append('dataProvider2.Delimiter = ","')
	script.append('dataProvider2.VariableNames = ["Temperature", "Plastic Strain", "Stress"]')
	script.append('dataProvider2.VariableUnits = ["C", "m m^-1", "Pa"]')
	script.append('dataProvider2.Import()')
	script.append('designPoint1 = Parameters.GetDesignPoint(Name="32")')
	script.append('parameter1 = Parameters.GetParameter(Name="P103")')
	script.append('designPoint1.SetParameterExpression(')
	script.append('    Parameter=parameter1,')
	script.append('    Expression="'+str(disp)+' [m]")')
	script.append('backgroundSession1 = UpdateAllDesignPoints(DesignPoints=[designPoint1])')
	script.append('Parameters.ExportAllDesignPointsData(FilePath="'+exportfile+'")') #Export results of interest to CSV

	with open(ansys_script_path, 'w', encoding="utf-8") as file:
		for i in script:
			file.write(i + '\n')
	log.diagnostic('Ansys internal script created successfully.')