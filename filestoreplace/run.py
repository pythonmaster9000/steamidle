from steamctl.commands.assistant import card_idler
import time
import csv

filename = 'logins.csv'
rows = []
with open(filename, 'r') as info:
    csvreader = csv.reader(info)
    next(csvreader)
    for row in csvreader:
        rows.append(row)


class Args:
    anonymous = None
    user = None
    app_ids = [1172470]


for _ in range(len(rows)):
    card_idler.cmd_assistant_idle_games(Args())
    time.sleep(3)
