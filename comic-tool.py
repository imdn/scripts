#!/bin/python

import argparse
import os
import os.path
import sys
import zipfile
import re
import io
from PIL import Image

# In Memory zipfile
class InMemZip(object):
    def __init__(self):
        self.byteBuf = io.BytesIO()

    def write(self, filename, data):
        with zipfile.ZipFile(self.byteBuf, 'a') as tmp:
            tmp.writestr(filename, data)

    def fixPermissions(self):
        # Mark as having been created on Windows
        with zipfile.ZipFile(self.byteBuf,'a') as tmp:
            for f in tmp.infolist():
                f.create_system = 0

    def printdir(self):
        with zipfile.ZipFile(self.byteBuf, 'r') as tmp:
            tmp.printdir()

    def read(self):
        self.byteBuf.seek(0)
        return self.byteBuf.read()

    def writeToFile(self, filename):
        self.fixPermissions()
        open(filename, 'wb').write(self.read())

# In-memory manipulation of Image
class InMemImage(object):
    def __init__(self,fileObj):
        self.imgFile = Image.open(fileObj)
        self.height = self.imgFile.height
        self.width = self.imgFile.width

    def convert_and_save(self, fmt):
        IMG_EXTENSION = {
            'png' : ('PNG','png'),
            'jpeg' : ('JPEG', 'jpg'),
            'jpg' : ('JPEG', 'jpg')
        }
        imgBuf = io.BytesIO()
        if fmt == None:
            extension = None
            self.imgFile.save(imgBuf)
        else:
            new_fmt, extension = IMG_EXTENSION[fmt.lower()]
            print ("Converting to format - {}".format(new_fmt))
            if self.imgFile.mode == "P":
                self.imgFile.convert("RGB").save(imgBuf, new_fmt)
            else:
                self.imgFile.save(imgBuf, new_fmt)
        imgBuf.seek(0)
        return (imgBuf, extension)

    def resize(self, dim):
        if not re.match('\d+[xX]\d+|\d+[xX]|[xX]\d+', dim):
            print ("Invalid resize specification - ", dim)
            sys.exit(-1)
        width, height = dim.split('x')
        if width == '':
            width = self.width * int(height) / self.height
        elif height == '':
            height = width * self.height / self.width
        dimensions = (int(width), int(height))

        print("Resized from {}x{} ----> {}x{}".format(self.width, self.height, int(width), int(height)))
        self.imgFile = self.imgFile.resize(dimensions, Image.ANTIALIAS)

def parse_range(pg_range, max_range):
    ranges = pg_range.split(",")
    pages = dict()
    for r in ranges:
        if re.match('^\d+$',r):
            r_num = int(r)
            if r_num > max_range:
                print ("Range Specification exceeds number of files : ", r_num)
            pages[r_num] = 1
        elif re.match('^\d+-\d+$',r):
            r_start, r_end = r.split('-')
            r_start = int(r_start)
            r_end = int(r_end)
            if r_start > r_end: # Swap
                temp = r_start
                r_start = r_end
                r_end = temp
            if r_start > max_range or r_end > max_range:
                print ("\nWARNING!!! Range Specification exceeds number of files :", r, "\n")
            else:
                for i in range(r_start, r_end + 1):
                    pages[i] = 1
        else:
            print ("Invalid range specification - ", r)
            
    return pages

# Scale val from [a,b] to [c,d]
def scale(val, a, b, c, d):
    x = c * (1 - (val - a) / (b - a)) + d * ((val - a) / (b - a))
    return x

# Graphical display of which pages have been modified
def page_range_graphic(selected_pages, max_pages):
    unselected_page_symbol = u'\u2500'
    selected_page_symbol = u'\u2550'
    eof_symbol = u'\u2588'
    max_cols = 99
    pg_status = [unselected_page_symbol for i in range(0,max_cols)]
    for key in sorted(selected_pages.keys()):
        index = int(scale(key, 1, max_pages, 1, len(pg_status)))
        if pg_status[index - 1] == unselected_page_symbol:
            pg_status[index - 1] = selected_page_symbol
        #print("{} ({}) - {}, {}".format(key, index,(key - 1) not in selected_pages.keys(),(key + 1) not in selected_pages.keys()))
        if ((key - 1) not in selected_pages.keys()):
            pg_status[index - 1] = "{}{}".format(key, selected_page_symbol)
        elif  ((key + 1) not in selected_pages.keys()):
            pg_status[index - 1] = "{}{}".format(selected_page_symbol, key)
    return ''.join(pg_status) + eof_symbol
    
# Natural sorting for filenames
def natural_key(string_):
    """See http://www.codinghorror.com/blog/archives/001018.html"""
    return [int(s) if s.isdigit() else s for s in re.split(r'(\d+)', string_.lower())]

def samefile(file1, file2):
    return os.stat(file1) == os.stat(file2)

