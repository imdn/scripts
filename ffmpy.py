#!/bin/python
# -*- coding: utf-8 -*-
"""
Created on Sun Aug 10 19:17:03 2014

@author: imad
- Wrapper for ffmpeg cli. Simply takes a video file and encodes it to mp4 as per default settings. Parameters can be changed.
- Dependencies: ffmpeg (incl. x264, libaac/libfdk_aac support), mediainfo-cli

"""

import os
import platform
import sys
import argparse
import subprocess
import shlex
import re
from collections import OrderedDict
from pymediainfo import MediaInfo
import time
from time import localtime, strftime
from colorama import init
from colorama import Fore, Back, Style

def enquote(str):
    return '"{}"'.format(str)

def get_vargs():
    if args.vcopy:
        v_args = ['-c:v', 'copy']
        return v_args
    
    v_args = ['-c:v', args.vcodec]     
    v_opts = ['-crf', args.crf]
    v_filter = []

    if args.samecbr or args.vcbr:
        v_cbr = get_cbr(args.input_file,'Video')
        v_opts = ['-b:v', v_cbr]
    elif args.vbitrate:
        v_opts = ['-b:v', args.vbitrate]

    if args.aspectratio:
        res = args.aspectratio
        if res == "1080p":
            res = "1920:1080"
        elif res == "720p":
            res = "1280:720"
        elif res == "540p":
            res = "960:540"
        elif res == "480p":
            res = "640:480"
        elif res == "360p":
            res == "480:360"
        elif res == "240p":
            res == "320:240"
        scale = "scale={}".format(res)
        v_filter.extend(['-vf', scale])
    
    v_args.extend(v_opts)
    v_args.extend(v_filter)
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
    print(dir, basename, ext)
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
            print(outfile + " already exists. Trying new filename(s)")
            for i in range(1,5):
                outfile = os.path.join(dir,basename) + " NEW " + str(i) + mp4ext
                print("Now trying new output filename - "  + outfile)
                if os.path.exists(outfile) is False:
                    TOO_MANY_FILES=False                
                    break;
            if TOO_MANY_FILES:
               print("!!! Too many duplicate output files appear to exist. Fix before trying !!!")
               sys.exit(-2);
    
    outfile = "\"{}\"".format(outfile)
    print("Output file - " + outfile)
    return outfile

def construct_cmd():
    ffmpeg_bin = enquote(args.ffmpeg)
    quoted_input = enquote(args.input_file)
    main_args = [ffmpeg_bin , '-i', quoted_input]

    if args.check:
        main_args.extend(['-f', 'null', '-v', 'error', '-nostats', '-'])
    elif args.copy:    
        main_args.extend(['-c', 'copy'])
    else:
        a_args = get_aargs()
        v_args = get_vargs()
        main_args.extend(v_args)            
        main_args.extend(a_args)
        main_args.extend(['-preset', args.preset])
    
    if args.other:
        main_args.append(args.other)

    # Add metadata comment
    main_args.extend(['-metadata comment="Transcoding aided by »———————► FFMPY"'])

    if args.autocrop:
        crop_params = get_crop_values(args.input_file)
        if crop_params == None:
            print("Unknown error occurred when obtaining crop values. Blame the dev for exiting ...")
            sys.exit(-1)
        main_args.append("-vf {}".format(crop_params))

    if not args.check:
        if not args.no_overwrite:
            main_args.append('-y')

        if not args.nofaststart:
            main_args.extend(['-movflags', 'faststart'])

        output = get_output_filename()
        print(output)
        main_args.append(output)

    print(main_args)
    return main_args
    
def get_video_codec(track):
    if track.codec_info is None:
        return "{}".format(track.codec)
    return "{} ({})".format(track.codec, track.codec_info)
    
