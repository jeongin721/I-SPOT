import os
import json
import pandas as pd
import torch
import torchaudio
import torchaudio.transforms as T
import librosa
import soundfile as sf
from datetime import datetime
from tqdm.auto import tqdm



  
# datasets의 in 폴더 = mp3 file  (원천데이터 mp3 파일)
wav_dir = '/workspace/kavadata/in/'

# datasets의 out 폴더 = json file  (원천데이터 json 파일)
json_dir = '/workspace/kavadata/out/'

# answer 부분만 잘라내어 처리된 새로운 mp3 file 저장될 폴더  (원천데이터로부터 추출되어질 대답 부분의 음성파일이 저장될 경로)
save_new_dir = '/workspace/kavadata/'



def time_to_seconds(time_str):
    time_obj = datetime.strptime(time_str, '%M:%S.%f')
    seconds = time_obj.minute * 60 + time_obj.second + time_obj.microsecond / 1e6
    return seconds


for _, filename in enumerate(tqdm(os.listdir(json_dir))):
    if filename.endswith('.json'):
        filename = "0002.json"
        json_file_path = os.path.join(json_dir, filename)
        merged_audio = None
        wav_name = filename.split(".")[0]
        file_size = os.path.getsize(json_file_path) / 1024
        
        if file_size <= 3:  # 3KB 이하인 경우 건너뛰기
            continue
     
        with open(json_file_path, 'r') as json_file:
            json_data = json.load(json_file)
            
        audio_texts = []

        first_list_item = json_data["list"]
        list_max_num = len(first_list_item)
        
        for i in range(list_max_num) :
            text_sector = first_list_item[i]
        
            ## version 1
            if "audio" in text_sector.keys() :
                audio_list = text_sector.get("audio")
                answer_dict = [item for item in audio_list if item['type'] == 'A']
                
                for item in answer_dict:
                    # print(item)
                    text = item.get('text')     
                    start_time = item.get('start')
                    end_time = item.get('end')
                    
                    try :
                        start_time = time_to_seconds(start_time)
                        end_time = time_to_seconds(end_time)
                    except ValueError :
                        break
                                   
                    waveform, sample_rate = torchaudio.load(wav_dir+wav_name+".mp3")
                    
                    start_sample = int(start_time * sample_rate)
                    end_sample = int(end_time * sample_rate)
                    trimmed_waveform = waveform[:, start_sample:end_sample]
                    
                    if merged_audio is None:
                        merged_audio = trimmed_waveform
                    else:
                        merged_audio = torch.cat((merged_audio, trimmed_waveform), dim=1)
            ## version 2
            else  :
                ## 음성이 없는건 audio 컬럼이 아예 빠지면서 오류가 남.
                try: 
                    audio_list = text_sector.get("list")
                    
                    for in_audio in audio_list :
                        print(in_audio)
                        
                        
                        audio_text= [item for item in in_audio['audio'] if item['type'] == 'A']

                        for item in audio_text:
                            text_values = item['text']
                            start_time = item.get('start')
                            end_time = item.get('end')
                            
                            try : 
                                start_time = time_to_seconds(start_time)
                                end_time = time_to_seconds(end_time)
                                # print(filename)
                                pass
                            except ValueError :
                                # print(filename)
                                break
                            
                            waveform, sample_rate = torchaudio.load(wav_dir+wav_name+".mp3")
                        
                            start_sample = int(start_time * sample_rate)
                            end_sample = int(end_time * sample_rate)
                            trimmed_waveform = waveform[:, start_sample:end_sample]
                            
                            if merged_audio is None:
                                merged_audio = trimmed_waveform
                            else:
                                merged_audio = torch.cat((merged_audio, trimmed_waveform), dim=1)
                except KeyError :
                    pass
                 
        try :
            sf.write(save_new_dir+wav_name+".mp3", merged_audio[0].numpy(), sample_rate)
        except TypeError :
            continue
        
