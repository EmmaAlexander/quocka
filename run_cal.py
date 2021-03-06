#!/usr/bin/env python

import argparse, ConfigParser
import glob, os
from subprocess import call
from numpy import unique

def logprint(s2p,lf):
	print >>lf, s2p
	print s2p

def main(args,cfg):
	# Initiate log file with options used
	logf = open(args.log_file,'w',1) # line buffered
	logprint('Input settings:',logf)
	logprint(args,logf)
	logprint(cfg.items('input'),logf)
	logprint(cfg.items('output'),logf)
	logprint(cfg.items('observation'),logf)
	logprint('',logf)

	gwcp = cfg.get('input','dir')+'/'+cfg.get('input','date')+'*'
	atfiles = sorted(glob.glob(gwcp))
	if_use = cfg.getint('input','if_use')
	outdir = cfg.get('output','dir')
	rawclobber = cfg.getboolean('output','rawclobber')
	outclobber = cfg.getboolean('output','clobber')
	prical = cfg.get('observation','primary')
	seccal = cfg.get('observation','secondary')
	polcal = cfg.get('observation','polcal')

	if not os.path.exists(outdir):
		logprint('Creating directory %s'%outdir,logf)
		os.makedirs(outdir)
	for line in open(args.setup_file):
		if line[0] == '#':
			continue
		sline = line.split()
		for a in atfiles:
			if sline[0] in a:
				logprint('Ignoring setup file %s'%sline[0],logf)
				atfiles.remove(a)
	uvlist = ','.join(atfiles)

	if not os.path.exists(outdir+'/dat.uv') or rawclobber:
		logprint('Running ATLOD...',logf)
		if if_use > 0:
			call(['atlod', 'in=%s'%uvlist, 'out=%s/dat.uv'%outdir, 'ifsel=%s'%if_use, 'options=birdie,noauto,xycorr,rfiflag'],stdout=logf,stderr=logf)
		else:
			call(['atlod', 'in=%s'%uvlist, 'out=%s/dat.uv'%outdir, 'options=birdie,noauto,xycorr,rfiflag'],stdout=logf,stderr=logf)
	else:
		logprint('Skipping atlod step',logf)
	os.chdir(outdir)
	logprint('Running UVSPLIT...',logf)
	if outclobber:
		logprint('Output files will be clobbered if necessary',logf)
		call(['uvsplit','vis=dat.uv','options=mosaic,clobber'],stdout=logf,stderr=logf)
	else:
		call(['uvsplit','vis=dat.uv','options=mosaic'],stdout=logf,stderr=logf)
	slist = sorted(glob.glob('[012]*'))
	logprint('Working on %d sources'%len(slist),logf)
	bandfreq = unique([x[-4:] for x in slist])
	logprint('Frequency bands to process: %s'%(','.join(bandfreq)),logf)

	for frqb in bandfreq:
		logprint('\n\n##########\nWorking on frequency: %s\n##########\n\n'%(frqb),logf)
		pricalname = '__NOT_FOUND__'
		seccalname = '__NOT_FOUND__'
		polcalnames = []
		targetnames = []
		for i,source in enumerate(slist):
			frqid = source[-4:]
			if frqid not in frqb:
				continue
			if prical in source: 
				pricalname = source
			elif seccal in source:
				seccalname = source
			elif any([pc in source for pc in polcal.split(',')]):
				polcalnames.append(source)
			else:
				targetnames.append(source)
			logprint('\nFLAGGING: %d / %d = %s'%(i+1,len(slist),source),logf)
			####
			# This part may be largely obsolete with options=rfiflag in ATLOD
			for line in open('../badchans_%s.txt'%frqid):
				sline=line.split()
				lc,uc=sline[0].split('-')
				dc = int(uc)-int(lc)+1
				call(['uvflag','vis=%s'%source,'line=chan,%d,%s'%(dc,lc),'flagval=flag'],stdout=logf,stderr=logf)
			####
			#call(['pgflag','vis=%s'%source,'stokes=xx,yy,yx,xy','flagpar=20,10,10,3,5,3,20','command=<be','options=nodisp'])
			call(['uvflag','vis=%s'%source,'select=amplitude(2),polarization(xy,yx)','flagval=flag'],stdout=logf,stderr=logf)
			call(['uvpflag','vis=%s'%source,'polt=xy,yx','pols=xx,xy,yx,yy','options=or'],stdout=logf,stderr=logf)
			call(['pgflag','vis=%s'%source,'stokes=v','flagpar=7,4,12,3,5,3,20','command=<be','options=nodisp'],stdout=logf,stderr=logf)
		if pricalname == '__NOT_FOUND__':
			logprint('Error: primary cal (%s) not found'%prical,logf)
			logf.close()
			exit(1)
		if seccalname == '__NOT_FOUND__':
			logprint('Error: secondary cal (%s) not found'%seccal,logf)
			logf.close()
			exit(1)
		logprint('Identified primary cal: %s'%pricalname,logf)
		logprint('Identified secondary cal: %s'%seccalname,logf)
		logprint('Identified %d polarization calibrators'%len(polcalnames),logf)
		logprint('Identified %d targets to calibrate'%len(targetnames),logf)
		logprint('Calibration of primary cal (%s) proceeding ...'%prical,logf)
		call(['mfcal','vis=%s'%pricalname,'interval=10000','select=elevation(40,90)'],stdout=logf,stderr=logf)
		call(['pgflag','vis=%s'%pricalname,'stokes=v','flagpar=7,4,12,3,5,3,20','command=<be','options=nodisp'],stdout=logf,stderr=logf)
		call(['mfcal','vis=%s'%pricalname,'interval=10000','select=elevation(40,90)'],stdout=logf,stderr=logf)
		call([ 'gpcal', 'vis=%s'%pricalname, 'interval=0.1', 'nfbin=16', 'options=xyvary','select=elevation(40,90)'],stdout=logf,stderr=logf)
		call(['pgflag','vis=%s'%pricalname,'stokes=v','flagpar=7,4,12,3,5,3,20','command=<be','options=nodisp'],stdout=logf,stderr=logf)
		call([ 'gpcal', 'vis=%s'%pricalname, 'interval=0.1', 'nfbin=16', 'options=xyvary','select=elevation(40,90)'],stdout=logf,stderr=logf)
		logprint('Transferring to secondary...',logf)
		#### MISSING HERE: GPBOOT
		call(['gpcopy','vis=%s'%pricalname,'out=%s'%seccalname],stdout=logf,stderr=logf)
		call(['puthd','in=%s/interval'%seccalname,'value=100000'],stdout=logf,stderr=logf)
		call(['pgflag','vis=%s'%seccalname,'stokes=v','flagpar=7,4,12,3,5,3,20','command=<be','options=nodisp'],stdout=logf,stderr=logf)
		call(['gpcal','in=%s'%seccalname,'interval=0.1','nfbin=16','options=xyvary,qusolve'],stdout=logf,stderr=logf)
		call(['pgflag','vis=%s'%seccalname,'stokes=v','flagpar=7,4,12,3,5,3,20','command=<be','options=nodisp'],stdout=logf,stderr=logf)
		call(['gpcal','in=%s'%seccalname,'interval=0.1','nfbin=16','options=xyvary,qusolve'],stdout=logf,stderr=logf)
		for t in targetnames:
			logprint('Working on source %s'%t,logf)
			slogname = '%s.log.txt'%t
			slogf = open(slogname,'w',1)
			call(['gpcopy','vis=%s'%seccalname,'out=%s'%t],stdout=logf,stderr=logf)
			call(['pgflag','vis=%s'%t,'stokes=v','flagpar=7,4,12,3,5,3,20','command=<be','options=nodisp'],stdout=logf,stderr=logf)
			logprint('Writing source flag and pol info to %s'%slogname,logf)
			call(['uvspec','vis=%s'%t,'axis=rm','options=nobase,avall','nxy=1,2','interval=100000','xrange=-1500,1500','device=junk.eps/vcps'],stdout=slogf,stderr=slogf)
			call(['epstool','--copy','--bbox','junk.eps','%s.eps'%t],stdout=logf,stderr=logf)
			os.remove('junk.eps')
			call(['uvfstats','vis=%s'%t],stdout=slogf,stderr=slogf)
			call(['uvfstats','vis=%s'%t,'mode=channel'],stdout=slogf,stderr=slogf)
			slogf.close()
	
	logprint('DONE!',logf)
	logf.close()

ap = argparse.ArgumentParser()
ap.add_argument('config_file',help='Input configuration file')
ap.add_argument('-s','--setup_file',help='Name of text file with setup correlator file names included so that they can be ignored during the processing [default setup.txt]',default='setup.txt')
ap.add_argument('-l','--log_file',help='Name of output log file [default log.txt]',default='log.txt')
args = ap.parse_args()

cfg = ConfigParser.RawConfigParser()
cfg.read(args.config_file)

main(args,cfg)

