# -*- coding: utf-8 -*-
"""
Created on Sun Aug 10 19:17:03 2014

@author: imad
- Wrapper for ffmpeg cli. Simply takes a video file and encodes it to mp4 as per default settings. Parameters can be changed.
- Dependencies: ffmpeg (incl. x264, libaac/libfdk_aac support), mediainfo-cli

"""

import os
import sys
import argparse
import subprocess
import shlex
from pymediainfo import MediaInfo
import time
from time import localtime, strftime

def enquote(str):
    return '"{}"'.format(str)

def get_vargs():
    if args.vcopy:
        v_args = ['-c:v', 'copy']
        return v_args
    
    v_args = ['-c:v', args.vcodec]     
    v_opts = ['-crf', args.crf]

    if args.samecbr or args.vcbr:
        v_cbr = get_cbr(args.input_file,'Video')
        v_opts = ['-b:v', v_cbr]
    elif args.vbitrate:
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

    if args.samecbr or args.acbr:
        a_cbr = get_cbr(args.input_file,'Audio')
        a_opts = ['-b:a', a_cbr]
    elif args.abitrate:
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
    
    outfile = "\"{}\"".format(outfile)
    print "Output file - " + outfile
    return outfile

def construct_cmd():
    ffmpeg_bin = enquote(args.ffmpeg)
    quoted_input = enquote(args.input_file)
    main_args = [ffmpeg_bin , '-i', quoted_input]

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
    
def get_video_codec(track):
    if track.codec_info is None:
        return "{}".format(track.codec)
    return "{} ({})".format(track.codec, track.codec_info)
    
def get_video_bitrate(track):
    if track.codec == "AVC":
        if not track.other_maximum_bit_rate is None and track.other_nominal_bit_rate is None:
            br = "{} / {} (nominal) / {} (max)".format(track.other_bit_rate[0], track.other_nominal_bit_rate[0], track.other_maximum_bit_rate[0])
            return br
    return "{}".format(track.other_bit_rate[0])

def get_video_size(track):
    if track.codec == "AVC":
        if not track.other_source_stream_size is None:
            return "{}".format(track.other_source_stream_size[0])
    return "{}".format(track.other_stream_size[0])

def get_audio_codec(track):
    if track.codec_info is None:
        return "{} ({})".format(track.codec, track.commercial_name)
    return "{} ({} / {})".format(track.codec, track.codec_info, track.commercial_name)

def get_audio_resolution(track):
    if track.other_resolution is None:
        track.other_resolution = ["?? bits"]
    return "{}".format(track.other_resolution[0])   

def get_audio_mode(track):
    if track.bit_rate_mode is None:
        track.bit_rate_mode = "Unspecified mode"
    return "{}".format(track.bit_rate_mode)   

def get_cbr(video_file, t_type):
    media_info = MediaInfo.parse(video_file)
    cbr = 0
    
    for track in media_info.tracks:
        if track.track_type == t_type:
            cbr=track.bit_rate
    
    return str(cbr)


def report_stats(video_file):
    media_info = MediaInfo.parse(video_file)

    filestr = "{:<20} : {} ".format("File", video_file)
    print "_" * len(filestr)
    print filestr

    for track in media_info.tracks:
        if track.track_type == 'General':
            print "{:<20} : {} ; Streams ({}V / {}A)".format("Codec", track.codec, track.count_of_video_streams, track.count_of_audio_streams)
            print "{:<20} : {} ; {} ".format("Duration, Size", track.other_duration[0], track.other_file_size[0])
            print
        elif track.track_type == 'Video' :
            print "{:<20} : {} (ID - {}); {}".format("Track", track.track_type, track.track_id, track.format)
            print "{:<20} : {}".format("Codec", track.codec, get_video_codec(track))
            print "{:<20} : {}".format("Duration", track.other_duration[0])
            print "{:<20} : {} x {}".format("Resolution", track.width, track.height)
            print "{:<20} : {}".format("Bit Rate", get_video_bitrate(track))
            print "{:<20} : {}".format("Stream Size: ", get_video_size(track))
            print
        elif track.track_type == 'Audio' :
            print "{:<20} : {} (ID - {}); {}".format("Track", track.track_type, track.track_id, track.format)
            print "{:<20} : {}".format("Codec", get_audio_codec(track))
            print "{:<20} : {}".format("Duration", track.other_duration[0])
            print "{:<20} : {} ({})".format("Bit Rate", track.other_bit_rate[0], get_audio_mode(track))
            print "{:<20} : {} Hz ({})".format("Sampling rate", track.sampling_rate, get_audio_resolution(track))
            print "{:<20} : {}".format("Stream Size: ", track.other_stream_size[0])
        else:
            print "Omitting info for Track - {}".format(track.track_type)
        
    print "_" * len(filestr)
   
