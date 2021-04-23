# IMPORTS
from shutil import copy2, copytree, rmtree
import os

# CLASSES
class LoggingFile:
	# Creates a class of object as a logging file. Simpler than the full logging library.
	def __init__(self, filepath):
		self.file = filepath
		with open(self.file, 'w') as text:
			text.write('Logfile created.')
	def diagnostic(self, phrase):
		#Records line in the logfile only.
		with open (self.file, 'a+') as text:
			text.write('\n'+phrase)
	def toconsole(self, phrase):
		#Records line in the logfile and also prints it to console.
		with open (self.file, 'a+') as text:
			text.write('\n'+phrase)
		print(phrase)

# FUNCTIONS
def copy_project(proj_direc, proj_file, ansys_dir, log):
	# Copies the workbench project and associated files. This is to facilitate the timeout functionality, avoiding workbench project locking
	old_proj = proj_direc + '/' + proj_file + '.wbpj'
	new_proj = ansys_dir + '/copied-project.wbpj'
	copy2(old_proj, new_proj)
	log.diagnostic('Workbench project copied.')
	old_files = proj_direc + '/' + proj_file + '_files'
	new_files = ansys_dir + '/copied-project_files'
	copytree(old_files, new_files)
	log.diagnostic('Workbench project files copied.')
	skeleton_project = new_proj
	return skeleton_project

def createFolder(path, folder, log):
	# Creates new folders in windows. Expects format as per dirPath.
	newDir = str(path + '/' + folder)
	log.diagnostic('Trying to create folder: ' + str(newDir))
	check = os.path.isdir(newDir)
	if check == True:
		log.diagnostic('Already existed: ' + str(newDir))
		return newDir
	else:
		try:
			os.mkdir(newDir)
			log.diagnostic('Successfully created: ' + str(newDir))
			return newDir
		except OSError:
			log.diagnostic('Failed to create: ' + str(newDir))
			exit()
		else:
			log.diagnostic('An unkown error occured while trying to create the directory: '  + str(newDir))

def dirPath(question):
	# Function to get a user input directory, with correctness check.
	correct = 'n'
	while correct != 'y':
		direc = str(input(question))
		print('Directory to be used is: '+str(direc))
		check = 'n'
		while check != 'y':
			answer=str(input('Is this correct? [y/n]')).lower()
			if answer == 'y':
				correct = 'y'
				check = 'y'
			elif answer == 'n':
				correct = 'n'
				check = 'y'
			else:
				print('Please use [y] or [n] to indicate')
				continue
	direcClean = direc.replace('\\','/')
	return direcClean

def extrapolate(x1,x2,y1,y2,x):
	# Function for linear extrapolation.
	y = y1 + (((y2-y1)*(x-x1))/(x2-x1))
	return y

def filePath(dirQuestion, fileQuestion):
	# Function to get a full filepath from user, in a convenient format for copy and pasting from Windows.
	# With correctness check,
	correct = 'n'
	while correct != 'y':
		direc = str(input(dirQuestion))
		file = str(input(fileQuestion))
		path = str(direc + '/' + file)
		print('File to be used is: '+str(path))
		check = 'n'
		while check != 'y':
			answer=str(input('Is this correct? [y/n]')).lower()
			if answer == 'y':
				correct = 'y'
				check = 'y'
			elif answer == 'n':
				correct = 'n'
				check = 'y'
			else:
				print('Please use [y] or [n] to indicate')
				continue
	pathClean = path.replace('\\','/')
	return pathClean

def getString(question):
	# Function to get a string form the user, with correctness check.
	correct = 'n'
	while correct != 'y':
		variable = str(input(question))
		print('Value is: '+str(variable))
		check = 'n'
		while check != 'y':
			answer=str(input('Is this correct? [y/n]')).lower()
			if answer == 'y':
				correct = 'y'
				check = 'y'
			elif answer == 'n':
				correct = 'n'
				check = 'y'
			else:
				print('Please use [y] or [n] to indicate')
				continue
	return variable

def getValue(question):
	# Function to get a float value from user.
	correct = 'n'
	while correct != 'y':
		value= float(input(question))
		print('Value is: '+str(value))
		check = 'n'
		while check != 'y':
			answer=str(input('Is this correct? [y/n]')).lower()
			if answer == 'y':
				correct = 'y'
				check = 'y'
			elif answer == 'n':
				correct = 'n'
				check = 'y'
			else:
				print('Please use [y] or [n] to indicate')
				continue
	return value

def interpolate(x1,x2,y1,y2,x):
	# Function for linear interpolation.
	y = (((x-x1)*(y2-y1))/(x2-x1))+y1
	return y

def point_check(point, lst, log):
	# Checks what data points are available prior to interpolation.
	if all(y > point for y in lst):
		return 'greater'
	elif all(y < point for y in lst):
		return 'lesser'
	elif any(y > point for y in lst) and any(y < point for y in lst):
		return 'between'
	log.diagnostic('Point check was successful.')

def write_elastic(youngs, poisson, elasticfile, log):
	#Write elasticity data file to be read by Ansys
	file_youngs = open(elasticfile, 'w')
	file_youngs.write('youngs,temp,poisson')
	file_youngs.write('\n'+str(youngs)+',22,'+str(poisson))
	file_youngs.close()
	log.diagnostic('Elasticity data file created successfully.')