def get_video_bitrate(track):
    br = "Unknown/Could not parse"
    if track.codec == "AVC":
        if track.other_bit_rate is not None and track.other_maximum_bit_rate is not None and track.other_nominal_bit_rate is not None:
            br = "{} / {} (nominal) / {} (max)".format(track.other_bit_rate[0], track.other_nominal_bit_rate[0], track.other_maximum_bit_rate[0])
        elif not track.other_bit_rate is None:
            br = "{}".format(track.other_bit_rate[0])
        return br
    if track.other_bit_rate is not None:
        br = "{}".format(track.other_bit_rate[0])
    elif track.other_nominal_bit_rate is not None:
        br = "{}".format(track.other_nominal_bit_rate[0])
    elif track.bit_rate is not None:
        br = "{}".format(track.bit_rate[0])
    return br

def get_video_size(track):
    if track.codec == "AVC":
        if not track.other_source_stream_size is None:
            return "{}".format(track.other_source_stream_size[0])
    if track.other_stream_size is not None:
        return "{}".format(track.other_stream_size[0])
    else:
        return "Unknown"

def get_audio_bitrate(track):
    br = "Unknown/Could not parse"
    if track.other_bit_rate is not None:
        br = "{}".format(track.other_bit_rate[0])
    elif track.overall_bit_rate is not None:
        br = "{}".format(track.overall_bit_rate[0])
    else:
        if track.codec == "AAC":
            if track.other_maximum_bit_rate is not None and track.other_nominal_bit_rate is not None:
                br = "{} (nominal) / {} (max)".format(track.other_nominal_bit_rate[0], track.other_maximum_bit_rate[0])
    return br

def get_audio_size(track):
    if track.other_stream_size is not None:
        return "{}".format(track.other_stream_size[0])
    elif track.other_file_size is not None:
        return "{}".format(track.other_file_size[0])
    else:
        return "Unknown"

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

def get_value_if_not_none(var, index):
    if var is not None:
        return var[index]
    return "Unknown"

def get_crop_values(infile):
    try:
        filename = os.path.basename(infile)
        TIMEOUT=60
        log_file = "cropdetect_" + filename + ".log"
        null_dev = "/dev/null"
        if platform.system() is 'Windows':
            null_dev = "NUL"
        command = "\"{}\" -i \"{}\" -vf cropdetect -report -f null {}".format(args.ffmpeg, infile, null_dev)
        print(command)
        env_dict = os.environ.copy()
        env_dict['FFREPORT'] = 'file={}:level=32'.format(log_file)
        print("Reading cropdetect values for file - {}".format(infile))
        ret = -1
        ret = subprocess.Popen(shlex.split(command), env=env_dict, stderr=open(os.devnull, 'w')).wait(timeout=TIMEOUT)

    except subprocess.TimeoutExpired as E:
        print("Not reading cropdetect values from {} beyond {} seconds".format(infile, TIMEOUT))
        #print(E)
    finally:
        if ret > 0:
            print ("Error occurred when reading cropdetect values. Exiting ...")
            sys.exit(-2)
        else:
            ret_crop = None 
            with open(log_file, 'r') as fp:
                pattern = "^\[Parsed_cropdetect.*(crop=\d+:\d+:\d+:\d+)$"
                crop_vals = OrderedDict()
                for line in fp:
                    match = re.search(pattern, line)
                    if (match):
                        crop_vals[match.group(1)] = True
                if len(crop_vals) > 0:
                    print("\nCrop Values Detected. Autocrop uses first value used by default if more than one")
                    count = 0
                    for key in crop_vals:
                        print("{}".format(key))
                        if count == 0:
                            ret_crop = key
                        count += 1
            return ret_crop                    

