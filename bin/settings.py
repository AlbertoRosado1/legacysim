import os

survey_dir = os.getenv('LEGACY_SURVEY_DIR')
output_dir = os.path.join(os.getenv('CSCRATCH'),'legacysim','dr9','test')
randoms_fn = '/global/cfs/cdirs/cosmo/data/legacysurvey/dr9/randoms/randoms-1-0.fits'
truth_fn = '/project/projectdirs/desi/users/ajross/MCdata/seed.fits'
injected_fn = os.path.join(output_dir,'injected','injected.fits')
bricklist_fn = 'bricklist.txt'
runlist_fn = 'runlist.txt'

def get_bricknames():
    return [brickname.replace('\n','') for brickname in open(bricklist_fn,'r')]


run = 'north'
#legacypipe_survey_dir = os.getenv('LEGACYPIPE_SURVEY_DIR')
legacypipe_output_dir = os.path.join(os.getenv('LEGACYPIPE_SURVEY_DIR'),run)
