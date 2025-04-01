#!/bin/bash
# Analyzes audio and returns mixed list of start and end of silences

# $1: input audio

#TODO:
# Create output file names based off of input file name.

ffmpeg -i Lesson_22.m4a -af silencedetect=noise=0.0001 -hide_banner -f null - 2>&1 | grep "silence_" | grep -v size | awk '{print $5}' > Lesson_22.txt

# Delete first line from silencedetect output
sed -i '' '1d' ref_22/Lesson_22.txt

# Create list of endpoint pairs of audible content

rm ref_22/Lesson_22_endpoints.txt
while read line1
do
read line2
echo $line1 $line2 >> ref_22/Lesson_22_endpoints.txt
done < ref_22/Lesson_22.txt


# Create silent audio: change duration as needed

ffmpeg -ss 126 -i "ref_22/Lesson_22.m4a" -to 128 -c copy -copyts -avoid_negative_ts 2 "ref_22/silence_2s.m4a"

# Play clips and prompt user to select French versions

rm ref_22/Lesson_22_fr_epoints.txt
exec 3<&0
while read start stop
do
echo "play: $start"
ffplay -ss "$start" -t 2 -autoexit -hide_banner -i "ref_22/Lesson_22.m4a" 2>/dev/null
echo "$start"
echo "Yes/no?"
answer=0
read answer <&3
if [ "$answer" = "z" ]; then	
echo "Add $start, $stop to file."
echo "$start $stop" >> ref_22/Lesson_22_fr_epoints.txt
fi
done < ref_22/Lesson_22_endpoints.txt

# Read user selected endpoint list and create clips
# Also create clip list, alternated with silent clips

exec 3<&0
num=1
mkdir clips_22
rm clip_list_22.txt
while read start stop
do
ffmpeg -ss "$start" -i "ref_22/Lesson_22.m4a" -to "$stop" -c copy -hide_banner -copyts -avoid_negative_ts 2 "clips_22/L22_$num.m4a" 2>/dev/null
echo "clips_22/L22_$num.m4a"
echo "file 'clips_22/L22_$num.m4a'" >> clip_list_22.txt
echo "file 'ref_22/silence_2s.m4a'" >> clip_list_22.txt
num=$((num+1))
done < ref_22/Lesson_22_fr_epoints.txt

# Concatinate using clip list and folder of clips!

ffmpeg -f concat -safe 0 -hide_banner -i clip_list_22.txt -c copy ref_22/output_22.m4a


exit 0
