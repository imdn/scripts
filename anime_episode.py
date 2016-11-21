#!/bin/python
#  coding: utf8

import codecs
import re
import sys
import requests
import os
import glob
import argparse
from terminaltables import SingleTable
from bs4 import BeautifulSoup

def TableParser(soupObj, offset):
    tables=soupObj.findAll('table')
    names = []
    for table in tables:
        rows= table.findAll('tr')
        rowSpan=False
        for row in rows:
            header = row.find('th')
            if header and 'id' in header.attrs:
                epid = header.string
                #print "Found episode: ", epid

                # Multiple titles for an episode
                if 'rowspan' in header.attrs:
                    num_rows=int(header['rowspan'])
                    rowSpan=True

                if not rowSpan:
                    cols = row.find_all('td', class_='summary')
                else:
                    cols=row.find_all('td')
                    num_rows -= 1;
                
                episode = processCols(row, epid, cols)
                if episode != "":
                    names.append(episode)
                    
            elif rowSpan:
                cols = row.find_all('td', class_="summary")
                episode = processCols(row, epid, cols)
                if episode != "":
                    names.append(episode)
                num_rows -= 1
                if num_rows == 0:
                    rowSpan=False
    return names

def processCols(row, epid, cols):
    ep_name = ""
    if cols:
        if re.match("^[0-9]$", epid):
            epid = "{0:02d}".format(int(epid))
        col=cols[0]
        ja_elem = col.find('span')
        if ja_elem and ja_elem['lang'] == "ja":
            title = stringToValidFilename (list(col.stripped_strings)[0]).strip(u'\'')
            ja_title= stringToValidFilename (ja_elem.string).strip('\'')
            ep_name = ("{} {} {}".format(epid, title, ja_title))
        else:
            title = stringToValidFilename (list(col.stripped_strings)[0]).strip('\'')
            ep_name = ("{} {}".format(epid, title))
    return ep_name
    

def stringToValidFilename(str):
    # Invalid characters in Windows filenames \/:*?\"<>|
    out = str.translate({
        ord('\\'): ',',
        ord('/'): ',',
        ord('|'): ',',
        ord(':'): '-',
        ord('*'): '-',
        ord('?'): '',
        ord('"'): '\'',
        ord('<'): '[',
        ord('>'): ']',
        ord(u'\xa0'): ' '
    })
    return out

def parseWiki(url, table_offset):
    print ("Fetching URL - " + url)
    r = requests.get(url)
    html = r.text
    soup = BeautifulSoup(html, "lxml")
    new_names = TableParser(soup, table_offset)
    return new_names

def parseURL(url):
    if re.match('^https?://', url):
        return url
    return 'https://en.wikipedia.org/wiki/' + url

def renameFiles(data):
    for d in data:
        old_file = d[0]
        new_file = d[1]
        dir = os.path.dirname(os.path.abspath(old_file))
        ext = os.path.splitext(old_file)[1]
        new_path = os.path.join(dir + os.sep + new_file + ext)
        os.replace(old_file, new_path)
        
#url = "http://en.wikipedia.org/wiki/List_of_Gintama_episodes"

parser = argparse.ArgumentParser(description='Rename files from Wikipedia entries')
parser.add_argument ('-f', help="File Pattern", nargs="+")
parser.add_argument ('-u', '--url', help="Complete URL incl. http or just the name of entry page)", required=True)
parser.add_argument ('-n', '--offset', help="Which table in page to parse (default=0)", default=0)

args = parser.parse_args()
url = parseURL(args.url)
new_names = parseWiki(url, args.offset)

if len(new_names) > 0:
    if args.f is not None and len(args.f) > 0:
        if len(new_names) != len(args.f):
            print("\n\nWarning!!! Unequal lenght for wiki entries ({}) and local files({}). Check wildcard usage\n\n".format(len(new_names), len(args.f)))
        table_data = [['OLD Filename', 'NEW Filename']]
        data = [list(i) for i in zip(args.f, new_names)]
        table_data.extend(data)
        table = SingleTable(table_data)
        print (table.table)
        ch = input("Rename? [yN]")
        if ch == 'y' or ch == "Y":
            renameFiles(data)
    else:
        for name in new_names:
            print(name)
else:
    print ("Could not obtain names from Wikipedia. Check URL - ", url)

