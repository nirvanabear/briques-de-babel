

import os
import subprocess
from tkinter import filedialog
import shutil
from dotenv import load_dotenv
import re
import time
import requests
from tqdm import tqdm
from huggingface_hub import login, HfApi


source_dir = "audio/ffmpeg_source/"
process_dir = "audio/ffmpeg_process/"
product_dir = "audio/ffmpeg_product/"
relative_prod_dir = "../ffmpeg_product/"
output_dir = "audio/ffmpeg_output/"
match_filename = "match_file.txt"
nonmatch_filename = "nonmatch_file.txt"
silence = "silence_4s.mp3"

# language = "French"
lang1 = 'fra'
lang2 = 'eng'

load_dotenv()
hf_token = os.environ.get('HF_TOKEN_WRITE')
login(token=hf_token)
api = HfApi()

## TODO ##
# Error handling for: RemoteDisconnected 
# ConnectionError: (ProtocolError('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')), '(Request ID: 378f6a49-2887-4f85-b0d1-371c38213a06)') 
# Maybe just try again?


### Delete source file copies ###
delete_list = [ source_dir + k for k in os.listdir(source_dir) if not k.startswith('.') ]
for filepath in delete_list:
    os.remove(filepath)


### File picker dialog window then copies files ###
dialog_list = filedialog.askopenfilenames()
for file in dialog_list:
    shutil.copyfile(file, f"{source_dir}{os.path.basename(file)}")
if len(dialog_list) == 0:
    raise OSError("File Picker error. Please try again.")
print("Files to be processed:")
print(dialog_list)


### Spin up inference endpoint ###
print("\nSpinning up inference endpoint...")
print("https://endpoints.huggingface.co/nirvanabear/endpoints/mms-lid-256-uxu")
print("...")
start_time1 = time.time()
endpoint = api.resume_inference_endpoint("mms-lid-256-uxu")
# endpoint = api.get_inference_endpoint("mms-lid-256-uxu")
endpoint.wait()
api_url = endpoint.url
end_time1 = time.time()
print(f"Endpoint ready: {(end_time1 - start_time1)//60}m {round((end_time1 - start_time1)%60, 3)}s")
print(api_url)

## TODO ##
# Add timeout limits to all the subprocess calls.
# Code needs to deal with spaces in the filename.
# If reformatted already exists, then skip to next line.
# Or, delete old products before creating new ones.
# Fine-tune classification of partial French/English sentences.
# Save and load models from disk locally.
# Check out Paperspace Gradient.

### Collects names of all files to be processed. ###
source_list = [ j for j in os.listdir(source_dir) if not j.startswith('.') ]
# print(source_list)


