#!/usr/bin/env python3
import os
import sys
import shutil
import sqlite3
import tempfile
import csv
from datetime import datetime, timedelta

def user_data_dir():
    if sys.platform.startswith('win'):
        return os.path.join(os.environ.get('LOCALAPPDATA', ''),"Google", "Chrome", "User Data")

def find_profiles(user_data_dir):
    profiles = []
    for files in os.listdir(user_data_dir):
        path = os.path.join(user_data_dir, files)
        if os.path.isdir(path) and os.path.exists(os.path.join(path, "History")):
            profiles.append((files, path))
    return profiles

def convert_time(ct):
    time = datetime(1601, 1, 1) + timedelta(microseconds=ct)
    return time

def copy_db(src):
    f, temp = tempfile.mkstemp(suffix=".db")
    os.close(f)
    shutil.copy2(src, temp)
    return temp

def extract_history(path, csv_path):
    temp = copy_db(path)
    conn = sqlite3.connect(temp)
    cur = conn.cursor()
    cur.execute("""
        SELECT url, title, last_visit_time
        FROM urls
        WHERE url IS NOT NULL
        ORDER BY last_visit_time DESC
    """)
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        file = csv.writer(f)
        file.writerow(["URL","Title","Last Visit"])
        for url, title, ct in cur:
            try:
                time = convert_time(ct).strftime("%d-%m-%Y %H:%M:%S")
            except:
                time = ""
            file.writerow([url, title, time])
    conn.close()
    os.remove(temp)

def extract_top_sites(path, csv_path):
    temp = copy_db(path)
    conn = sqlite3.connect(temp)
    cur = conn.cursor()
    cur.execute("""
        SELECT url, url_rank 
        FROM top_sites
        ORDER BY url_rank
    """)
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        file = csv.writer(f)
        file.writerow(["Rank","URL"])
        for url, rank in cur:
            file.writerow([rank, url])
    conn.close()
    os.remove(temp)

def extract_autofill(path, csv_path):
    temp = copy_db(path)
    conn = sqlite3.connect(temp)
    cur = conn.cursor()
    cur.execute("""
        SELECT name, value FROM autofill ORDER BY date_created DESC
    """)
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        file = csv.writer(f)
        file.writerow(["Name","Value"])
        for name, val in cur:
            file.writerow([name, val])
    conn.close()
    os.remove(temp)
