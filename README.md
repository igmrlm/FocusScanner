# FocusScanner
This python script scans the chosen folder of most photo formats (including some raw types) and sorts them with the most 'in focus' photos at the top

# Usage

pip install opencv-python rawpy pillow

python ./FocusScanner.py

# Introduction

This is a fairly basic python gui script that uses openCV and rawpy to scan a folder of photos and rank them with a Laplacian function.
The user can set the desired threshold and then copy the list of files to another folder. 

# Background

A friend of mine invited me to his live show as a media rep to take photos and videos. I ended up using burst mode a lot and took over 4000 photos.. as one often does when they had a few beers. Sooo a week later, he needs the pics for an upcoming radio spot and I did not have time to sort through all 4000 photos and find the ones that were in focus, not blurry, not a blank wall or whatever.. and so I made this to make my life easier, and it worked way better than I could have expected. 

# About

If you found this useful as a photographer please consider sending a few $ my way at https://ko-fi.com/nathanaelnewton
I considered trying to make money directly from this but so many friends wanted it I felt it would be better to publish it as open source, especially considering it's so simple and uses openCV to do all the real work. 