def report_stats(video_file, summary=False):
    media_info = MediaInfo.parse(video_file)

    filestr = "{:<20} : {} ".format("File", video_file)

    # Print a one line summary
    if summary:
        for track in media_info.tracks:
            if track.track_type == 'General':
                format = track.codec
                duration = get_value_if_not_none(track.other_duration,0)
                size = track.other_file_size[0]
            elif track.track_type == 'Video' :
                vcodec = track.codec
                resolution = "{}x{}".format(track.width, track.height)
                vbitrate = get_video_bitrate(track)
                vsize = get_video_size(track)
            elif track.track_type == 'Audio' :
                acodec = track.codec
                abitrate = get_audio_bitrate(track)
                abitratetype = get_audio_mode(track)
                asamplingrate = track.sampling_rate
                asize = get_audio_size(track)
        mainstr = "[{}]: {} {} {}{}{}".format(video_file, format, duration, Fore.MAGENTA, size, Fore.RESET)
        vstr = "{} {}{} {}{} {}{}{}".format(vcodec, Fore.GREEN, resolution, Fore.YELLOW, vbitrate, Fore.CYAN, vsize, Fore.RESET)
        astr = "{} {}{}({}) {}{}  {}{}{}".format(acodec, Fore.YELLOW, abitrate, abitratetype, Fore.GREEN, asamplingrate, Fore.CYAN, asize, Fore.RESET)
        #outstr = "{}: {} {} {} | {} {} {} {} | {} {} {} {} {}".format(video_file, duration, size, format, vcodec, resolution, vbitrate, vsize, acodec, abitrate, abitratetype, asamplingrate, asize)
        outstr = "{} / {} / {}".format(mainstr, vstr, astr)
        print (outstr)
        return

    # Print a full tabular report
    print("_" * len(filestr))
    print(filestr)
    for track in media_info.tracks:
        if track.track_type == 'General':
            print("{:<20} : {} ; Streams ({}V / {}A)".format("Codec", track.codec, track.count_of_video_streams, track.count_of_audio_streams))
            print("{:<20} : {} ; {}{}{} ".format("Duration, Size", get_value_if_not_none(track.other_duration,0), Fore.CYAN, track.other_file_size[0], Fore.RESET))
            print()
        elif track.track_type == 'Video' :
            print("{:<20} : {} (ID - {}); {}".format("Track", track.track_type, track.track_id, track.format))
            print("{:<20} : {}".format("Codec", track.codec, get_video_codec(track)))
            print("{:<20} : {}".format("Duration", get_value_if_not_none(track.other_duration,0)))
            print("{:<20} : {} x {}".format("Resolution", track.width, track.height))
            print("{:<20} : {}".format("Bit Rate", get_video_bitrate(track)))
            print("{:<20} : {}{}{}".format("Stream Size: ", Fore.GREEN, get_video_size(track), Fore.RESET))
            print()
        elif track.track_type == 'Audio' :
            print("{:<20} : {} (ID - {}); {}".format("Track", track.track_type, track.track_id, track.format))
            print("{:<20} : {}".format("Codec", get_audio_codec(track)))
            print("{:<20} : {}".format("Duration", get_value_if_not_none(track.other_duration,0)))
            print("{:<20} : {} ({})".format("Bit Rate", get_audio_bitrate(track), get_audio_mode(track)))
            print("{:<20} : {} Hz ({})".format("Sampling rate", track.sampling_rate, get_audio_resolution(track)))
            print("{:<20} : {}{}{}".format("Stream Size: ", Fore.YELLOW, get_audio_size(track), Fore.RESET))
            print()
        else:
            if track.type is not None:
                print("Omitting info for track type - {}".format(track.type))
            else:
                print("Omitting info for Track - {}".format(track.track_type))


    print("_" * len(filestr))

def humansize(nbytes):
    suffixes = ['B', 'KiB', 'MiB', 'GiB', 'TB', 'PB']
    if nbytes == 0: return '0 B'
    i = 0
    while nbytes >= 1024 and i < len(suffixes)-1:
        nbytes /= 1024.
        i += 1
    f = ('%.2f' % nbytes).rstrip('0').rstrip('.')
    return '%s %s' % (f, suffixes[i])

