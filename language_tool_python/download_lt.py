#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Download latest LanguageTool distribution."""

import glob
import logging
import os
import re
import requests
import subprocess
import sys
import os
import tqdm
import zipfile
import uuid

from distutils.spawn import find_executable
from urllib.parse import urljoin
from .utils import get_language_tool_download_path

# Create logger for this file.
logging.basicConfig(format='%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# Get download host from environment or default.
BASE_URL = os.environ.get('LTP_DOWNLOAD_HOST', 'https://github.com/plotlyst/feed/releases/download/spellcheck/')
FILENAME = 'LanguageTool-{version}.zip'

LATEST_VERSION = '6.4'

JAVA_VERSION_REGEX = re.compile(
    r'^(?:java|openjdk) version "(?P<major1>\d+)(|\.(?P<major2>\d+)\.[^"]+)"',
    re.MULTILINE)

# Updated for later versions of java
JAVA_VERSION_REGEX_UPDATED = re.compile(
    r'^(?:java|openjdk) [version ]?(?P<major1>\d+)\.(?P<major2>\d+)',
    re.MULTILINE)


def parse_java_version(version_text):
    """Return Java version (major1, major2).

    >>> parse_java_version('''java version "1.6.0_65"
    ... Java(TM) SE Runtime Environment (build 1.6.0_65-b14-462-11M4609)
    ... Java HotSpot(TM) 64-Bit Server VM (build 20.65-b04-462, mixed mode))
    ... ''')
    (1, 6)

    >>> parse_java_version('''
    ... openjdk version "1.8.0_60"
    ... OpenJDK Runtime Environment (build 1.8.0_60-b27)
    ... OpenJDK 64-Bit Server VM (build 25.60-b23, mixed mode))
    ... ''')
    (1, 8)

    """
    match = re.search(JAVA_VERSION_REGEX, version_text) or re.search(JAVA_VERSION_REGEX_UPDATED, version_text) 
    if not match:
        raise SystemExit(
            'Could not parse Java version from """{}""".'.format(version_text))
    major1 = int(match.group('major1'))
    major2 = int(match.group('major2')) if match.group('major2') else 0
    return (major1, major2)

def confirm_java_compatibility():
    """ Confirms Java major version >= 8. """
    java_path = find_executable('java')
    if not java_path:
        # Just ignore this and assume an old version of Java. It might not be
        # found because of a PATHEXT-related issue
        # (https://bugs.python.org/issue2200).
        raise ModuleNotFoundError('No java install detected. Please install java to use language-tool-python.')

    output = subprocess.check_output([java_path, '-version'],
                                     stderr=subprocess.STDOUT,
                                     universal_newlines=True)

    major_version, minor_version = parse_java_version(output)
    # Some installs of java show the version number like `14.0.1` and others show `1.14.0.1`
    # (with a leading 1). We want to support both, as long as the major version is >= 8.
    # (See softwareengineering.stackexchange.com/questions/175075/why-is-java-version-1-x-referred-to-as-java-x)
    if major_version == 1 and minor_version >= 8:
        return True
    elif major_version >= 8:
        return True
    else:
        raise SystemError('Detected java {}.{}. LanguageTool requires Java >= 8.'.format(major_version, minor_version))

def get_common_prefix(z):
    """Get common directory in a zip file if any."""
    name_list = z.namelist()
    if name_list and all(n.startswith(name_list[0]) for n in name_list[1:]):
        return name_list[0]
    return None

def http_get(url, out_file, proxies=None):
    """ Get contents of a URL and save to a file.
    """
    with requests.get(url, stream=True, proxies=proxies, timeout=10) as req:
        req.raise_for_status()
        content_length = req.headers.get('Content-Length')
        total = int(content_length) if content_length is not None else None
        progress = tqdm.tqdm(unit="B", unit_scale=True, total=total, desc=f'Downloading LanguageTool {LATEST_VERSION}')
        with open(out_file, 'wb') as f:
            for chunk in req.iter_content(chunk_size=8192):
                progress.update(len(chunk))
                f.write(chunk)
    
        progress.close()

def unzip_file(temp_file, directory_to_extract_to):
    """ Unzips a .zip file to folder path. """
    logger.info('Unzipping {} to {}.'.format(temp_file, directory_to_extract_to))
    with zipfile.ZipFile(temp_file, 'r') as zip_ref:
        zip_ref.extractall(directory_to_extract_to)


def download_zip(url, directory):
    """ Downloads and unzips zip file from `url` to `directory`. """
    downloaded_file = os.path.join(directory, f'{uuid.uuid4()}.zip')
    http_get(url, downloaded_file)
    
    unzip_file(downloaded_file, directory)
    os.remove(downloaded_file)
    
    logger.info('Downloaded {} to {}.'.format(url, directory))

def download_lt():
    download_folder = get_language_tool_download_path()
    assert os.path.isdir(download_folder)
    old_path_list = [
        path for path in
        glob.glob(os.path.join(download_folder, 'LanguageTool*'))
        if os.path.isdir(path)
    ]

    version = LATEST_VERSION
    filename = FILENAME.format(version=version)
    language_tool_download_url = urljoin(BASE_URL, filename)
    dirname = os.path.splitext(filename)[0]
    extract_path = os.path.join(download_folder, dirname)

    if extract_path in old_path_list:
        return

    download_zip(language_tool_download_url, download_folder)

if __name__ == '__main__':
    sys.exit(download_lt())