for source in source_list:
    ### Remove space in filename ###
    if " " in source:
        new_source = source.replace(" ", "_")
        os.rename(f"{source_dir}{source}", f"{source_dir}{new_source}")
        source = new_source
    print("\n")
    print("Processing: " + source)

    ## Clear out existing mp3 versions ###
    mp3_name = f"{process_dir}{os.path.splitext(source)[0]}.mp3"
    if os.path.exists(mp3_name):
        os.remove(mp3_name)

    ### Change format to .mp3 ###
    print("Reformatting to mp3...")
    m4a_to_mp3_cmd = f"ffmpeg -hide_banner -loglevel error -i {source_dir}{source} {mp3_name}"
    m4a_to_mp3_split = m4a_to_mp3_cmd.split()
    result1 = subprocess.run(m4a_to_mp3_split, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    # print(result1.stderr)
    print(f"Reformatted to {mp3_name}")
    

    ### Create list of silences between audio clips. ###
    detect_cmd = f"ffmpeg -i {mp3_name} -af silencedetect=noise=0.0001 -hide_banner -f null - "
    detect_split = detect_cmd.split()
    result2 = subprocess.run(detect_split, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    # print(result2.stderr)
    print("Silencedetect completed.")

    ### Flip list of silences into a list of audio clips ###
    start_silence = re.findall(r"silence_start: (.*)", result2.stderr)
    end_silence = re.findall(r"silence_end: (\d*\.\d*)", result2.stderr)
    start_times = end_silence[:-1]
    end_times = start_silence[1:]
    # print(start_times)


    ## Delete existing clips currently in product_dir ###
    if (len(os.listdir(product_dir)) > 0):
        clips_list = [ k for k in os.listdir(product_dir) if not k.startswith('.') ]
        for clip in clips_list:
            if os.path.isfile((f"{product_dir}{clip}")):
                os.remove((f"{product_dir}{clip}"))


    ### Splits the audio into clips ###
    print("Splitting file into audio clips...")
    for i in range(len(start_times)):
    # for i in range(10):
        product_name = f"{product_dir}{os.path.splitext(source)[0]}_{i}.mp3"
        clip_cmd = f'ffmpeg -ss {start_times[i]} -i {mp3_name} -to {end_times[i]} -c copy -hide_banner -bitexact -f mp3 -copyts -avoid_negative_ts 2 {product_name}'
        # print(f"{source_dir}{os.path.splitext(source)[0]}.mp3")
        clip_split = clip_cmd.split()
        result3 = subprocess.run(clip_split, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        # print(result3.stderr)
    print("Audio split completed.")


    ### Filepath for clips producted from source audio ###
    product_list = [ j for j in os.listdir(product_dir) if not j.startswith('.') ]
    # print(product_list)

    ### HTTP request version ###
    headers = {
        "Accept" : "application/json",
        "Authorization": f"Bearer {hf_token}",
        "Content-Type": "audio/mpeg" 
    }
    def query(filename):
        with open(filename, "rb") as f:
            data = f.read()
        response = requests.post(api_url, headers=headers, data=data)
        return response.json()

    ### Run inference ###
    print("Inference starting...")
    infer_list = []
    path_list = []
    start_time2 = time.time()
    endpoint.resume()
    api_url = endpoint.url
    for track in tqdm(product_list):
        inference = query(product_dir + track)
        # print(inference[0])
        infer_list.append(inference)
        path_list.append(relative_prod_dir + track)
    end_time2 = time.time()
    print(f"Inference compute time: {(end_time2 - start_time2)//60}m {round((end_time2 - start_time2)%60, 3)}s")


    ### Evaluate language score ###
    match_list = []
    nonmatch_list = []
    for j in range(len(infer_list)):
        for id_score in infer_list[j]:
            if id_score["label"] == lang1 and id_score["score"] > 0.50:
                match_list.append("file " + "'" + path_list[j] + "'\n")
            else:
                nonmatch_list.append("file " + "'" + path_list[j] + "'\n")
                

    ### Sort, insert silence as spacing ###
    match_list.sort()
    nonmatch_list.sort()
    spaced_matches = []
    for item in match_list:
        spaced_matches.append(item)
        spaced_matches.append("file " + "'" + f"{silence}" + "'\n")

    ### Create ffmpeg concat instructions file ###
    # print(match_list)
    # print(nonmatch_list)
    with open(f"{process_dir}{match_filename}", 'w') as match_file:
        with open(f"{process_dir}{nonmatch_filename}", 'w') as nonmatch_file:
            [ match_file.write(track_path) for track_path in spaced_matches ]
            [ nonmatch_file.write(track_path2) for track_path2 in nonmatch_list ]

    ### Delete mp3 file version if already in output ###
    output_name = f"{output_dir}{os.path.splitext(source)[0]}_{lang1}.mp3"
    if os.path.exists(output_name):
        os.remove(output_name)

    ### Concatinate final output mp3 ###
    concat_cmd = f"ffmpeg -f concat -safe 0 -i {process_dir}{match_filename} -c copy {output_dir}{os.path.splitext(source)[0]}_{lang1}.mp3"
    concat_split = concat_cmd.split()
    result4 = subprocess.run(concat_split, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    # print(result4.stderr)
    print(f"{process_dir}{os.path.splitext(source)[0]}_{lang1}.mp3 output file.")

    ### Delete mp3 file version after usage ###
    if os.path.exists(mp3_name):
        os.remove(mp3_name)

    ### Delete existing clips currently in product_dir ###
    if (len(os.listdir(product_dir)) > 0):
        clips_list = [ k for k in os.listdir(product_dir) if not k.startswith('.') ]
        for clip in clips_list:
            if os.path.isfile((f"{product_dir}{clip}")):
                os.remove((f"{product_dir}{clip}"))
    
    ### End loop ###

### Delete source file copies ###
delete_list = [ source_dir + k for k in os.listdir(source_dir) if not k.startswith('.') ]
for filepath in delete_list:
    os.remove(filepath)

proceed = input("Finished? Would you like to pause the endpoint? (y/n)")
if proceed.lower() == "y":
    endpoint.pause()