# Initializes colorama
init()

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
cgroup.add_argument ('-copy:a', '--acopy',  help="Copy only audio stream", action="store_true")
parser.add_argument ('--ffmpeg',            help="Path to ffmpeg.exe", default="ffmpeg")
parser.add_argument ('-p ',     '--preset', help="Preset speed/qual tradeoff. slow(better) ... fast(worse)", default="slow")
parser.add_argument ('-o',      '--output', help="Specify output filename")
parser.add_argument ('-n','--no_overwrite', help="Overwrite output file", action="store_true")
parser.add_argument ('-i',      '--info',   help="Display media information", action="store_true")
parser.add_argument ('-1', '--summary',     help="Media info one-line summary", action="store_true")
parser.add_argument ('-s',  '--samecbr',    help="Convert using same CBR as input (audio and video)", action="store_true")
vgroup.add_argument ('-s:v',    '--vcbr',   help="Convert using same CBR as input (video)", action="store_true")
agroup.add_argument ('-s:a',    '--acbr',   help="Convert using same CBR as input (audio)", action="store_true")
parser.add_argument ('-r', '--aspectratio', help="Specify aspect ratio in FFMPEG width:height format e.g. 1280:720 or -1:1080 OR 1080p,720p,540p,480p,360p")
parser.add_argument ('-x',      '--other',  help="Other arguments to ffmpeg")
parser.add_argument ('--nofaststart',       help="Disable passing the '-movflags faststart' argument to ffmpeg", action="store_true")
parser.add_argument ('--showonly'   ,       help="Disable actual run and show only the arguments passed to ffmpeg", action="store_true")
parser.add_argument ('--check'   ,          help="Check for integrity of files, print errors only", action="store_true")
parser.add_argument ('--autocrop'   ,       help="Crop black borders automatically", action="store_true")


args = parser.parse_args()

if os.path.exists(args.input_file):
    if args.summary:
        report_stats(args.input_file, summary=True)
    elif args.info:
        report_stats(args.input_file)
    else:
        time_start = strftime("%Y-%m-%d %H:%M:%S", localtime())        
        cmd_args = construct_cmd()

        print("\n" + "-" * 22 + " STARTING " + "-" * 22)
        cmd_str = " ".join([str(i) for i in cmd_args])
        print(cmd_str)
        print("\n" + "-" * 54)

        shlexxed_args = shlex.split(cmd_str)
        #print "SHLEXXED - "
        #print shlexxed_args
        # print

        if args.showonly:
            print("Skipping actual run of ffmpeg due to argument --showonly")
            sys.exit(0)
        
        t0 = time.time()
        ret = subprocess.call(shlexxed_args)
        #ret = subprocess.call(cmd_args)

        t1 = time.time()
        if not ret:
            print("!!! SUCCESS !!!")
            report_stats(args.input_file)
            if not args.check:
                ofile=cmd_args[-1].strip('"')
                report_stats(ofile)
        else:
            print("FFMpeg exited with error")
    
        time_end = strftime("%Y-%m-%d %H:%M:%S", localtime())
        isize = os.stat(args.input_file).st_size;
        if not args.check:
            osize = os.stat(ofile).st_size;
        box_single_line = '\u2500'
        box_double_line = '\u2550'
        print("\n" + box_double_line * 22 + " REPORT " + box_double_line * 22) # print ????????????????????????????????????
        print("{:<16}: {}".format("Command", " ".join([str(i) for i in cmd_args])))
        print("{:<16}: {}".format("Start time", time_start))
        print('{:<16}: {}'.format("End time", time_end))
        print("{:<16}: {}".format("Conversion Time", strftime ("%H:%M:%S", time.gmtime(t1-t0))))
        print()
        if not args.check:
            if osize < isize:
                diff = Fore.CYAN + humansize(isize - osize)  + Fore.RESET;
                diff_ratio = 1.0 - (osize * 1.0) / isize
                print("{} Input Filesize ({}{}{}) ~ Output Filesize ({}{}{}) = {} ({:.2%} smaller)".format(
                    "COMPRESSED!!! ", Fore.RED, humansize(isize), Fore.RESET, Fore.GREEN, humansize(osize), Fore.RESET, diff, diff_ratio))
            else:
                diff = Fore.BLUE + humansize(osize - isize) + Fore.RESET;
                diff_ratio = (osize - isize) * 1.0 / isize
                print("{} Input Filesize ({}{}{}) ~ Output Filesize ({}{}{}) = {} ({:.2%} bigger)".format(
                    "WARNING!!! (output file bigger) ", Fore.GREEN, humansize(isize), Fore.RESET, Fore.RED, humansize(osize), Fore.RESET, diff, diff_ratio))
        else:
            print("Integrity check finished. If you see no error messages, then file has no errors")
        

        print("\n" + box_single_line * 52) # print ????????????????????????????????????????????????
else:
    print("ERROR: No such file - ", args.input_file)
    sys.exit(-1);
