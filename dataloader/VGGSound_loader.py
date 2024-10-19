import csv
import os
import random
import librosa
import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset,DataLoader
from torchvision import transforms

class VGGSound_DataLoader(DataLoader):
    def __init__(self,cfgs):
        self.cfgs = cfgs
        if cfgs.dataset == 'VGGSound':
            self.train_dataset = VGGSoundDataset(mode='train')
            self.test_dataset = VGGSoundDataset(mode='test')
            self.dep_dataset = VGGSoundDataset(mode="test")
        else:
            raise NotImplementedError('Incorrect dataset name {}!'.format(cfgs.dataset))
        
    @property
    def train_dataloader(self):
        return DataLoader(dataset=self.train_dataset,
                            batch_size = self.cfgs.batch_size,
                            shuffle=True,
                            num_workers=32,
                            pin_memory=True)
    @property
    def test_dataloader(self):
        return DataLoader(dataset=self.test_dataset,
                          batch_size = self.cfgs.batch_size,
                          shuffle=False,
                          num_workers=32,
                          pin_memory=True)
        
    @property
    def dep_dataloader(self):
        return DataLoader(dataset=self.dep_dataset,
                          batch_size=self.cfgs.batch_size,
                          shuffle=False,
                          num_workers=32,
                          pin_memory=True)

    
class VGGSoundDataset(Dataset):

    def __init__(self, mode='train', fps=1, use_video_frames=3):
        self.mode = mode
        train_video_data = []
        train_audio_data = []
        test_video_data = []
        test_audio_data = []
        train_label = []
        test_label = []
        train_class = []
        test_class = []
        train_items = []
        test_items = [] 
        self.item = []
        self.fps = fps
        self.use_video_frames = use_video_frames

        with open('/home/rakib/Multi-modal-Imbalance/data/VGGSound/vggsound.csv') as f:
            csv_reader = csv.reader(f)
            next(csv_reader) ## Skip the header
            
            for item in csv_reader:
                youtube_id = item[0]
                timestamp = "{:06d}".format(int(item[1]))  # Zero-padding the timestamp
                train_test_split = item[3]

                video_dir = os.path.join('/home/rakib/Multimodal-Datasets/VGGSound/video/frames', train_test_split, 'Image-{:02d}-FPS'.format(self.fps), f'{youtube_id}_{timestamp}')
                audio_dir = os.path.join('/home/rakib/Multimodal-Datasets/VGGSound/audio', train_test_split, f'{youtube_id}_{timestamp}.wav')

                if os.path.exists(video_dir) and os.path.exists(audio_dir) and len(os.listdir(video_dir)) > 3:
                    if train_test_split == 'train':
                        train_video_data.append(video_dir)
                        train_audio_data.append(audio_dir)
                        if item[2] not in train_class: 
                            train_class.append(item[2])
                        train_label.append(item[2])
                        train_items.append(item)
                    elif train_test_split == 'test':
                        test_video_data.append(video_dir)
                        test_audio_data.append(audio_dir)
                        if item[2] not in test_class: 
                            test_class.append(item[2])
                        test_label.append(item[2])
                        test_items.append(item)

        assert len(train_class) == len(test_class)
        # print(f"Number of classes: {len(train_class)}")
        self.classes = train_class
        class_dict = dict(zip(self.classes, range(len(self.classes))))

        if mode == 'train':
            self.video = train_video_data
            self.audio = train_audio_data
            self.label = [class_dict[label] for label in train_label]
            self.item = train_items
        elif mode == 'test':
            self.video = test_video_data
            self.audio = test_audio_data
            self.label = [class_dict[label] for label in test_label]
            self.item = test_items

    def __len__(self):
        return len(self.video)

    def __getitem__(self, idx):
        # if idx >= len(self.audio) or idx >= len(self.video) or idx >= len(self.label):
        #     print(f"Index {idx} out of range. Audio length: {len(self.audio)}, Video length: {len(self.video)}, Label length: {len(self.label)}")
        #     raise IndexError(f"Index {idx} out of range.")
        
        # Audio processing
        sample, rate = librosa.load(self.audio[idx], sr=16000, mono=True)
        while len(sample) / rate < 10.:
            sample = np.tile(sample, 2)

        start_point = random.randint(0, rate * 5)
        new_sample = sample[start_point:start_point + rate * 5]
        new_sample[new_sample > 1.] = 1.
        new_sample[new_sample < -1.] = -1.

        spectrogram = librosa.stft(new_sample, n_fft=256, hop_length=128)
        spectrogram = np.log(np.abs(spectrogram) + 1e-7)

        # Image transformations based on mode
        if self.mode == 'train':
            transform = transforms.Compose([
                transforms.RandomResizedCrop(224),
                transforms.RandomHorizontalFlip(),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
            ])
        else:
            transform = transforms.Compose([
                transforms.Resize(size=(224, 224)),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
            ])

        # Image processing
        image_samples = os.listdir(self.video[idx])
        image_samples = sorted(image_samples)
        images = torch.zeros((self.use_video_frames, 3, 224, 224))
        np.random.seed(999)
        select_index = np.random.choice(len(image_samples), size=self.use_video_frames, replace=False)

        for i, index in enumerate(select_index):
            img = Image.open(os.path.join(self.video[idx], image_samples[index])).convert('RGB')
            img = transform(img)
            images[i] = img

        images = torch.permute(images, (1, 0, 2, 3))

        # Label
        label = self.label[idx]
        item = self.item[idx]

        return item, spectrogram, images, label