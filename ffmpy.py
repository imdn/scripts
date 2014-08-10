# -*- coding: utf-8 -*-
"""
Created on Sun Aug 10 19:17:03 2014

@author: imad
Wrapper for ffmpeg cli. Simply takes a video file and encodes it to mp4 as per default settings. Parameters can be changed.
"""

import os
import sys, re
import argparse
import subprocess

def get_vargs():
    if args.vcopy:
        v_args = ['-c:v', 'copy']
        return v_args
    
    v_args = ['-c:v', args.vcodec]     
 
    v_opts = ['-crf', args.crf]
    if args.vbitrate:
        v_opts = ['-b:v', args.vbitrate]
     
    v_args.extend(v_opts)
    return v_args

def get_aargs():
    if args.acopy:
        a_args = ['-c:a', 'copy']
        return a_args
        
    if args.acodec is 'aac':
        a_args = ['-c:a', args.acodec, '-strict', 'experimental']     
    else:
        a_args = ['-c:a', args.acodec]
 
    a_opts = ['-q:a', args.aquality]    
    if args.abitrate:
        a_opts = ['-b:a', args.abitrate]
    
    a_args.extend(a_opts)
    return a_args

def samefile(file1, file2):
    return os.stat(file1) == os.stat(file2)
    
def get_output_filename():
    infile = args.input_file
    dir = os.path.dirname(infile)
    basename, ext = os.path.splitext(os.path.basename(infile))
    print dir, basename, ext
    mp4ext = '.mp4'
    
    if args.output:
        outfile=args.output
        basename, ext = os.path.splitext(outfile)
    else:
        outfile = os.path.join(dir,basename) + mp4ext
        
    if os.path.exists(outfile):
        if (args.no_overwrite) or samefile(infile, outfile):
        # If outfile is same as infile, give it a new name        
            TOO_MANY_FILES = True
            print outfile + " already exists. Trying new filename(s)"
            for i in range(1,5):
                outfile = basename + " NEW " + str(i) + mp4ext
                print "Now trying new output filename - "  + outfile
                if os.path.exists(outfile) is False:
                    TOO_MANY_FILES=False                
                    break;
            if TOO_MANY_FILES:
               print "!!! Too many duplicate output files appear to exist. Fix before trying !!!"
               sys.exit(-2);
    
    print "Output file - " + outfile
    return outfile

def construct_cmd():
    main_args = [args.ffmpeg , '-i', args.input_file]

    if args.copy:    
        main_args.extend(['-c', 'copy'])
    else:
        a_args = get_aargs()
        v_args = get_vargs()
        main_args.extend(v_args)            
        main_args.extend(a_args)
        main_args.extend(['-preset', args.preset])
    
    if args.other:
        main_args.append(args.other)

    if not args.no_overwrite:
        main_args.append('-y')

    output = get_output_filename()
    print output
    main_args.append(output)
    
    print main_args
    return main_args
    
parser = argparse.ArgumentParser(description='Convert a file using ffmpeg')
parser.add_argument ('input_file', help="File to be converted")
#parser.add_argument ('-t', '--title', help="Title for filename. (Files are renamed to <Title> 01, <Title> 02, ...)", required=True)
vgroup = parser.add_mutually_exclusive_group()
agroup = parser.add_mutually_exclusive_group()
cgroup = parser.add_mutually_exclusive_group()

parser.add_argument ('-c:v', '--vcodec',    help="Video codec", default="libx264")
vgroup.add_argument ('-crf',                help="Specify CRF for video usually between 18-24 (lower is better but bigger)", default='20')
vgroup.add_argument ('-b:v', '--vbitrate',  help="Bitrate for video, overrides CRF if specified")
parser.add_argument ('-c:a', '--acodec',    help="Audio codec", default="aac")
agroup.add_argument ('-q:a', '--aquality',  help="Audio quality", default='100')
agroup.add_argument ('-b:a', '--abitrate',  help="Audio bitrate. Overrides -aq")
cgroup.add_argument ('-copy',               help="Copy both audio and video streams. Overrides others", action="store_true")
cgroup.add_argument ('-copy:v', '--vcopy',  help="Copy only video stream", action="store_true")
cgroup.add_argument ('-copy:a', '--acopy',  help="Copy only audioo stream", action="store_true")
parser.add_argument ('--ffmpeg',            help="Path to ffmpeg.exe", default="ffmpeg.exe")
parser.add_argument ('-p ',   '--preset',   help="Preset speed/qual tradeoff. slow(better) ... fast(worse)", default="slow")
parser.add_argument ('-o',   '--output',    help="Specify output filename")
parser.add_argument ('-n',   '--no_overwrite', help="Overwrite output file", action="store_true")
parser.add_argument ('-other',              help="Other arguments to ffmpeg")
args = parser.parse_args()

if os.path.exists(args.input_file):
    print "exists " + args.input_file
    cmd_args = construct_cmd()

    print "\n" + "-" * 22 + " STARTING " + "-" * 22
    print " ".join([str(i) for i in cmd_args])    
    print "\n" + "-" * 54
    
    ret = subprocess.call(cmd_args)
    if not ret:
        print "!!! SUCCESS !!!"
    else:
        print "FFMpeg exited with error"

    print "\n" + "-" * 22 + " FINISHED " + "-" * 22
    print " ".join([str(i) for i in cmd_args])    
    print "\n" + "-" * 54




else:
    print "ERROR: No such file - ", args.input_file
    sys.exit(-1);