def generate_archive_name(infile):
    dir = os.path.dirname(infile)
    basename, ext = os.path.splitext(os.path.basename(infile))
    #print(dir, basename, ext)
    cbz_ext = '.cbz'
    outfile = os.path.join(dir,basename) + cbz_ext
    
    if os.path.exists(outfile):
        if samefile(infile, outfile):
        # If outfile is same as infile, give it a new name        
            TOO_MANY_FILES = True
            print(outfile + " already exists. Trying new filename(s)")
            for i in range(1,5):
                outfile = os.path.join(dir,basename) + "_MODIFIED_" + str(i) + cbz_ext
                print("Now trying new output filename - "  + outfile)
                if os.path.exists(outfile) is False:
                    TOO_MANY_FILES=False                
                    break;
            if TOO_MANY_FILES:
               print("!!! Too many duplicate output files appear to exist. Fix before trying !!!")
               sys.exit(-2);
    
    outfile = "{}".format(outfile)
    print("Output file - " + outfile)
    return outfile

def get_sorted_filelist(zfile):
    with (zipfile.ZipFile(zfile, 'r')) as comic: 
        files_in_archive = comic.namelist()
        files_no_dirs = []
        for file in files_in_archive:
            if not re.match(".*/$", file):
                files_no_dirs.append(file)
        sorted_files = sorted(files_no_dirs, key=natural_key)
        return sorted_files

def create_archive_from_extracted(zfile, new_zfile, selection, resize_dim=None, img_format=None):
    memZ = InMemZip()
    with zipfile.ZipFile(zfile,'r') as zbuf:
        for f in selection:
            fname = f
            if resize_dim is not None or img_format is not None:
                img = InMemImage(zbuf.open(f))
                print ("Manipulating Image - '{}'".format(f))
                if resize_dim is not None:
                    img.resize(resize_dim)
                imgbuf, new_ext = img.convert_and_save(img_format)
                buf = imgbuf.read()
                dir = os.path.dirname(f)
                name_no_ext, old_ext = os.path.splitext(os.path.basename(f))
                if new_ext is None:
                    new_ext = old_ext
                fname = os.path.join (dir, name_no_ext) + "." + new_ext
            else:
                buf = zbuf.read(f)

            memZ.write(fname, buf)

    memZ.writeToFile(new_zfile)

def join_selected_archives(files, new_zfile):
    memZ = InMemZip()
    count = 0
    for file in files:
        count += 1
        sorted_files = get_sorted_filelist(file)
        with zipfile.ZipFile(file, 'r') as zbuf:
            for sf in sorted_files:
                new_name = "{:02d} - {}/{}".format(count, os.path.basename(file), sf)
                buf = zbuf.read(sf)
                memZ.write(new_name, buf)

    #memZ.printdir()
    memZ.writeToFile(new_zfile)

def get_user_confirmation(msg):
    ch = input(msg + " [yN]")
    if ch == 'y' or ch == "Y":
        return True
    return False

def main():
    parser = argparse.ArgumentParser(description='Manipulate Comic Book archives (split, extract, trim)')
    input_group = parser.add_mutually_exclusive_group()

    input_group.add_argument('-i', '--input', help="Path to comic book archive (cbz/cbr/zip/rar)", default=None)
    input_group.add_argument('-j', '--join', help="Join filenames in Order Specified", nargs="+")
    parser.add_argument('-x', '--extract', help="Extract ranges to new archive. Format 3,4,10-19")
    parser.add_argument('-r', '--resize', help="Resize images e.g. 1600x1200, x1200 (height only), 1600x (width only) ", default=None)
    parser.add_argument('-f', '--iformat', help="Convert images to formart (png/jpg)", default=None)
    parser.add_argument('-o', '--output', help="Output filename")

    args=parser.parse_args()

    if args.input is not None:
        if zipfile.is_zipfile(args.input):
            sorted_files = get_sorted_filelist(args.input)
            #print ("Files in archive (Excl. directories) - ", len(sorted_files))
            
            if args.output is None:
                args.output = generate_archive_name(args.input)
            if args.extract is not None:
                pages_2_extract = parse_range(args.extract, len(sorted_files))
                if len(pages_2_extract.keys()) == 0:
                    print ("Invalid range specification")
                else:
                    graphic = page_range_graphic(pages_2_extract, len(sorted_files))
                    print ("\n{} of {} pages will be extracted\n\n{}\n".format(len(pages_2_extract), len(sorted_files), graphic))
                    count = 0
                    selected_pages = []
                    for file in sorted_files:
                        count += 1
                        if count in  pages_2_extract:
                            selected_pages.append(file)
                    #print ("Selected Pages - ", selected_pages)
                    if get_user_confirmation("Extract files and create new archive?"):
                        create_archive_from_extracted(args.input, args.output, selected_pages, args.resize, args.iformat)

            elif args.resize or args.iformat is not None:
                if get_user_confirmation("Process files and create new archive?"):
                    create_archive_from_extracted(args.input, args.output, sorted_files, args.resize, args.iformat)
        else:
            print ("ERROR! Invalid zip file - ", args.input)
    elif args.join is not None:
        for file in args.join:
            if not zipfile.is_zipfile(file):
                print ("ERROR! Invalid zip file - ", file)
                sys.exit(-1)
        
        if args.output is None:
            args.output = generate_archive_name(args.join[0])
        if get_user_confirmation("Join files and create new archive?"):
            join_selected_archives(args.join, args.output)

    print ("Done!\n")

if __name__ == "__main__":
    main()