parser = argparse.ArgumentParser(description='Convert a file using ffmpeg')
parser.add_argument ('input_file', help="File to be converted")
#parser.add_argument ('-t', '--title', help="Title for filename. (Files are renamed to <Title> 01, <Title> 02, ...)", required=True)
vgroup = parser.add_mutually_exclusive_group()
agroup = parser.add_mutually_exclusive_group()
cgroup = parser.add_mutually_exclusive_group()

parser.add_argument ('-c:v', '--vcodec',    help="Video codec", default="libx264")
vgroup.add_argument ('-crf',                help="Specify CRF for video usually between 18-24 (lower is better but bigger)", default='20')
vgroup.add_argument ('-b:v', '--vbitrate',  help="Bitrate for video, overrides CRF if specified")
#parser.add_argument ('-c:a', '--acodec',    help="Audio codec", default="aac")
parser.add_argument ('-c:a', '--acodec',    help="Audio codec", default="libfdk_aac")
agroup.add_argument ('-q:a', '--aquality',  help="Audio quality", default='5')
agroup.add_argument ('-b:a', '--abitrate',  help="Audio bitrate. Overrides -aq")
cgroup.add_argument ('-copy',               help="Copy both audio and video streams. Overrides others", action="store_true")
cgroup.add_argument ('-copy:v', '--vcopy',  help="Copy only video stream", action="store_true")
cgroup.add_argument ('-copy:a', '--acopy',  help="Copy only audioo stream", action="store_true")
parser.add_argument ('--ffmpeg',            help="Path to ffmpeg.exe", default="C:\\Users\\humayun\\bin\\ffmpeg.exe")
parser.add_argument ('-p ',     '--preset', help="Preset speed/qual tradeoff. slow(better) ... fast(worse)", default="slow")
parser.add_argument ('-o',      '--output', help="Specify output filename")
parser.add_argument ('-n','--no_overwrite', help="Overwrite output file", action="store_true")
parser.add_argument ('-i',      '--info',   help="Display media information", action="store_true")
parser.add_argument ('-s',  '--samecbr',    help="Convert using same CBR as input (audio and video)", action="store_true")
vgroup.add_argument ('-s:v',    '--vcbr',   help="Convert using same CBR as input (video)", action="store_true")
agroup.add_argument ('-s:a',    '--acbr',   help="Convert using same CBR as input (audio)", action="store_true")
parser.add_argument ('-x',      '--other',  help="Other arguments to ffmpeg")


args = parser.parse_args()

if os.path.exists(args.input_file):
    if args.info:
        report_stats(args.input_file)
    else:
        time_start = strftime("%Y-%m-%d %H:%M:%S", localtime())        
        cmd_args = construct_cmd()
    
        print "\n" + "-" * 22 + " STARTING " + "-" * 22
        cmd_str = " ".join([str(i) for i in cmd_args])
        print cmd_str
        print "\n" + "-" * 54

        shlexxed_args = shlex.split(cmd_str)
        # print "SHLEXXED - "
        # print shlexxed_args
        # print

        t0 = time.time()        
        ret = subprocess.call(shlexxed_args)
        #ret = subprocess.call(cmd_args)
        t1 = time.time()
        if not ret:
            print "!!! SUCCESS !!!"
            report_stats(args.input_file)
            ofile=cmd_args[-1]
            report_stats(ofile)
        else:
            print "FFMpeg exited with error"
    
        time_end = strftime("%Y-%m-%d %H:%M:%S", localtime())
        print "\n" + chr(205) * 22 + " REPORT " + chr(205) * 22 # print ════════════
        print "{:<16}: {}".format("Command", " ".join([str(i) for i in cmd_args]))
        print "{:<16}: {}".format("Start time", time_start)
        print '{:<16}: {}'.format("End time", time_end)
        print "{:<16}: {}".format("Conversion Time", strftime ("%H:%M:%S", time.gmtime(t1-t0)))
        print "\n" + chr(196) * 52 # print ────────────────
else:
    print "ERROR: No such file - ", args.input_file
    sys.exit(-1);
