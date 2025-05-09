#!/bin/bash
while true
do
    # Capture the settings and append to a log file with timestamp
    echo "$(date) - Line, Mic, and Master settings:" >> /home/pi/webapp/logfile.txt
    amixer -c 2 sget 'Line',0 >> /home/pi/webapp/logfile.txt
    amixer -c 2 sget 'Mic',0 >> /home/pi/webapp/logfile.txt
    amixer -c 2 sget 'Master' >> /home/pi/webapp/logfile.txt
    echo "---------------------------------" >> /home/pi/webapp/logfile.txt
    sleep 10
done
